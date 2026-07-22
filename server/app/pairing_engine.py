from __future__ import annotations

import json
import logging
import os
from collections import Counter
from dataclasses import dataclass, field

import httpx
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from app.models import ClothingItem
from app.style_embeddings import cosine_similarity

from app.config import get_style_boost, get_body_type_rules

# ── Color definitions: HSL_MAP ──

HSL_MAP: dict[str, tuple[float, float, float]] = {
    # Neutrals
    "black": (0, 0, 0),
    "white": (0, 0, 100),
    "grey": (0, 0, 50),
    "gray": (0, 0, 50),
    "beige": (40, 40, 80),
    "cream": (45, 50, 90),
    "ivory": (60, 30, 95),
    "khaki": (55, 40, 70),
    "tan": (30, 40, 70),
    # Reds
    "red": (0, 80, 50),
    "burgundy": (345, 60, 30),
    "maroon": (0, 60, 30),
    "crimson": (348, 80, 45),
    "wine": (340, 50, 35),
    "cherry": (0, 70, 45),
    # Blues
    "blue": (220, 70, 55),
    "navy": (220, 50, 30),
    "sky blue": (200, 60, 75),
    "royal blue": (220, 70, 50),
    "turquoise": (175, 65, 55),
    "teal": (170, 50, 40),
    "cyan": (180, 70, 65),
    # Greens
    "green": (120, 60, 45),
    "olive": (80, 40, 45),
    "sage": (150, 25, 60),
    "emerald": (140, 65, 45),
    "mint": (150, 50, 75),
    "forest green": (140, 55, 35),
    "lime": (80, 65, 55),
    # Yellows
    "yellow": (55, 80, 55),
    "gold": (45, 70, 50),
    "mustard": (45, 65, 45),
    "amber": (40, 75, 50),
    # Oranges
    "orange": (25, 75, 55),
    "rust": (15, 60, 40),
    "peach": (25, 55, 80),
    "coral": (10, 65, 65),
    # Purples
    "purple": (280, 55, 50),
    "violet": (270, 60, 55),
    "lavender": (270, 35, 80),
    "plum": (300, 40, 40),
    "mauve": (300, 30, 70),
    # Pinks
    "pink": (340, 60, 75),
    "magenta": (300, 80, 50),
    "fuchsia": (290, 75, 55),
    "rose": (340, 55, 65),
    "hot pink": (330, 80, 60),
    # Browns
    "brown": (25, 45, 35),
    "camel": (30, 45, 60),
    "copper": (15, 50, 45),
    "chocolate": (15, 55, 35),
}

KNOWN_NEUTRAL_NAMES: set[str] = {
    "black", "white", "beige", "grey", "gray", "cream",
    "ivory", "khaki", "tan", "navy", "sage", "mauve",
}

# Fashion-specific clashing pairs — these look bad together despite
# color theory saying they're complementary or analogous.
_FASHION_CLASHES: set[frozenset[str]] = {
    frozenset(("lime", "purple")),
    frozenset(("red", "green")),
    frozenset(("orange", "hot pink")),
    frozenset(("coral", "brown")),
    frozenset(("maroon", "teal")),
    frozenset(("lavender", "mustard")),
    frozenset(("fuchsia", "rust")),
}

# ── Fabric compatibility ──

_FABRIC_CLASHES: set[frozenset[str]] = {
    frozenset(("silk", "denim")),
    frozenset(("silk", "wool")),
    frozenset(("leather", "linen")),
    frozenset(("silk", "synthetic")),
    frozenset(("knit", "leather")),
}

_FABRIC_AFFINITY: set[frozenset[str]] = {
    frozenset(("cotton", "denim")),
    frozenset(("cotton", "linen")),
    frozenset(("wool", "leather")),
    frozenset(("silk", "knit")),
    frozenset(("cotton", "knit")),
    frozenset(("denim", "leather")),
}

# ── Fit contrast scores (top_fit, bottom_fit) → score ──

_FIT_CONTRAST: dict[tuple[str, str], float] = {
    ("slim", "oversized"):   0.90,
    ("slim", "loose"):       0.85,
    ("oversized", "slim"):   0.90,
    ("loose", "slim"):       0.85,
    ("regular", "oversized"): 0.80,
    ("regular", "loose"):    0.70,
    ("slim", "regular"):     0.65,
    ("oversized", "loose"):  0.30,
    ("loose", "oversized"):  0.30,
}

