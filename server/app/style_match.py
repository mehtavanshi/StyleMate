"""Style Match Suggestions engine.

Given ONE selected wardrobe item, recommend everything that matches it
(bottoms, tops, footwear, accessories, layering), the best/avoid color
pairings, occasion outfit ideas, and shopping links.

This is distinct from "Complete the Look" / gap detection:
- gap detection analyses the WHOLE wardrobe and finds what's MISSING;
- style match works on a SINGLE item and finds what GOES WELL WITH it.

Recommendations are deterministic and fashion-aware (no AI call needed):
category pairing rules, color theory (complementary / analogous /
monochromatic / triadic / neutral), fabric/fit/season compatibility, and
the user's own wardrobe are all consulted. Every suggestion carries a
compatibility score (0-100) and a human-readable reason.

Scoring reuses pairing_engine.score_pair() — the same blended color +
FashionCLIP-embedding + fabric + fit + season + hard-rule engine used
for real outfit suggestions — so a "you own this" match and a "you
could buy this" match are scored on the same scale, and results are
genuinely personalized per selected item rather than a static list.
Only matches scoring >= MATCH_THRESHOLD are returned to the client.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Literal
from urllib.parse import quote_plus

from sqlalchemy.orm import Session

from app.models import ClothingItem
from app.pairing_engine import (
    _FASHION_CLASHES,
    HSL_MAP,
    KNOWN_NEUTRAL_NAMES,
    _color_to_hsl,
    _hue_diff,
    _is_neutral_hsl,
    _normalise,
    score_pair,
)
from app.shopping_links import build_google_shopping_link, build_meesho_search_link

logger = logging.getLogger(__name__)

# Minimum match_percentage required for an item to be shown to the user.
# Tune this down (e.g. to 60-65) if categories are coming back empty too
# often for your current wardrobe/template coverage.
MATCH_THRESHOLD = 70

# Neutral colors (white/black/beige/grey/navy...) score high against almost
# ANY other color in the compatibility math below — that's correct color
# theory, but left unchecked it means the "safe" neutral candidate wins
# every category, every time, and every bottom ends up paired with the
# same white shirt. STYLE_VARIETY_THRESHOLD is a relaxed bar that lets
# genuinely stylish, non-neutral candidates qualify too, and
# MAX_NEUTRAL_PER_CATEGORY caps how many neutral picks can appear so they
# don't crowd everything else out. See _apply_style_diversity().
STYLE_VARIETY_THRESHOLD = 62
MAX_NEUTRAL_PER_CATEGORY = 1

# Max suggestions considered per category before threshold-filtering.
MAX_CANDIDATES_PER_CATEGORY = 6


def _primary_occasion(occasion_tag: str | None) -> str | None:
    if not occasion_tag:
        return None
    return occasion_tag.split(",")[0].strip()


# -- Category pairing rules --
# For a selected item of a given category, which other categories "go with" it.
# Ordered by typical importance for the UI.

_MATCHING_CATEGORIES: dict[str, list[str]] = {
    "top": ["bottom", "footwear", "accessory", "outerwear"],
    "bottom": ["top", "accessory", "footwear", "outerwear"],
    "dress": ["footwear", "accessory", "outerwear"],
    "outerwear": ["top", "bottom", "footwear", "accessory"],
    "footwear": ["top", "bottom", "dress", "accessory"],
    "accessory": ["top", "bottom", "dress", "footwear"],
    "kurti": ["bottom", "accessory", "footwear", "outerwear"],
}

# Section label per target category (what to show the user).
_SECTION_LABELS: dict[str, str] = {
    "top": "matchingTops",
    "bottom": "matchingBottoms",
    "footwear": "matchingFootwear",
    "accessory": "matchingAccessories",
    "outerwear": "layeringSuggestions",
    "dress": "matchingFootwear",
}

_OCCASIONS = [
    "casual",
    "office",
    "formal",
    "party",
    "wedding",
    "college",
    "date",
    "travel",
    "traditional",
    "festive",
    "streetwear",
]

# Shopping deep-link builders (no scraping — only search URLs).
_SHOP_BUILDERS: dict[str, str] = {
    "meesho": "https://www.meesho.com/search?q=",
    "myntra": "https://www.myntra.com/",
    "ajio": "https://www.ajio.com/search/",
    "amazon": "https://www.amazon.in/s?k=",
    "flipkart": "https://www.flipkart.com/search?q=",
}


@dataclass
class StyleMatchItem:
    name: str
    match_percentage: int
    reason: str
    owned: bool = False
    item_id: int | None = None
    category: str | None = None
    color: str | None = None
    image_url: str | None = None


@dataclass
class ShoppingLink:
    store: str
    url: str


@dataclass
class StyleMatchResult:
    selected_item: dict
    matching_bottoms: list[StyleMatchItem] = field(default_factory=list)
    matching_tops: list[StyleMatchItem] = field(default_factory=list)
    matching_footwear: list[StyleMatchItem] = field(default_factory=list)
    matching_accessories: list[StyleMatchItem] = field(default_factory=list)
    layering_suggestions: list[StyleMatchItem] = field(default_factory=list)
    recommended_colors: list[str] = field(default_factory=list)
    avoid_colors: list[str] = field(default_factory=list)
    occasion_outfits: list[dict] = field(default_factory=list)
    shopping_suggestions: list[dict] = field(default_factory=list)
    already_owned: list[StyleMatchItem] = field(default_factory=list)
    wardrobe_matches: list[StyleMatchItem] = field(default_factory=list)


# -- Color theory helpers --


def _complementary(h: float) -> float:
    return (h + 180) % 360


def _analogous(h: float) -> list[float]:
    return [((h - 30) % 360), ((h + 30) % 360)]


def _triadic(h: float) -> list[float]:
    return [((h + 120) % 360), ((h + 240) % 360)]


def _nearest_named_color(hsl: tuple[float, float, float]) -> str | None:
    h, s, l = hsl
    best: str | None = None
    best_d = float("inf")
    for name, (hh, ss, ll) in HSL_MAP.items():
        dh = _hue_diff(h, hh) / 180.0
        ds = abs(s - ss) / 100.0
        dl = abs(l - ll) / 100.0
        d = dh * 0.5 + ds * 0.25 + dl * 0.25
        if d < best_d:
            best_d = d
            best = name
    return best


def _hsl_for_color(color: str | None):
    return _color_to_hsl(color)


def _color_compat_score(color_a: str | None, color_b: str | None) -> tuple[float, str]:
    """Return (score 0-1, reason) for pairing two colors.

    Still used (independently of score_pair) purely to generate a
    human-readable color explanation for the "reason" text shown to
    the user — score_pair's own reason tags are terser.
    """
    ha = _hsl_for_color(color_a)
    hb = _hsl_for_color(color_b)
    if ha is None or hb is None:
        return 0.5, "Color compatibility unknown — neutral base."

    na = _normalise(color_a)
    nb = _normalise(color_b)
    if na == nb or _hue_diff(ha[0], hb[0]) <= 15:
        return 0.92, f"Monochromatic {na} palette — clean and cohesive."

    if _is_neutral_hsl(ha, color_a) or _is_neutral_hsl(hb, color_b):
        return 0.88, f"{na or 'neutral'} anchors {nb or 'neutral'} effortlessly."

    diff = _hue_diff(ha[0], hb[0])
    if frozenset({na, nb}) in _FASHION_CLASHES:
        return 0.25, f"{na} and {nb} clash in practice — avoid this combo."

    if 150 <= diff <= 210:
        return 0.85, f"Complementary colors ({na} + {nb}) create contrast."
    if diff <= 40:
        return 0.80, f"Analogous colors ({na} + {nb}) sit well together."
    if 100 <= diff <= 140:
        return 0.78, f"Triadic colors ({na} + {nb}) add playful balance."
    return 0.55, f"{na} and {nb} are wearable but not a standout pairing."


def _color_rotation(selected: ClothingItem) -> list[str]:
    """A small list of accent colors to cycle through for template
    placeholders, so different suggestion cards in the same category get
    genuinely different colors (and therefore genuinely different scores)
    instead of all sharing one computed color.
    """
    hsl = _hsl_for_color(selected.color)
    if hsl is None or _is_neutral_hsl(hsl, selected.color):
        return ["black", "white", "beige", "navy", "grey"]

    comp = _nearest_named_color((_complementary(hsl[0]), 45.0, 55.0))
    analogs = [_nearest_named_color((h, 45.0, 55.0)) for h in _analogous(hsl[0])]
    rotation = [c for c in [comp, *analogs, "black", "beige"] if c]

    seen: set[str] = set()
    return [c for c in rotation if not (c in seen or seen.add(c))]


def _is_neutral_color(color: str | None) -> bool:
    hsl = _color_to_hsl(color)
    if hsl is None:
        return False
    return _is_neutral_hsl(hsl, color)


def _apply_style_diversity(
    candidates: list["StyleMatchItem"], max_items: int = MAX_CANDIDATES_PER_CATEGORY
) -> list["StyleMatchItem"]:
    """Turn score-sorted candidates into a final, visually varied list.

    Without this, the highest-scoring items in a category are almost
    always the neutral ones (white/black/beige score well against nearly
    any color), so every suggestion set collapses into the same 1-2 safe
    picks. Here: at most MAX_NEUTRAL_PER_CATEGORY neutral items are kept
    at the strict MATCH_THRESHOLD, and non-neutral (colorful, trendier)
    items are allowed through at the more relaxed STYLE_VARIETY_THRESHOLD
    so a genuinely styled set — not just "whatever matches everything" —
    reaches the user.
    """
    neutral_used = 0
    final: list["StyleMatchItem"] = []
    for c in candidates:
        neutral = _is_neutral_color(c.color)
        bar = MATCH_THRESHOLD if neutral else STYLE_VARIETY_THRESHOLD
        if c.match_percentage < bar:
            continue
        if neutral:
            if neutral_used >= MAX_NEUTRAL_PER_CATEGORY:
                continue
            neutral_used += 1
        final.append(c)
        if len(final) >= max_items:
            break
    return final


def _humanize_pair_reason(raw: str) -> str:
    """Turn score_pair's terse tag reason ('great colors; occasion match')
    into a readable sentence for wardrobe-owned matches."""
    if not raw or raw in ("mixed compatibility", "target_gender mismatch"):
        return "Versatile pairing from your wardrobe."
    parts = [p.strip() for p in raw.split(";") if p.strip()]
    text = ", ".join(parts)
    return text[0].upper() + text[1:] + "."


# -- Hypothetical (not-yet-owned) candidate, scored with the real engine --


@dataclass
class _HypotheticalItem:
    """A candidate purchase suggestion, shaped enough like a ClothingItem
    to be scored by pairing_engine.score_pair() — reusing the exact same
    color/fabric/fit/season/occasion/embedding-blended logic used for real
    wardrobe pairings, instead of a separate, weaker scoring path.
    """

    color: str | None = None
    fabric_type: str | None = None
    fit_type: str | None = None
    season: str | None = None
    occasion_tag: str | None = None
    formality_score: int | None = None
    target_gender: str | None = None
    style_tags: str | None = None
    embedding_json: str | None = None
    pattern: str | None = None


# -- Occasion-aware suggestion templates --
# Each entry: display name (may contain "{color}"), a fixed color (None =
# pull the next color from the rotation so cards differ), and a fabric
# hint used for real fabric-affinity/clash scoring against the selected
# item's own fabric_type.

_FOOTWEAR_TEMPLATES: dict[str, list[dict]] = {
    "formal": [
        {"name": "{color} Oxfords", "color": None, "fabric": "leather"},
        {"name": "Black Leather Loafers", "color": "black", "fabric": "leather"},
        {"name": "{color} Derby Shoes", "color": None, "fabric": "leather"},
    ],
    "office": [
        {"name": "Black Loafers", "color": "black", "fabric": "leather"},
        {"name": "{color} Pointed Flats", "color": None, "fabric": "leather"},
        {"name": "Brown Brogues", "color": "brown", "fabric": "leather"},
    ],
    "party": [
        {"name": "{color} Block Heels", "color": None, "fabric": "synthetic"},
        {"name": "Metallic Strappy Heels", "color": "gold", "fabric": "synthetic"},
        {"name": "Statement Sneakers", "color": "white", "fabric": "synthetic"},
    ],
    "date": [
        {"name": "{color} Block Heels", "color": None, "fabric": "synthetic"},
        {"name": "Black Ankle Boots", "color": "black", "fabric": "leather"},
        {"name": "Brown Loafers", "color": "brown", "fabric": "leather"},
    ],
    "wedding": [
        {"name": "{color} Juttis", "color": None, "fabric": "leather"},
        {"name": "Embellished Mojaris", "color": "gold", "fabric": "leather"},
        {"name": "Kolhapuri Sandals", "color": "brown", "fabric": "leather"},
    ],
    "traditional": [
        {"name": "{color} Juttis", "color": None, "fabric": "leather"},
        {"name": "Kolhapuri Chappals", "color": "brown", "fabric": "leather"},
        {"name": "Embellished Mojaris", "color": "gold", "fabric": "leather"},
    ],
    "festive": [
        {"name": "{color} Juttis", "color": None, "fabric": "leather"},
        {"name": "Embellished Flats", "color": "gold", "fabric": "synthetic"},
        {"name": "{color} Block Heels", "color": None, "fabric": "synthetic"},
    ],
    "streetwear": [
        {"name": "Chunky White Sneakers", "color": "white", "fabric": "synthetic"},
        {"name": "{color} High-Top Sneakers", "color": None, "fabric": "canvas"},
        {"name": "Navy Slip-On Loafers", "color": "navy", "fabric": "canvas"},
    ],
    "college": [
        {"name": "White Sneakers", "color": "white", "fabric": "canvas"},
        {"name": "{color} Canvas Shoes", "color": None, "fabric": "canvas"},
        {"name": "Navy Slip-On Loafers", "color": "navy", "fabric": "canvas"},
    ],
    "travel": [
        {"name": "Grey Comfortable Sneakers", "color": "grey", "fabric": "canvas"},
        {"name": "{color} Walking Shoes", "color": None, "fabric": "synthetic"},
        {"name": "Brown Slip-On Loafers", "color": "brown", "fabric": "leather"},
    ],
    "casual": [
        {"name": "White Sneakers", "color": "white", "fabric": "canvas"},
        {"name": "{color} Espadrilles", "color": None, "fabric": "cotton"},
        {"name": "Grey Slip-On Sneakers", "color": "grey", "fabric": "canvas"},
    ],
}

_ACCESSORY_TEMPLATES: dict[str, list[dict]] = {
    "formal_men": [
        {"name": "{color} Silk Tie", "color": None, "fabric": "silk"},
        {"name": "Brown Leather Belt", "color": "brown", "fabric": "leather"},
        {"name": "Silver Cufflinks", "color": "silver", "fabric": None},
    ],
    "formal_default": [
        {"name": "Structured {color} Tote Bag", "color": None, "fabric": "leather"},
        {"name": "Minimal Silver Watch", "color": "silver", "fabric": None},
        {"name": "{color} Leather Belt", "color": None, "fabric": "leather"},
    ],
    "office_men": [
        {"name": "Brown Leather Belt", "color": "brown", "fabric": "leather"},
        {"name": "Silver Watch", "color": "silver", "fabric": None},
        {"name": "{color} Pocket Square", "color": None, "fabric": "silk"},
    ],
    "office_default": [
        {"name": "Structured Black Tote Bag", "color": "black", "fabric": "leather"},
        {"name": "Minimal Watch", "color": "silver", "fabric": None},
        {"name": "{color} Leather Belt", "color": None, "fabric": "leather"},
    ],
    "party": [
        {"name": "Statement {color} Earrings", "color": None, "fabric": None},
        {"name": "Gold Clutch Bag", "color": "gold", "fabric": "synthetic"},
        {"name": "Layered Gold Necklace", "color": "gold", "fabric": None},
    ],
    "date": [
        {"name": "Delicate {color} Necklace", "color": None, "fabric": None},
        {"name": "Black Clutch", "color": "black", "fabric": "synthetic"},
        {"name": "Black Sunglasses", "color": "black", "fabric": None},
    ],
    "wedding": [
        {"name": "Gold Jhumkas", "color": "gold", "fabric": None},
        {"name": "{color} Potli Bag", "color": None, "fabric": "silk"},
        {"name": "Statement Gold Bangles", "color": "gold", "fabric": None},
    ],
    "traditional": [
        {"name": "Gold Jhumkas", "color": "gold", "fabric": None},
        {"name": "{color} Bangles", "color": None, "fabric": None},
        {"name": "Maroon Potli Bag", "color": "maroon", "fabric": "silk"},
    ],
    "festive": [
        {"name": "Statement {color} Jewelry", "color": None, "fabric": None},
        {"name": "Gold Potli Bag", "color": "gold", "fabric": "silk"},
        {"name": "Gold Jhumkas", "color": "gold", "fabric": None},
    ],
    "streetwear": [
        {"name": "Silver Chain Necklace", "color": "silver", "fabric": None},
        {"name": "{color} Crossbody Bag", "color": None, "fabric": "canvas"},
        {"name": "Black Cap", "color": "black", "fabric": "cotton"},
    ],
    "college": [
        {"name": "Beige Canvas Tote Bag", "color": "beige", "fabric": "cotton"},
        {"name": "Black Sunglasses", "color": "black", "fabric": None},
        {"name": "Minimal {color} Chain", "color": None, "fabric": None},
    ],
    "travel": [
        {"name": "Black Crossbody Sling Bag", "color": "black", "fabric": "canvas"},
        {"name": "Black Sunglasses", "color": "black", "fabric": None},
        {"name": "{color} Scarf", "color": None, "fabric": "cotton"},
    ],
    "casual": [
        {"name": "Beige Canvas Tote Bag", "color": "beige", "fabric": "cotton"},
        {"name": "Black Sunglasses", "color": "black", "fabric": None},
        {"name": "Minimal {color} Chain", "color": None, "fabric": None},
    ],
}

_OUTERWEAR_TEMPLATES: dict[str, list[dict]] = {
    "formal": [
        {"name": "{color} Tailored Blazer", "color": None, "fabric": "wool"},
        {"name": "Beige Trench Coat", "color": "beige", "fabric": "wool"},
    ],
    "office": [
        {"name": "{color} Blazer", "color": None, "fabric": "wool"},
        {"name": "Beige Trench Coat", "color": "beige", "fabric": "wool"},
    ],
    "party": [
        {"name": "{color} Blazer", "color": None, "fabric": "synthetic"},
        {"name": "Black Leather Jacket", "color": "black", "fabric": "leather"},
    ],
    "date": [
        {"name": "{color} Cardigan", "color": None, "fabric": "knit"},
        {"name": "Black Leather Jacket", "color": "black", "fabric": "leather"},
    ],
    "wedding": [
        {"name": "Navy Nehru Jacket", "color": "navy", "fabric": "silk"},
        {"name": "{color} Shrug", "color": None, "fabric": "silk"},
    ],
    "traditional": [
        {"name": "Navy Nehru Jacket", "color": "navy", "fabric": "silk"},
        {"name": "{color} Dupatta", "color": None, "fabric": "silk"},
    ],
    "festive": [
        {"name": "Gold Embellished Jacket", "color": "gold", "fabric": "synthetic"},
        {"name": "{color} Shrug", "color": None, "fabric": "silk"},
    ],
    "streetwear": [
        {"name": "Grey Oversized Hoodie", "color": "grey", "fabric": "cotton"},
        {"name": "Navy Varsity Jacket", "color": "navy", "fabric": "synthetic"},
    ],
    "college": [
        {"name": "Blue Denim Jacket", "color": "blue", "fabric": "denim"},
        {"name": "{color} Cardigan", "color": None, "fabric": "knit"},
    ],
    "travel": [
        {"name": "Lightweight {color} Jacket", "color": None, "fabric": "cotton"},
        {"name": "Beige Cardigan", "color": "beige", "fabric": "knit"},
    ],
    "casual": [
        {"name": "Blue Denim Jacket", "color": "blue", "fabric": "denim"},
        {"name": "{color} Bomber Jacket", "color": None, "fabric": "cotton"},
    ],
}

_BOTTOM_TEMPLATES: dict[str, list[dict]] = {
    "formal": [
        {"name": "{color} Tailored Trousers", "color": None, "fabric": "wool"},
        {"name": "Black Formal Pants", "color": "black", "fabric": "wool"},
        {"name": "{color} Pencil Skirt", "color": None, "fabric": "wool"},
    ],
    "office": [
        {"name": "{color} Straight Trousers", "color": None, "fabric": "cotton"},
        {"name": "Black Pencil Pants", "color": "black", "fabric": "cotton"},
        {"name": "{color} Wide-Leg Trousers", "color": None, "fabric": "cotton"},
        {"name": "{color} Pleated Midi Skirt", "color": None, "fabric": "cotton"},
    ],
    "party": [
        {"name": "{color} Satin Pants", "color": None, "fabric": "synthetic"},
        {"name": "Black Skinny Pants", "color": "black", "fabric": "cotton"},
        {"name": "{color} Mini Skirt", "color": None, "fabric": "synthetic"},
        {"name": "{color} Sequin Skirt", "color": None, "fabric": "synthetic"},
    ],
    "traditional": [
        {"name": "{color} Palazzo Pants", "color": None, "fabric": "cotton"},
        {"name": "Beige Dhoti Pants", "color": "beige", "fabric": "cotton"},
        {"name": "Printed {color} Palazzos", "color": None, "fabric": "cotton"},
    ],
    "festive": [
        {"name": "{color} Palazzo Pants", "color": None, "fabric": "silk"},
        {"name": "Gold Sharara Pants", "color": "gold", "fabric": "silk"},
        {"name": "{color} Lehenga Skirt", "color": None, "fabric": "silk"},
    ],
    "wedding": [
        {"name": "{color} Palazzo Pants", "color": None, "fabric": "silk"},
        {"name": "Gold Sharara Pants", "color": "gold", "fabric": "silk"},
        {"name": "{color} Lehenga Skirt", "color": None, "fabric": "silk"},
    ],
    "streetwear": [
        {"name": "Olive Cargo Pants", "color": "olive", "fabric": "cotton"},
        {"name": "{color} Joggers", "color": None, "fabric": "cotton"},
        {"name": "Baggy {color} Jeans", "color": None, "fabric": "denim"},
        {"name": "{color} Bike Shorts", "color": None, "fabric": "synthetic"},
    ],
    "college": [
        {"name": "Blue Straight Jeans", "color": "blue", "fabric": "denim"},
        {"name": "{color} Joggers", "color": None, "fabric": "cotton"},
        {"name": "{color} Mom Jeans", "color": None, "fabric": "denim"},
        {"name": "Pleated {color} Mini Skirt", "color": None, "fabric": "cotton"},
    ],
    "travel": [
        {"name": "{color} Joggers", "color": None, "fabric": "cotton"},
        {"name": "Khaki Comfortable Chinos", "color": "khaki", "fabric": "cotton"},
        {"name": "{color} Culottes", "color": None, "fabric": "cotton"},
    ],
    "date": [
        {"name": "{color} Skinny Jeans", "color": None, "fabric": "denim"},
        {"name": "Black Tailored Trousers", "color": "black", "fabric": "wool"},
        {"name": "{color} Wrap Skirt", "color": None, "fabric": "cotton"},
        {"name": "{color} Mini Skirt", "color": None, "fabric": "synthetic"},
    ],
    "casual": [
        {"name": "Blue Straight Jeans", "color": "blue", "fabric": "denim"},
        {"name": "{color} Chinos", "color": None, "fabric": "cotton"},
        {"name": "Olive Cargo Pants", "color": "olive", "fabric": "cotton"},
        {"name": "{color} Mom Jeans", "color": None, "fabric": "denim"},
        {"name": "{color} Wide-Leg Pants", "color": None, "fabric": "cotton"},
    ],
}

_TOP_TEMPLATES: dict[str, list[dict]] = {
    "formal": [
        {"name": "White Formal Shirt", "color": "white", "fabric": "cotton"},
        {"name": "{color} Silk Blouse", "color": None, "fabric": "silk"},
        {"name": "{color} Pussy-Bow Blouse", "color": None, "fabric": "silk"},
        {"name": "Structured {color} Shell Top", "color": None, "fabric": "cotton"},
    ],
    "office": [
        {"name": "White Shirt", "color": "white", "fabric": "cotton"},
        {"name": "{color} Blouse", "color": None, "fabric": "cotton"},
        {"name": "{color} Puff-Sleeve Top", "color": None, "fabric": "cotton"},
        {"name": "Striped {color} Shirt", "color": None, "fabric": "cotton"},
    ],
    "party": [
        {"name": "{color} Satin Top", "color": None, "fabric": "synthetic"},
        {"name": "Black Bodysuit", "color": "black", "fabric": "cotton"},
        {"name": "{color} Corset Top", "color": None, "fabric": "synthetic"},
        {"name": "Sequin {color} Top", "color": None, "fabric": "synthetic"},
        {"name": "{color} Halter Top", "color": None, "fabric": "synthetic"},
    ],
    "traditional": [
        {"name": "{color} Kurti", "color": None, "fabric": "cotton"},
        {"name": "Beige Embroidered Kurta", "color": "beige", "fabric": "cotton"},
        {"name": "{color} Anarkali Top", "color": None, "fabric": "silk"},
        {"name": "Printed {color} Kurti", "color": None, "fabric": "cotton"},
    ],
    "festive": [
        {"name": "{color} Embellished Top", "color": None, "fabric": "silk"},
        {"name": "Gold Silk Kurti", "color": "gold", "fabric": "silk"},
        {"name": "{color} Sequin Blouse", "color": None, "fabric": "synthetic"},
        {"name": "Mirror-Work {color} Top", "color": None, "fabric": "cotton"},
    ],
    "wedding": [
        {"name": "{color} Silk Kurti", "color": None, "fabric": "silk"},
        {"name": "Gold Embellished Blouse", "color": "gold", "fabric": "silk"},
        {"name": "{color} Zari Blouse", "color": None, "fabric": "silk"},
    ],
    "streetwear": [
        {"name": "Grey Hoodie", "color": "grey", "fabric": "cotton"},
        {"name": "{color} Oversized Tee", "color": None, "fabric": "cotton"},
        {"name": "{color} Graphic Crop Top", "color": None, "fabric": "cotton"},
        {"name": "Cropped {color} Hoodie", "color": None, "fabric": "cotton"},
    ],
    "college": [
        {"name": "Black T-Shirt", "color": "black", "fabric": "cotton"},
        {"name": "{color} Sweater", "color": None, "fabric": "knit"},
        {"name": "{color} Crop Top", "color": None, "fabric": "cotton"},
        {"name": "Printed {color} Tee", "color": None, "fabric": "cotton"},
    ],
    "travel": [
        {"name": "{color} T-Shirt", "color": None, "fabric": "cotton"},
        {"name": "Grey Sweatshirt", "color": "grey", "fabric": "cotton"},
        {"name": "{color} Wrap Top", "color": None, "fabric": "cotton"},
    ],
    "date": [
        {"name": "{color} Fitted Top", "color": None, "fabric": "cotton"},
        {"name": "Black Shirt", "color": "black", "fabric": "cotton"},
        {"name": "{color} Cami Top", "color": None, "fabric": "silk"},
        {"name": "{color} Wrap Blouse", "color": None, "fabric": "cotton"},
    ],
    "casual": [
        {"name": "White Shirt", "color": "white", "fabric": "cotton"},
        {"name": "Black T-Shirt", "color": "black", "fabric": "cotton"},
        {"name": "{color} Sweater", "color": None, "fabric": "knit"},
        {"name": "{color} Crop Top", "color": None, "fabric": "cotton"},
        {"name": "Printed {color} Blouse", "color": None, "fabric": "cotton"},
    ],
}


def _suggestion_templates(selected: ClothingItem, target: str) -> list[dict]:
    """Pick the right occasion (and, where it matters, gender) branch of
    templates for this selected item and target category."""
    sc = _normalise(selected.category)
    occ = _primary_occasion(selected.occasion_tag) or "casual"
    gender = _normalise(selected.target_gender)

    if target == "bottom":
        if sc not in ("top", "shirt", "tshirt", "sweater", "hoodie", "kurti"):
            return []
        return _BOTTOM_TEMPLATES.get(occ, _BOTTOM_TEMPLATES["casual"])
    if target == "top":
        if sc not in ("bottom", "jeans", "trousers", "pants", "shorts", "leggings"):
            return []
        return _TOP_TEMPLATES.get(occ, _TOP_TEMPLATES["casual"])
    if target == "footwear":
        return _FOOTWEAR_TEMPLATES.get(occ, _FOOTWEAR_TEMPLATES["casual"])
    if target == "accessory":
        if occ in ("formal", "office"):
            key = f"{occ}_men" if gender == "men" else f"{occ}_default"
            return _ACCESSORY_TEMPLATES.get(key, _ACCESSORY_TEMPLATES["casual"])
        return _ACCESSORY_TEMPLATES.get(occ, _ACCESSORY_TEMPLATES["casual"])
    if target == "outerwear":
        return _OUTERWEAR_TEMPLATES.get(occ, _OUTERWEAR_TEMPLATES["casual"])
    return []


# -- Generated (non-owned) suggestions --


def _generated_suggestions(
    selected: ClothingItem,
    target_category: str,
    owned_ids: set[int],
    count: int = MAX_CANDIDATES_PER_CATEGORY,
) -> list[StyleMatchItem]:
    """Build concrete, named PURCHASE suggestions for a category.

    Each candidate is a distinct hypothetical item (its own color and
    fabric, chosen for the selected item's actual occasion) scored via
    pairing_engine.score_pair() against the selected item — the same
    engine used for real outfit scoring. This is what makes results
    differ by category AND by item, instead of a fixed list with a
    near-identical percentage stamped on every card.

    Returns candidates sorted by score, descending. Threshold-filtering
    (MATCH_THRESHOLD) happens in generate_style_match(), not here, so
    other callers (e.g. build_item_match_queries) can still use the
    top raw candidate even if it's below the display threshold.
    """
    templates = _suggestion_templates(selected, target_category)
    if not templates:
        return []

    rotation = _color_rotation(selected)
    occ = _primary_occasion(selected.occasion_tag) or "casual"

    scored: list[StyleMatchItem] = []
    for i, tpl in enumerate(templates[:count]):
        color = tpl["color"] or rotation[i % len(rotation)]
        name = (
            tpl["name"].format(color=color.capitalize())
            if "{color}" in tpl["name"]
            else tpl["name"]
        )

        hypo = _HypotheticalItem(
            color=color,
            fabric_type=tpl.get("fabric"),
            season=selected.season,
            occasion_tag=selected.occasion_tag,
            formality_score=getattr(selected, "formality_score", None),
            target_gender=selected.target_gender,
        )
        raw_score, _raw_reason, breakdown = score_pair(selected, hypo)
        pct = int(round(raw_score * 100))

        _col_score, col_reason = _color_compat_score(selected.color, color)
        reason_bits = [col_reason]
        if breakdown.get("fabric", 0.5) >= 0.8:
            reason_bits.append(
                f"fabric complements your {selected.fabric_type or 'piece'}"
            )
        elif breakdown.get("fabric", 0.5) <= 0.25:
            reason_bits.append("fabric contrast — style with care")
        reason_bits.append(f"fits {occ} occasions")
        reason = " — ".join(reason_bits) + "."

        scored.append(
            StyleMatchItem(
                name=name,
                match_percentage=pct,
                reason=reason,
                owned=False,
                category=target_category,
                color=color,
            )
        )

    scored.sort(key=lambda x: x.match_percentage, reverse=True)
    return scored


# -- Color recommendations / avoid --


def _recommend_avoid_colors(selected: ClothingItem) -> tuple[list[str], list[str]]:
    hsl = _hsl_for_color(selected.color)
    if hsl is None:
        return ["beige", "navy blue", "black", "olive green", "grey"], [
            "neon green",
            "bright orange",
        ]

    rec: list[str] = []
    if _is_neutral_hsl(hsl, selected.color):
        rec = ["navy blue", "black", "beige", "olive green", "grey", "brown"]
    else:
        comp = _nearest_named_color((_complementary(hsl[0]), 45, 55))
        analog = [_nearest_named_color((h, 45, 55)) for h in _analogous(hsl[0])]
        tri = [_nearest_named_color((h, 45, 55)) for h in _triadic(hsl[0])]
        for c in [comp] + analog + tri:
            if c and c not in rec:
                rec.append(c)
        for n in ["beige", "navy blue", "black", "grey", "olive green"]:
            if n not in rec:
                rec.append(n)
        rec = rec[:6]

    clashes: list[str] = []
    na = _normalise(selected.color)
    for pair in _FASHION_CLASHES:
        if na in pair:
            other = next(iter(pair - {na}))
            clashes.append(other)
    avoid = clashes + ["neon green", "bright orange"]
    seen = set()
    avoid = [c for c in avoid if not (c in seen or seen.add(c))]
    return rec, avoid[:5]


def _occasion_ideas(selected: ClothingItem) -> list[dict]:
    sel_occ = _primary_occasion(selected.occasion_tag) or "casual"
    mapping = {
        "casual": ["Office Casual", "Streetwear", "Weekend Casual"],
        "office": ["Office Casual", "Business Formal", "Travel"],
        "formal": ["Business Formal", "Wedding Guest", "Date Night"],
        "party": ["Date Night", "Festive", "Party Glam"],
        "wedding": ["Wedding Guest", "Festive", "Date Night"],
        "college": ["College Day", "Streetwear", "Casual Hangout"],
        "date": ["Date Night", "Dinner Out", "Smart Casual"],
        "travel": ["Travel", "Weekend Casual", "Airport Look"],
        "traditional": ["Traditional", "Festive", "Wedding Guest"],
        "festive": ["Festive", "Party", "Traditional"],
        "streetwear": ["Streetwear", "College Day", "Weekend Casual"],
    }
    ideas = mapping.get(sel_occ, ["Casual", "Office Casual", "Weekend Casual"])
    return [
        {"name": idea, "based_on": selected.name or selected.category} for idea in ideas
    ]


def _gender_label(target_gender: str | None) -> str:
    """Map a ClothingItem.target_gender value to a search-friendly gender
    qualifier ('Men' / 'Women'). Returns '' for unisex/unknown so we don't
    over-narrow a search that's meant to stay broad."""
    g = _normalise(target_gender)
    if g in ("men", "male", "man", "boys", "boy"):
        return "Men"
    if g in ("women", "female", "woman", "girls", "girl"):
        return "Women"
    return ""


def _gendered_query(item_name: str, target_gender: str | None) -> str:
    """Prefix a shopping search query with the wearer's gender, e.g.
    'Black Oxfords' -> 'Men Black Oxfords', so results on Myntra/Ajio/
    Amazon/Flipkart/Meesho/Google Shopping land on the right section
    instead of a generic (often women's-skewed) search."""
    label = _gender_label(target_gender)
    return f"{label} {item_name}".strip() if label else item_name


def _build_shop_links(query: str) -> list[dict]:
    q = quote_plus(_normalise(query) or query)
    dash = _normalise(query).replace(" ", "-")
    links = [
        {"store": "meesho", "url": f"{_SHOP_BUILDERS['meesho']}{q}"},
        {"store": "myntra", "url": f"{_SHOP_BUILDERS['myntra']}{dash}"},
        {"store": "ajio", "url": f"{_SHOP_BUILDERS['ajio']}{dash}"},
        {"store": "amazon", "url": f"{_SHOP_BUILDERS['amazon']}{q}"},
        {"store": "flipkart", "url": f"{_SHOP_BUILDERS['flipkart']}{q}"},
    ]
    return links


# -- Main entry --


def generate_style_match(item_id: int, db: Session) -> StyleMatchResult:
    selected = db.query(ClothingItem).filter(ClothingItem.id == item_id).first()
    if not selected:
        raise ValueError(f"Item {item_id} not found")

    user_id = selected.user_id
    all_items = db.query(ClothingItem).filter(ClothingItem.user_id == user_id).all()
    owned_ids = {it.id for it in all_items}

    partner_cats = _MATCHING_CATEGORIES.get(_normalise(selected.category), [])

    section_map: dict[str, list[StyleMatchItem]] = {
        "top": [],
        "bottom": [],
        "footwear": [],
        "accessory": [],
        "outerwear": [],
    }

    # 1) Wardrobe matches (owned items in partner categories), scored with
    #    the real pairing engine and filtered to MATCH_THRESHOLD+.
    wardrobe_matches: list[StyleMatchItem] = []
    for it in all_items:
        if it.id == selected.id:
            continue
        if _normalise(it.category) not in partner_cats:
            continue
        raw_score, raw_reason, _bd = score_pair(selected, it)
        pct = int(round(raw_score * 100))
        if pct < MATCH_THRESHOLD:
            continue
        wardrobe_matches.append(
            StyleMatchItem(
                name=it.name or f"{it.category}",
                match_percentage=pct,
                reason=_humanize_pair_reason(raw_reason),
                owned=True,
                item_id=it.id,
                category=it.category,
                color=it.color,
                image_url=it.image_url,
            )
        )
    wardrobe_matches.sort(key=lambda x: x.match_percentage, reverse=True)

    # 2) Generated suggestions per partner category (not owned), filtered
    #    to MATCH_THRESHOLD+.
    for cat in partner_cats:
        generated = _generated_suggestions(selected, cat, owned_ids)
        section_map[cat].extend(_apply_style_diversity(generated))

    # 3) Split into the response buckets.
    result = StyleMatchResult(
        selected_item={
            "id": selected.id,
            "name": selected.name,
            "category": selected.category,
            "color": selected.color,
            "pattern": selected.pattern,
            "fabric_type": selected.fabric_type,
            "sleeve_length": selected.sleeve_length,
            "occasion_tag": selected.occasion_tag,
            "season": selected.season,
            "target_gender": selected.target_gender,
            "image_url": selected.image_url,
        },
        matching_bottoms=section_map.get("bottom", []),
        matching_tops=section_map.get("top", []),
        matching_footwear=section_map.get("footwear", []),
        matching_accessories=section_map.get("accessory", []),
        layering_suggestions=section_map.get("outerwear", []),
        already_owned=wardrobe_matches,
        wardrobe_matches=wardrobe_matches,
    )

    rec, avoid = _recommend_avoid_colors(selected)
    result.recommended_colors = rec
    result.avoid_colors = avoid
    result.occasion_outfits = _occasion_ideas(selected)

    # 4) Shopping suggestions: one group per partner category's top
    #    (already threshold-qualified) pick.
    for cat in partner_cats:
        picks = section_map.get(cat, [])
        if not picks:
            continue
        top = picks[0]
        shop_query = _gendered_query(top.name, selected.target_gender)
        links = _build_shop_links(shop_query)
        links.append(
            {"store": "Google Shopping", "url": build_google_shopping_link(shop_query)}
        )
        links.append({"store": "Meesho", "url": build_meesho_search_link(shop_query)})
        result.shopping_suggestions.append(
            {
                "category": cat,
                "item_name": top.name,
                "match_percentage": top.match_percentage,
                "reason": top.reason,
                "owned": False,
                "shopping_links": links,
            }
        )

    return result


def style_match_to_dict(result: StyleMatchResult) -> dict:
    """Serialise to the structured JSON contract."""

    def _item(d: StyleMatchItem) -> dict:
        return {
            "name": d.name,
            "match_percentage": d.match_percentage,
            "reason": d.reason,
            "owned": d.owned,
            "item_id": d.item_id,
            "category": d.category,
            "color": d.color,
            "image_url": d.image_url,
        }

    return {
        "selectedItem": result.selected_item,
        "matchingBottoms": [_item(d) for d in result.matching_bottoms],
        "matchingTops": [_item(d) for d in result.matching_tops],
        "matchingFootwear": [_item(d) for d in result.matching_footwear],
        "matchingAccessories": [_item(d) for d in result.matching_accessories],
        "layeringSuggestions": [_item(d) for d in result.layering_suggestions],
        "recommendedColors": result.recommended_colors,
        "avoidColors": result.avoid_colors,
        "occasionOutfits": result.occasion_outfits,
        "shoppingSuggestions": result.shopping_suggestions,
        "alreadyOwned": [_item(d) for d in result.already_owned],
    }


def build_item_match_queries(item_id: int, db: Session) -> list[dict]:
    """Build search queries for each category that matches the given item.

    Returns ``[{label: "bottom", query: "Black Trousers"}, ...]``.
    """
    selected = db.query(ClothingItem).filter(ClothingItem.id == item_id).first()
    if not selected:
        return []

    partner_cats = _MATCHING_CATEGORIES.get(_normalise(selected.category), [])
    queries: list[dict] = []

    for cat in partner_cats:
        names = _generated_suggestions(selected, cat, set())
        query = names[0].name if names else cat.capitalize()
        queries.append({"label": cat, "query": query})

    return queries
