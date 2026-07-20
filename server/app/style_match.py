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
compatibility score (0–100) and a human-readable reason.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Literal
from urllib.parse import quote_plus

from sqlalchemy.orm import Session

from app.models import ClothingItem
from app.pairing_engine import (
    HSL_MAP,
    KNOWN_NEUTRAL_NAMES,
    _FASHION_CLASHES,
    _color_to_hsl,
    _hue_diff,
    _is_neutral_hsl,
    _normalise,
)

logger = logging.getLogger(__name__)

# ── Category pairing rules ──
# For a selected item of a given category, which other categories "go with" it.
# Ordered by typical importance for the UI.

_MATCHING_CATEGORIES: dict[str, list[str]] = {
    "top": ["bottom", "footwear", "accessory", "outerwear"],
    "bottom": ["top", "footwear", "accessory", "outerwear"],
    "dress": ["footwear", "accessory", "outerwear"],
    "outerwear": ["top", "bottom", "footwear", "accessory"],
    "footwear": ["top", "bottom", "dress", "accessory"],
    "accessory": ["top", "bottom", "dress", "footwear"],
    "kurti": ["bottom", "footwear", "accessory", "outerwear"],
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
    "casual", "office", "formal", "party", "wedding",
    "college", "date", "travel", "traditional", "festive", "streetwear",
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


# ── Color theory helpers ──

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
    """Return (score 0-1, reason) for pairing two colors."""
    ha = _hsl_for_color(color_a)
    hb = _hsl_for_color(color_b)
    if ha is None or hb is None:
        return 0.5, "Color compatibility unknown — neutral base."

    na = _normalise(color_a)
    nb = _normalise(color_b)
    # Same/very close color → monochromatic.
    if na == nb or _hue_diff(ha[0], hb[0]) <= 15:
        return 0.92, f"Monochromatic {na} palette — clean and cohesive."

    # One (or both) neutral → safe anchor.
    if _is_neutral_hsl(ha, color_a) or _is_neutral_hsl(hb, color_b):
        return 0.88, f"{na or 'neutral'} anchors {nb or 'neutral'} effortlessly."

    diff = _hue_diff(ha[0], hb[0])
    # Fashion-specific clash overrides theory.
    if frozenset({na, nb}) in _FASHION_CLASHES:
        return 0.25, f"{na} and {nb} clash in practice — avoid this combo."

    if 150 <= diff <= 210:
        return 0.85, f"Complementary colors ({na} + {nb}) create contrast."
    if diff <= 40:
        return 0.80, f"Analogous colors ({na} + {nb}) sit well together."
    if 100 <= diff <= 140:
        return 0.78, f"Triadic colors ({na} + {nb}) add playful balance."
    return 0.55, f"{na} and {nb} are wearable but not a standout pairing."


# ── Attribute compatibility ──

def _season_score(season_a: str | None, season_b: str | None) -> float:
    sa = _normalise(season_a)
    sb = _normalise(season_b)
    if not sa or not sb:
        return 0.5
    if sa == sb:
        return 0.9
    if "all-season" in (sa, sb):
        return 0.85
    return 0.3


def _occasion_score(oa: str | None, ob: str | None) -> float:
    a = _normalise(oa)
    b = _normalise(ob)
    if not a or not b:
        return 0.5
    return 0.9 if a == b else 0.45


def _fit_score(fa: str | None, fb: str | None) -> float:
    a = _normalise(fa)
    b = _normalise(fb)
    if not a or not b:
        return 0.5
    if a == b:
        return 0.7
    if {a, b} == {"slim", "oversized"} or {a, b} == {"loose", "slim"}:
        return 0.9
    if {a, b} == {"oversized", "loose"}:
        return 0.3
    return 0.6


def _gender_ok(a: str | None, b: str | None) -> bool:
    g1 = _normalise(a) or "unisex"
    g2 = _normalise(b) or "unisex"
    return g1 == "unisex" or g2 == "unisex" or g1 == g2


# ── Core item-to-item compatibility ──

def _compatibility(selected: ClothingItem, other: ClothingItem) -> tuple[int, str]:
    """Return (score 0-100, reason) for pairing two wardrobe items."""
    parts: list[str] = []
    scores: list[float] = []

    col_s, col_r = _color_compat_score(selected.color, other.color)
    scores.append(col_s)
    parts.append(col_r)

    sc_s = _season_score(selected.season, other.season)
    scores.append(sc_s * 0.8 + 0.2 * 0.5)
    if sc_s >= 0.85:
        parts.append("same season")

    oc_s = _occasion_score(selected.occasion_tag, other.occasion_tag)
    scores.append(oc_s)
    if oc_s >= 0.9:
        parts.append(f"both {_normalise(selected.occasion_tag)} wear")

    ft_s = _fit_score(selected.fit_type, other.fit_type)
    scores.append(ft_s)
    if ft_s >= 0.85:
        parts.append("balanced fit")

    if not _gender_ok(selected.target_gender, other.target_gender):
        return 20, "Different target gender — likely a mismatch."

    base = sum(scores) / len(scores)
    # Slight boost when the other item is a natural category partner.
    partner_cats = _MATCHING_CATEGORIES.get(_normalise(selected.category), [])
    if _normalise(other.category) in partner_cats:
        base = min(1.0, base + 0.05)

    score = int(round(base * 100))
    reason = "; ".join(parts[:3]) if parts else "Versatile pairing."
    return score, reason


# ── Generated (non-owned) suggestions ──

def _generated_suggestions(
    selected: ClothingItem, target_category: str, owned_ids: set[int], count: int = 5
) -> list[StyleMatchItem]:
    """Build concrete, named suggestions for a category with reasons + scores.

    Uses the selected item's attributes (color, occasion, season) to generate
    plausible, fashion-correct items. These are NOT wardrobe items — they are
    purchase suggestions, so owned=False.
    """
    sel_color = _normalise(selected.color)
    sel_hsl = _hsl_for_color(selected.color)
    sel_occ = _normalise(selected.occasion_tag) or "casual"

    # Pick a complementary/neutral color to recommend for the new item.
    if sel_hsl is not None and not _is_neutral_hsl(sel_hsl, selected.color):
        rec_color = _nearest_named_color((_complementary(sel_hsl[0]), 45.0, 55.0))
    else:
        # Neutral selected item (white/black/beige/...) → recommend a safe
        # complementary neutral rather than a vivid hue.
        rec_color = "navy" if _normalise(selected.color) in ("white", "beige", "cream", "ivory") else "beige"

    # Base names per (target_category, selected_category) using the style rules.
    names = _suggested_names(selected, target_category, rec_color)
    items: list[StyleMatchItem] = []
    for name in names[:count]:
        # Score the generated item as if it had the recommended color.
        col_s, col_r = _color_compat_score(selected.color, rec_color)
        season_s = _season_score(selected.season, selected.season)
        occ_s = 0.9 if sel_occ else 0.5
        score = int(round(((col_s * 0.6) + (season_s * 0.2) + (occ_s * 0.2)) * 100))
        reason = f"{col_r} Pairs with your {selected.name or selected.category}."
        items.append(
            StyleMatchItem(
                name=name,
                match_percentage=max(55, min(96, score)),
                reason=reason,
                owned=False,
                category=target_category,
                color=rec_color,
            )
        )
    return items


def _suggested_names(selected: ClothingItem, target: str, rec_color: str) -> list[str]:
    sc = _normalise(selected.category)
    cap = rec_color.capitalize() if rec_color else ""
    suggestions: list[str] = []

    if target == "bottom":
        if sc in ("top", "shirt", "tshirt", "sweater", "hoodie", "kurti"):
            suggestions = [
                f"{cap} Trousers",
                "Blue Straight Jeans",
                "Black Wide Leg Pants",
                "Olive Cargo Pants",
                "Denim Shorts",
            ]
    elif target == "top":
        if sc in ("bottom", "jeans", "trousers", "pants", "shorts", "leggings"):
            suggestions = [
                "White Shirt",
                "Black T-Shirt",
                "Grey Hoodie",
                "Olive Shirt",
                f"{cap} Sweater",
            ]
    elif target == "footwear":
        suggestions = [
            "White Sneakers",
            "Black Loafers",
            "Brown Boots",
            "White Canvas Shoes",
            "Chelsea Boots",
        ]
    elif target == "accessory":
        suggestions = [
            "Silver Watch",
            "Black Belt",
            "Minimal Chain",
            "Sunglasses",
            "Tote Bag",
        ]
    elif target == "outerwear":
        suggestions = [
            "Denim Jacket",
            "Black Blazer",
            f"{cap} Overshirt",
            "Beige Cardigan",
        ]
    return suggestions or [f"{cap} {target}"]


# ── Color recommendations / avoid ──

def _recommend_avoid_colors(selected: ClothingItem) -> tuple[list[str], list[str]]:
    hsl = _hsl_for_color(selected.color)
    if hsl is None:
        return ["beige", "navy blue", "black", "olive green", "grey"], ["neon green", "bright orange"]

    rec: list[str] = []
    if _is_neutral_hsl(hsl, selected.color):
        # Neutrals pair with everything — recommend timeless neutrals.
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

    # Avoid: clashing fashion pairs + own hue's weak neighbors.
    clashes: list[str] = []
    na = _normalise(selected.color)
    for pair in _FASHION_CLASHES:
        if na in pair:
            other = (pair - {na}).pop()
            clashes.append(other)
    avoid = clashes + ["neon green", "bright orange"]
    # de-dup preserving order
    seen = set()
    avoid = [c for c in avoid if not (c in seen or seen.add(c))]
    return rec, avoid[:5]


def _occasion_ideas(selected: ClothingItem) -> list[dict]:
    sel_occ = _normalise(selected.occasion_tag) or "casual"
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
        {"name": idea, "based_on": selected.name or selected.category}
        for idea in ideas
    ]


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