# ── Sleeve layering bonus pairs ──

_SLEEVE_LAYERING_BONUS: set[tuple[str, str]] = {
    ("sleeveless", "long"),
    ("short", "long"),
    ("sleeveless", "three_quarter"),
}

# ── Blended scoring weights ──
COLOR_WEIGHT = 0.35
EMBEDDING_WEIGHT = 0.25
HARD_RULE_WEIGHT = 0.15
FABRIC_WEIGHT = 0.10
FIT_WEIGHT = 0.08
SEASON_WEIGHT = 0.07

# ── Body-type style-tag scoring weight ──
STYLE_TAG_WEIGHT = 0.07

# ── Optional learned-compatibility override (Step 6) ──
USE_LEARNED_COMPATIBILITY = os.environ.get("USE_LEARNED_COMPATIBILITY", "false").lower() == "true"

# Weights when learned compatibility is active
LEARNED_WEIGHT = 0.40
LEARNED_COLOR_WEIGHT = 0.30
LEARNED_EMBEDDING_WEIGHT = 0.20
LEARNED_HARD_RULE_WEIGHT = 0.10

# Cache body-type rules at module load so we never re-read the file per request.
_BODY_TYPE_RULES = get_body_type_rules()


def _normalise(color: str | None) -> str:
    if not color:
        return ""
    return color.strip().lower()


def _color_to_hsl(color: str | None) -> tuple[float, float, float] | None:
    """Convert a color name to (H, S, L) via HSL_MAP lookup."""
    c = _normalise(color)
    if not c:
        return None
    if c in HSL_MAP:
        return HSL_MAP[c]
    for key in HSL_MAP:
        if key in c or c in key:
            return HSL_MAP[key]
    return None


def _is_neutral_hsl(hsl: tuple[float, float, float], name: str = "") -> bool:
    """Determine if a color is neutral based on HSL values or known name."""
    h, s, l = hsl
    if _normalise(name) in KNOWN_NEUTRAL_NAMES:
        return True
    if s < 15:
        return True
    if l < 10 or l > 90:
        return True
    return False


# ── Wardrobe gap detection (deterministic, no AI) ──

# Core categories every versatile wardrobe should have in multiples.
CORE_CATEGORIES = ("top", "bottom", "footwear")
# Minimum number of items required in a core category before it's "covered".
MIN_CORE_ITEMS = 2


@dataclass
class Gap:
    missing_category: str
    reason: str
    existing_items_to_pair_with: list[int] = field(default_factory=list)


def find_gaps(user_id: int, db: Session) -> list[Gap]:
    """Count what a user's wardrobe is missing using pure aggregation.

    Flags a gap when:
      * a core category (top, bottom, footwear) has fewer than 2 items, or
      * a category exists but has zero neutral-colored items.

    No AI call — this is deterministic counting over the wardrobe the user
    already provided.
    """
    items = db.query(ClothingItem).filter(ClothingItem.user_id == user_id).all()

    by_category: Counter = Counter()
    neutral_by_category: Counter = Counter()
    ids_by_category: dict[str, list[int]] = {}

    for item in items:
        cat = _normalise(item.category)
        if not cat:
            continue
        by_category[cat] += 1
        ids_by_category.setdefault(cat, []).append(item.id)

        hsl = _color_to_hsl(item.color)
        if hsl is not None and _is_neutral_hsl(hsl, item.color or ""):
            neutral_by_category[cat] += 1

    gaps: list[Gap] = []

    # Rule 1: core categories with too few items.
    for cat in CORE_CATEGORIES:
        count = by_category.get(cat, 0)
        if count < MIN_CORE_ITEMS:
            # Suggest pairing with whatever else the user already owns.
            existing = [
                iid
                for other_cat in ids_by_category
                if other_cat != cat
                for iid in ids_by_category[other_cat]
            ]
            gaps.append(
                Gap(
                    missing_category=cat,
                    reason=(
                        f"Only {count} {cat}(s) — add at least "
                        f"{MIN_CORE_ITEMS - count} more for versatile outfits."
                    ),
                    existing_items_to_pair_with=existing,
                )
            )

    # Rule 2: categories that exist but lack any neutral-colored item.
    for cat, count in by_category.items():
        if count > 0 and neutral_by_category.get(cat, 0) == 0:
            gaps.append(
                Gap(
                    missing_category=cat,
                    reason=(
                        f"Your {cat}(s) are all non-neutral — add a neutral "
                        f"piece to anchor outfits."
                    ),
                    existing_items_to_pair_with=list(ids_by_category[cat]),
                )
            )

    return gaps


