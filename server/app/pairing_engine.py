from __future__ import annotations

import json
import os
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models import ClothingItem
from app.style_embeddings import cosine_similarity

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

# ── Blended scoring weights (tune these to adjust scoring balance) ──
COLOR_WEIGHT = 0.50
EMBEDDING_WEIGHT = 0.35
HARD_RULE_WEIGHT = 0.15

# ── Optional learned-compatibility override (Step 6) ──
USE_LEARNED_COMPATIBILITY = os.environ.get("USE_LEARNED_COMPATIBILITY", "false").lower() == "true"

# Weights when learned compatibility is active
LEARNED_WEIGHT = 0.40
LEARNED_COLOR_WEIGHT = 0.30
LEARNED_EMBEDDING_WEIGHT = 0.20
LEARNED_HARD_RULE_WEIGHT = 0.10


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


def _hue_diff(h1: float, h2: float) -> float:
    """Shortest circular distance between two hues (0-180)."""
    d = abs(h1 - h2)
    return min(d, 360 - d)


def _pattern_is_busy(pattern: str | None) -> bool:
    p = _normalise(pattern)
    return p in {"printed", "floral", "striped", "checked", "plaid", "polka dot"}


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

    Only counts a sub-score when *both* items have the field populated.
    Returns 0.5 when neither field is available on both items.
    """
    total = 0.0
    count = 0

    o1 = _normalise(getattr(item1, "occasion_tag", None))
    o2 = _normalise(getattr(item2, "occasion_tag", None))
    if o1 and o2:
        total += 1.0 if o1 == o2 else 0.0
        count += 1

    f1 = _normalise(getattr(item1, "formality", None))
    f2 = _normalise(getattr(item2, "formality", None))
    if f1 and f2:
        total += 1.0 if f1 == f2 else 0.0
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


def score_pair(item1: ClothingItem, item2: ClothingItem) -> tuple[float, str]:
    """Blended compatibility score for a pair of items.

    Combines color harmony, FashionCLIP embedding similarity, and hard-rule
    matching (occasion, formality, target_gender) using configurable weights.

    When USE_LEARNED_COMPATIBILITY is true and the outfit-transformer model
    is available, blends in a learned compatibility score with alternate weights.

    Returns (score, reason).  Score is 0.0 when target_gender is incompatible.
    """
    if not _gender_compatible(item1, item2):
        return 0.0, "target_gender mismatch"

    color_score = score_pair_color(item1.color, item2.color)
    embed_score = _embedding_similarity(item1, item2)
    hard_score = _hard_rule_score(item1, item2)

    learned_score = None
    if USE_LEARNED_COMPATIBILITY and item1.image_url and item2.image_url:
        from app.learned_compatibility import get_learned_compatibility

        learned_score = get_learned_compatibility([item1.image_url, item2.image_url])

    if learned_score is not None:
        final = (
            LEARNED_WEIGHT * learned_score
            + LEARNED_COLOR_WEIGHT * color_score
            + LEARNED_EMBEDDING_WEIGHT * embed_score
            + LEARNED_HARD_RULE_WEIGHT * hard_score
        )
    else:
        final = (
            COLOR_WEIGHT * color_score
            + EMBEDDING_WEIGHT * embed_score
            + HARD_RULE_WEIGHT * hard_score
        )

    reasons = []
    if learned_score is not None:
        reasons.append(f"learned={learned_score:.2f}")
    if color_score >= 0.8:
        reasons.append("good color harmony")
    elif color_score <= 0.4:
        reasons.append("clashing colors")
    if embed_score > 0.7:
        reasons.append("visually similar style")
    if hard_score >= 0.9:
        reasons.append("occasion+formality match")
    elif hard_score <= 0.1:
        reasons.append("occasion/formality mismatch")

    reason = "; ".join(reasons) if reasons else "mixed compatibility"
    return round(final, 3), reason


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


def score_outfit(items: list[ClothingItem]) -> tuple[float, str]:
    """Score an outfit (list of 2-3 items) and return (score, reason)."""
    if not items:
        return 0.0, "Empty outfit"

    colors = [i.color for i in items]
    patterns = [i.pattern for i in items]

    # Base score from blended pair scoring
    pair_scores = []
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            ps, _ = score_pair(items[i], items[j])
            pair_scores.append(ps)

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
    return round(final, 3), reason


# ── Main suggestion function ──

@dataclass
class OutfitSuggestion:
    items: list[dict]
    score: float
    reason: str


def suggest_outfits(
    db: Session,
    user_id: int,
    occasion_tag: str | None = None,
    target_gender: str | None = None,
    limit: int = 5,
) -> list[OutfitSuggestion]:
    """Load user's items and return top outfit combinations."""
    query = db.query(ClothingItem).filter(ClothingItem.user_id == user_id)
    if occasion_tag:
        query = query.filter(ClothingItem.occasion_tag == occasion_tag)
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

    candidates = []

    # Dresses are single-piece: pair with footwear + optional accessory
    for dress in dresses:
        for shoe in footwear or [None]:
            combo = [dress] + ([shoe] if shoe else [])
            score, reason = score_outfit(combo)
            candidates.append((score, reason, combo))

        # Dress + shoes + accessory
        for shoe in footwear or [None]:
            for acc in accessories:
                combo = [dress] + ([shoe] if shoe else []) + [acc]
                s, r = score_outfit(combo)
                candidates.append((s, r, combo))

    # Top + bottom combinations
    for top in tops:
        for bottom in bottoms:
            # With footwear
            for shoe in footwear or [None]:
                combo = [top, bottom] + ([shoe] if shoe else [])
                score, reason = score_outfit(combo)
                candidates.append((score, reason, combo))

                # With outerwear
                for coat in outerwear:
                    full = [top, bottom, coat] + ([shoe] if shoe else [])
                    s, r = score_outfit(full)
                    candidates.append((s, r, full))

                # With accessory
                for acc in accessories:
                    full = [top, bottom] + ([shoe] if shoe else []) + [acc]
                    s, r = score_outfit(full)
                    candidates.append((s, r, full))

    # If no tops/bottoms but have outerwear on its own, skip
    # Fallback: only footwear
    if not candidates and footwear:
        for shoe in footwear:
            score, reason = score_outfit([shoe])
            candidates.append((score, reason, [shoe]))

    # Sort by score descending
    candidates.sort(key=lambda x: x[0], reverse=True)

    # Deduplicate by item IDs
    seen = set()
    results = []
    for score, reason, combo in candidates:
        key = tuple(sorted(i.id for i in combo))
        if key in seen:
            continue
        seen.add(key)
        results.append(
            OutfitSuggestion(
                items=[
                    {
                        "id": i.id,
                        "name": i.name,
                        "category": i.category,
                        "color": i.color,
                        "pattern": i.pattern,
                        "image_url": i.image_url,
                        "target_gender": i.target_gender,
                    }
                    for i in combo
                ],
                score=score,
                reason=reason,
            )
        )
        if len(results) >= limit:
            break

    return results