# ── Main entry ──

def generate_style_match(item_id: int, db: Session) -> StyleMatchResult:
    selected = db.query(ClothingItem).filter(ClothingItem.id == item_id).first()
    if not selected:
        raise ValueError(f"Item {item_id} not found")

    user_id = selected.user_id
    all_items = (
        db.query(ClothingItem).filter(ClothingItem.user_id == user_id).all()
    )
    owned_ids = {it.id for it in all_items}

    partner_cats = _MATCHING_CATEGORIES.get(_normalise(selected.category), [])

    section_map: dict[str, list[StyleMatchItem]] = {
        "top": [], "bottom": [], "footwear": [], "accessory": [], "outerwear": [],
    }

    # 1) Wardrobe matches (owned items in partner categories), scored.
    wardrobe_matches: list[StyleMatchItem] = []
    for it in all_items:
        if it.id == selected.id:
            continue
        if _normalise(it.category) not in partner_cats:
            continue
        score, reason = _compatibility(selected, it)
        wardrobe_matches.append(
            StyleMatchItem(
                name=it.name or f"{it.category}",
                match_percentage=score,
                reason=reason,
                owned=True,
                item_id=it.id,
                category=it.category,
                color=it.color,
                image_url=it.image_url,
            )
        )
    wardrobe_matches.sort(key=lambda x: x.match_percentage, reverse=True)

    # 2) Generated suggestions per partner category (not owned).
    for cat in partner_cats:
        generated = _generated_suggestions(selected, cat, owned_ids)
        section_map[cat].extend(generated)

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

    # 4) Shopping suggestions: one group per partner category's top pick.
    for cat in partner_cats:
        picks = section_map.get(cat, [])
        if not picks:
            continue
        top = picks[0]
        result.shopping_suggestions.append(
            {
                "category": cat,
                "item_name": top.name,
                "match_percentage": top.match_percentage,
                "reason": top.reason,
                "owned": False,
                "shopping_links": _build_shop_links(top.name),
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