# ── Gap → shopping search query (deterministic, optional AI polish) ──

# Opt-in flag: when enabled, the deterministic query is rephrased by the
# Gemini free-tier text path for a more natural phrasing. OFF by default —
# the deterministic query already works on its own, no external API needed.
AI_QUERY_POLISH = os.environ.get("AI_QUERY_POLISH", "false").lower() == "true"

_NEUTRAL_REASON_HINT = "all non-neutral"


def _existing_colors(db: Session, item_ids: list[int]) -> list[str]:
    if not item_ids:
        return []
    rows = db.query(ClothingItem).filter(ClothingItem.id.in_(item_ids)).all()
    return [i.color for i in rows if i.color]


def _nearest_named_color(hsl: tuple[float, float, float]) -> str | None:
    """Map an (H, S, L) triple to the closest named color in HSL_MAP."""
    h, s, l = hsl
    best: str | None = None
    best_d = float("inf")
    for name, (hh, ss, ll) in HSL_MAP.items():
        # circular hue distance, weighted saturation/lightness diffs
        dh = _hue_diff(h, hh) / 180.0
        ds = abs(s - ss) / 100.0
        dl = abs(l - ll) / 100.0
        d = dh * 0.5 + ds * 0.25 + dl * 0.25
        if d < best_d:
            best_d = d
            best = name
    return best


def _pick_color_for_gap(db: Session, gap: Gap) -> str:
    """Pick a color for the missing item from the user's existing items.

    - If the gap is a "lacks neutral" gap, prefer a neutral family.
    - Otherwise pick a complementary hue to the user's existing item colors
      (hue + 180°), mapped back to a named color, falling back to a neutral.
    """
    existing = _existing_colors(db, gap.existing_items_to_pair_with)
    hues = []
    for c in existing:
        hsl = _color_to_hsl(c)
        if hsl is not None:
            hues.append(hsl)

    neutral_needed = _NEUTRAL_REASON_HINT in gap.reason.lower()
    neutral_families = ["black", "white", "beige", "grey", "navy", "cream"]

    if neutral_needed:
        # Choose a neutral the user doesn't already own in this category.
        owned = {_normalise(c) for c in existing}
        for nf in neutral_families:
            if nf not in owned:
                return nf
        return "beige"

    if hues:
        avg_h = sum(h[0] for h in hues) / len(hues)
        comp_hsl = ((avg_h + 180) % 360, 55.0, 50.0)
        name = _nearest_named_color(comp_hsl)
        if name:
            return name

    # Fallback: a versatile neutral anchor.
    return "beige"


def _build_deterministic_query(
    gap: Gap, db: Session, target_gender: str | None, occasion_tag: str | None
) -> str:
    color = _pick_color_for_gap(db, gap)
    category = gap.missing_category or "clothing"
    parts = [color, category]
    if target_gender:
        parts.append(_normalise(target_gender))
    if occasion_tag:
        parts.append(_normalise(occasion_tag))
    return " ".join(parts)


def _polish_query_with_gemini(query: str) -> str:
    """Rephrase a deterministic query via the Gemini free-tier text path.

    Strictly optional — only called when AI_QUERY_POLISH is enabled. Returns
    the original query untouched if the API is unavailable or fails.
    """
    try:
        from app.routers.tagging import GEMINI_API_KEY, GEMINI_API_URL, GEMINI_MODEL
    except Exception:
        return query

    if not GEMINI_API_KEY:
        return query

    api_url = GEMINI_API_URL.replace("{model}", GEMINI_MODEL)
    prompt = (
        "Rephrase this product search query into a single concise, natural "
        f"shopping search string (max 6 words, no punctuation): {query}"
    )
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.3, "maxOutputTokens": 32},
    }
    headers = {
        "x-goog-api-key": GEMINI_API_KEY,
        "Content-Type": "application/json",
    }
    try:
        with httpx.Client(timeout=15.0) as client:
            resp = client.post(api_url, json=payload, headers=headers)
            resp.raise_for_status()
            text = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
        polished = text.strip().strip('"').strip()
        return polished or query
    except Exception as exc:
        logger.warning("AI_QUERY_POLISH failed, using deterministic query: %s", exc)
        return query


def build_search_query(
    gap: Gap,
    db: Session,
    target_gender: str | None = None,
    occasion_tag: str | None = None,
    polish: bool | None = None,
) -> str:
    """Build a plain shopping search string from gap data — no AI call.

    Combines a color chosen from the user's existing items (complementary or
    neutral via the color-harmony module), the missing category, the user's
    target gender, and the occasion into one query string, e.g.
    "beige wide leg trousers women casual".

    If ``polish`` (or the AI_QUERY_POLISH env flag) is enabled, the
    deterministic query is optionally rephrased by Gemini — but the base
    deterministic query is always produced first and used as the fallback.
    """
    query = _build_deterministic_query(gap, db, target_gender, occasion_tag)
    use_polish = AI_QUERY_POLISH if polish is None else polish
    if use_polish:
        return _polish_query_with_gemini(query)
    return query


def _hue_diff(h1: float, h2: float) -> float:
    """Shortest circular distance between two hues (0-180)."""
    d = abs(h1 - h2)
    return min(d, 360 - d)


def _pattern_is_busy(pattern: str | None) -> bool:
    p = _normalise(pattern)
    return p in {"printed", "floral", "striped", "checked", "plaid", "polka dot"}


def _fabric_score(fabric1: str | None, fabric2: str | None) -> float:
    if not fabric1 or not fabric2:
        return 0.5
    pair = frozenset({_normalise(fabric1), _normalise(fabric2)})
    if pair in _FABRIC_AFFINITY:
        return 0.9
    if pair in _FABRIC_CLASHES:
        return 0.2
    return 0.5


def _fit_contrast_score(fit1: str | None, fit2: str | None) -> float:
    if not fit1 or not fit2:
        return 0.5
    key = (_normalise(fit1), _normalise(fit2))
    return _FIT_CONTRAST.get(key, 0.5)


def _season_compatible(season1: str | None, season2: str | None) -> float:
    s1 = _normalise(season1)
    s2 = _normalise(season2)
    if not s1 or not s2:
        return 0.5
    if s1 == s2:
        return 0.9
    if "all-season" in (s1, s2):
        return 0.85
    return 0.3


# ── Body-type style-tag scoring ──


def _parse_style_tags(raw: str | None) -> list[str]:
    """Parse a JSON-serialized list of style tags from a Text column."""
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return [str(t).strip().lower() for t in parsed if t]
    except (json.JSONDecodeError, TypeError):
        pass
    return []


def _body_type_style_score(
    item: ClothingItem,
    user_body_type: str | None,
) -> float:
    """Score 0–1 reflecting how well an item's style tags match the
    user's body-type rules from the YAML config.

    Returns 0.5 (neutral) when body type is unknown or the item
    has no style tags.
    """
    if not user_body_type:
        return 0.5

    tags = _parse_style_tags(getattr(item, "style_tags", None))
    if not tags:
        return 0.5

    total_boost = 0.0
    for tag in tags:
        total_boost += get_style_boost(user_body_type, tag)

    # Clamp to [0, 1]
    return min(max(total_boost, 0.0), 1.0)


# ── Embedding & hard-rule helpers ──


def _load_embedding(item: ClothingItem) -> list[float] | None:
    """Load the FashionCLIP embedding from an item's embedding_json field."""
    raw = getattr(item, "embedding_json", None)
    if not raw:
        return None
    try:
        vec = json.loads(raw)
        if isinstance(vec, list) and len(vec) > 0:
            return vec
    except (json.JSONDecodeError, TypeError):
        pass
    return None


def _embedding_similarity(item1: ClothingItem, item2: ClothingItem) -> float:
    """Cosine similarity between two items' embeddings, normalised to [0, 1].

    Returns 0.5 (neutral) if either item has no embedding.
    """
    e1 = _load_embedding(item1)
    e2 = _load_embedding(item2)
    if e1 is None or e2 is None:
        return 0.5
    sim = cosine_similarity(e1, e2)
    return (sim + 1.0) / 2.0


def _gender_compatible(item1: ClothingItem, item2: ClothingItem) -> bool:
    """Hard filter: items must share target_gender or at least one must be unisex."""
    g1 = _normalise(getattr(item1, "target_gender", None)) or "unisex"
    g2 = _normalise(getattr(item2, "target_gender", None)) or "unisex"
    if g1 == "unisex" or g2 == "unisex":
        return True
    return g1 == g2


def _hard_rule_score(item1: ClothingItem, item2: ClothingItem) -> float:
    """Soft score [0, 1] from occasion and formality matching.

    Uses the numeric formality_score (1-5) for a more nuanced comparison
    than the old string-based formality field.
    Returns 0.5 when neither field is available on both items.
    """
    total = 0.0
    count = 0

    o1 = getattr(item1, "occasion_tag", None)
    o2 = getattr(item2, "occasion_tag", None)
    if o1 and o2:
        o1_tags = [t.strip().lower() for t in o1.split(",")]
        o2_tags = [t.strip().lower() for t in o2.split(",")]
        total += 1.0 if any(t in o2_tags for t in o1_tags) else 0.0
        count += 1

    fs1 = getattr(item1, "formality_score", None)
    fs2 = getattr(item2, "formality_score", None)
    if fs1 is not None and fs2 is not None:
        diff = abs(fs1 - fs2)
        if diff == 0:
            total += 1.0
        elif diff == 1:
            total += 0.7
        elif diff == 2:
            total += 0.3
        else:
            total += 0.0
        count += 1

    return total / count if count > 0 else 0.5


# ── Pair scoring ──

def score_pair_color(c1: str | None, c2: str | None) -> float:
    """Score 0–1 for how well two colors pair together using HSL color theory."""
    if not c1 or not c2:
        return 0.5

    hsl1 = _color_to_hsl(c1)
    hsl2 = _color_to_hsl(c2)

    if hsl1 is None or hsl2 is None:
        return 0.5

    if _is_neutral_hsl(hsl1, c1) or _is_neutral_hsl(hsl2, c2):
        return 0.9

    # Fashion-specific clashing override
    pair_key = frozenset({_normalise(c1), _normalise(c2)})
    if pair_key in _FASHION_CLASHES:
        return 0.25

    diff = _hue_diff(hsl1[0], hsl2[0])
    s1, s2 = hsl1[1], hsl2[1]

    if diff < 15:
        return 0.85
    if 150 <= diff <= 210:
        return 0.80
    if 15 <= diff < 60:
        return 0.70
    if (60 <= diff < 150) or (210 < diff <= 300):
        if s1 < 20 or s2 < 20:
            return 0.45
        return 0.30
    return 0.55


def score_pair(
    item1: ClothingItem, item2: ClothingItem,
    user_body_type: str | None = None,
) -> tuple[float, str, dict[str, float]]:
    """Blended compatibility score for a pair of items.

    Combines color harmony, embedding similarity, hard-rule matching,
    fabric affinity, fit contrast, season compatibility, and
    body-type style-tag alignment.

    Returns (score, reason, breakdown).
    Score is 0.0 when target_gender is incompatible.
    """
    if not _gender_compatible(item1, item2):
        return 0.0, "target_gender mismatch", {}

    color_score = score_pair_color(item1.color, item2.color)
    embed_score = _embedding_similarity(item1, item2)
    hard_score = _hard_rule_score(item1, item2)
    fabric_score = _fabric_score(item1.fabric_type, item2.fabric_type)
    fit_score = _fit_contrast_score(item1.fit_type, item2.fit_type)
    season_score = _season_compatible(item1.season, item2.season)
    style_score = (
        _body_type_style_score(item1, user_body_type)
        + _body_type_style_score(item2, user_body_type)
    ) / 2.0

    final = (
        COLOR_WEIGHT * color_score
        + EMBEDDING_WEIGHT * embed_score
        + HARD_RULE_WEIGHT * hard_score
        + FABRIC_WEIGHT * fabric_score
        + FIT_WEIGHT * fit_score
        + SEASON_WEIGHT * season_score
        + STYLE_TAG_WEIGHT * style_score
    )

    reasons = []
    if color_score >= 0.8:
        reasons.append("great colors")
    elif color_score <= 0.4:
        reasons.append("clashing colors")
    if embed_score > 0.7:
        reasons.append("matching style")
    if hard_score >= 0.8:
        reasons.append("occasion match")
    if fabric_score >= 0.8:
        reasons.append("complementary fabrics")
    elif fabric_score <= 0.3:
        reasons.append("clashing fabrics")
    if fit_score >= 0.8:
        reasons.append("balanced silhouette")
    elif fit_score <= 0.4:
        reasons.append("unbalanced fit")
    if season_score >= 0.8:
        reasons.append("season match")
    elif season_score <= 0.4:
        reasons.append("season mismatch")
    if style_score >= 0.7:
        reasons.append("flattering for body type")

    reason = "; ".join(reasons) if reasons else "mixed compatibility"
    breakdown = {
        "color": round(color_score, 3),
        "embedding": round(embed_score, 3),
        "hard_rules": round(hard_score, 3),
        "fabric": round(fabric_score, 3),
        "fit": round(fit_score, 3),
        "season": round(season_score, 3),
        "style_tag": round(style_score, 3),
    }
    return round(final, 3), reason, breakdown


def _outfit_hues(colors: list[str]) -> list[tuple[float, float, float]]:
    """Return list of HSL tuples for valid colors in an outfit."""
    return [hsl for hsl in (_color_to_hsl(c) for c in colors) if hsl is not None]


def _has_complementary_pair(hues: list[tuple[float, float, float]]) -> str | None:
    """Check if any pair of hues is in the complementary range (150-210°)."""
    for i in range(len(hues)):
        for j in range(i + 1, len(hues)):
            if 150 <= _hue_diff(hues[i][0], hues[j][0]) <= 210:
                return f"hue {hues[i][0]:.0f}° + {hues[j][0]:.0f}° are complementary"
    return None


def _is_analogous(hues: list[tuple[float, float, float]]) -> str | None:
    """Check if all hues fall within 45° of each other (analogous palette)."""
    if len(hues) < 2:
        return None
    hue_vals = [h[0] for h in hues]
    max_diff = max(_hue_diff(h1, h2) for h1 in hue_vals for h2 in hue_vals)
    if max_diff <= 45:
        return f"analogous palette (max hue spread {max_diff:.0f}°)"
    return None


def score_outfit(
    items: list[ClothingItem],
    user_body_type: str | None = None,
) -> tuple[float, str, dict[str, float]]:
    """Score an outfit (list of 2-3 items) and return (score, reason, breakdown)."""
    if not items:
        return 0.0, "Empty outfit", {}

    colors = [i.color for i in items]
    patterns = [i.pattern for i in items]

    # Aggregate breakdown across all pairs
    pair_scores = []
    breakdown_sums: dict[str, float] = {}
    pair_count = 0
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            ps, _, bd = score_pair(items[i], items[j], user_body_type)
            pair_scores.append(ps)
            for k, v in bd.items():
                breakdown_sums[k] = breakdown_sums.get(k, 0.0) + v
            pair_count += 1

    base = sum(pair_scores) / len(pair_scores) if pair_scores else 0.5

    # Penalty for multiple busy patterns
    busy_count = sum(1 for p in patterns if _pattern_is_busy(p))
    if busy_count >= 2:
        base *= 0.5

    # HSL-based bonuses
    hues = _outfit_hues(colors)

    comp_bonus = 0.0
    comp_reason = ""
    comp_msg = _has_complementary_pair(hues)
    if comp_msg:
        comp_bonus = 0.10
        comp_reason = comp_msg

    analogous_bonus = 0.0
    analogous_reason = ""
    ana_msg = _is_analogous(hues)
    if ana_msg:
        analogous_bonus = 0.12
        analogous_reason = ana_msg

    final = min(base + comp_bonus + analogous_bonus, 1.0)

    # Average breakdown
    avg_breakdown = {k: round(v / pair_count, 3) for k, v in breakdown_sums.items()} if pair_count else {}

    # Build reason
    reasons = []
    if comp_reason:
        reasons.append(comp_reason)
    if analogous_reason:
        reasons.append(analogous_reason)
    if busy_count >= 2:
        reasons.append("multiple busy patterns clash")
    if all(
        _is_neutral_hsl(hsl, c)
        for c, hsl in zip(colors, hues)
        if hsl is not None
    ):
        reasons.append("all-neutral palette")

    reason = "; ".join(reasons) if reasons else "solid color pairing"
    return round(final, 3), reason, avg_breakdown


# ── Body-type outfit-level boost (Step 2.3) ──


def _outfit_body_type_boost(
    items: list[ClothingItem],
    user_body_type: str | None,
) -> tuple[float, list[str]]:
    """Sum matching style-tag boosts for an outfit, capped at +0.2."""
    if not user_body_type:
        return 0.0, []

    bt = user_body_type.strip().lower()
    rules = _BODY_TYPE_RULES.model_dump().get(bt, [])
    tag_boosts = {r["tag"]: r["boost"] for r in rules}

    total = 0.0
    fired = []
    for item in items:
        tags = _parse_style_tags(getattr(item, "style_tags", None))
        for tag in tags:
            if tag in tag_boosts:
                total += tag_boosts[tag]
                fired.append(f"{bt}:{tag}+{tag_boosts[tag]}")

    return min(total, 0.2), fired


def _apply_body_type_boost(
    score: float,
    combo: list[ClothingItem],
    user_body_type: str | None,
) -> float:
    body_boost, fired = _outfit_body_type_boost(combo, user_body_type)
    if fired:
        logger.debug(
            "Body-type rules fired for outfit %s: %s",
            [i.id for i in combo],
            fired,
        )
    return min(score + body_boost, 1.0)


# ── Main suggestion function ──

@dataclass
class OutfitSuggestion:
    items: list[dict]
    score: float
    reason: str
    breakdown: dict[str, float] = None

    def __post_init__(self):
        if self.breakdown is None:
            self.breakdown = {}


def _recommender_ml_weight(feedback_count: int) -> float:
    """Adaptive LightFM blend weight.

    Returns 0.0 for users with fewer than 10 feedback entries (rely entirely
    on the rule-based + FashionCLIP scoring), then ramps linearly up to a cap
    of 0.30 as more feedback is collected.
    """
    if feedback_count < 10:
        return 0.0
    ramp = (feedback_count - 10) / 30.0  # full weight reached at 40 entries
    return min(0.30, max(0.0, 0.30 * ramp))


def suggest_outfits(
    db: Session,
    user_id: int,
    occasion_tag: str | None = None,
    target_gender: str | None = None,
    limit: int = 5,
) -> list[OutfitSuggestion]:
    """Load user's items and return top outfit combinations.

    The final score blends the existing rule-based + FashionCLIP score with a
    learned LightFM recommendation score. The learned weight starts at 0% for
    users with fewer than 10 feedback entries and ramps linearly up to a cap of
    30% as more feedback accumulates. If the model file is missing or fails to
    load, scoring falls back entirely to the rule-based result.
    """
    from app.models import OutfitFeedback, User

    user = db.query(User).filter(User.id == user_id).first()
    user_body_type: str | None = getattr(user, "body_type", None) if user else None

    feedback_count = (
        db.query(OutfitFeedback).filter(OutfitFeedback.user_id == user_id).count()
    )
    ml_weight = _recommender_ml_weight(feedback_count)
    ml_available = False
    if ml_weight > 0.0:
        try:
            from app.recommender import get_recommendation_score

            ml_available = True
        except Exception:  # pragma: no cover - defensive
            ml_available = False

    query = db.query(ClothingItem).filter(ClothingItem.user_id == user_id)
    if occasion_tag:
        query = query.filter(ClothingItem.occasion_tag.contains(occasion_tag))
    if target_gender:
        query = query.filter(ClothingItem.target_gender == target_gender)

    all_items = query.all()

    # Group by category
    by_category: dict[str, list[ClothingItem]] = {}
    for item in all_items:
        by_category.setdefault(item.category, []).append(item)

    tops = by_category.get("top", [])
    bottoms = by_category.get("bottom", [])
    footwear = by_category.get("footwear", [])
    dresses = by_category.get("dress", [])
    outerwear = by_category.get("outerwear", [])
    accessories = by_category.get("accessory", [])

    candidates: list[tuple[float, str, dict[str, float], list[ClothingItem]]] = []

    def _add_candidate(combo, base_score, reason, bd):
        final_score = base_score
        if ml_available:
            try:
                ml_score = get_recommendation_score(
                    user_id, [i.id for i in combo]
                )
                final_score = (1.0 - ml_weight) * base_score + ml_weight * ml_score
                bd = dict(bd)
                bd["recommender_ml"] = round(ml_score, 3)
                bd["ml_weight"] = round(ml_weight, 3)
            except Exception:
                # Fall back to rule-based-only scoring.
                pass
        candidates.append((final_score, reason, bd, combo))

    # Dresses are single-piece: pair with footwear + optional accessory
    for dress in dresses:
        for shoe in footwear or [None]:
            combo = [dress] + ([shoe] if shoe else [])
            score, reason, bd = score_outfit(combo, user_body_type)
            score = _apply_body_type_boost(score, combo, user_body_type)
            _add_candidate(combo, score, reason, bd)

        # Dress + shoes + accessory
        for shoe in footwear or [None]:
            for acc in accessories:
                combo = [dress] + ([shoe] if shoe else []) + [acc]
                s, r, bd = score_outfit(combo, user_body_type)
                s = _apply_body_type_boost(s, combo, user_body_type)
                _add_candidate(combo, s, r, bd)

    # Top + bottom combinations
    for top in tops:
        for bottom in bottoms:
            # With footwear
            for shoe in footwear or [None]:
                combo = [top, bottom] + ([shoe] if shoe else [])
                score, reason, bd = score_outfit(combo, user_body_type)
                score = _apply_body_type_boost(score, combo, user_body_type)
                _add_candidate(combo, score, reason, bd)

                # With outerwear
                for coat in outerwear:
                    full = [top, bottom, coat] + ([shoe] if shoe else [])
                    s, r, bd = score_outfit(full, user_body_type)
                    s = _apply_body_type_boost(s, full, user_body_type)
                    _add_candidate(full, s, r, bd)

                # With accessory
                for acc in accessories:
                    full = [top, bottom] + ([shoe] if shoe else []) + [acc]
                    s, r, bd = score_outfit(full, user_body_type)
                    s = _apply_body_type_boost(s, full, user_body_type)
                    _add_candidate(full, s, r, bd)

    # If no tops/bottoms but have outerwear on its own, skip
    # Fallback: only footwear
    if not candidates and footwear:
        for shoe in footwear:
            score, reason, bd = score_outfit([shoe], user_body_type)
            score = _apply_body_type_boost(score, [shoe], user_body_type)
            _add_candidate([shoe], score, reason, bd)

    # Sort by score descending
    candidates.sort(key=lambda x: x[0], reverse=True)

    # Deduplicate by item IDs, with diversity: prefer varied color palettes
    seen = set()
    seen_colors: list[str] = []
    results: list[OutfitSuggestion] = []
    bucket_size = max(limit * 2, 10)

    for score, reason, bd, combo in candidates[:bucket_size]:
        key = tuple(sorted(i.id for i in combo))
        if key in seen:
            continue
        seen.add(key)

        # Diversity: penalise combos whose dominant color we already show too much
        combo_colors = [i.color for i in combo if i.color]
        dominant = combo_colors[0] if combo_colors else ""
        dup_count = sum(1 for c in seen_colors if c == dominant)
        if dup_count >= 2:
            continue

        seen_colors.append(dominant)
        results.append(
            OutfitSuggestion(
                items=[
                    {
                        "id": i.id,
                        "name": i.name,
                        "category": i.category,
                        "color": i.color,
                        "pattern": i.pattern,
                        "fabric_type": i.fabric_type,
                        "fit_type": i.fit_type,
                        "sleeve_length": i.sleeve_length,
                        "image_url": i.image_url,
                        "target_gender": i.target_gender,
                    }
                    for i in combo
                ],
                score=score,
                reason=reason,
                breakdown=bd,
            )
        )
        if len(results) >= limit:
            break

    return results
