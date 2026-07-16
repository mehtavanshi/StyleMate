from __future__ import annotations

import itertools
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models import ClothingItem

# ── Color definitions ──

NEUTRAL_COLORS = {"black", "white", "beige", "grey", "gray", "navy", "cream", "khaki", "tan", "ivory"}

COLOR_FAMILIES = {
    "red": {"red", "burgundy", "maroon", "crimson", "wine", "cherry"},
    "blue": {"blue", "navy", "sky blue", "royal blue", "turquoise", "teal", "cyan"},
    "green": {"green", "olive", "sage", "emerald", "mint", "forest green", "lime"},
    "yellow": {"yellow", "gold", "mustard", "amber"},
    "orange": {"orange", "rust", "peach", "coral"},
    "purple": {"purple", "violet", "lavender", "plum", "mauve"},
    "pink": {"pink", "magenta", "fuchsia", "rose", "hot pink"},
    "brown": {"brown", "tan", "khaki", "camel", "copper", "chocolate"},
}

# Color wheel opposites (complementary pairs)
COMPLEMENTARY = {
    "red": "green",
    "green": "red",
    "blue": "orange",
    "orange": "blue",
    "yellow": "purple",
    "purple": "yellow",
    "pink": "green",
    "brown": "blue",
}

# Ideal outfit slots
SLOT_ORDER = ["top", "bottom", "footwear"]
ACCESSORY_SLOT = "accessory"


def _normalise(color: str | None) -> str:
    if not color:
        return ""
    return color.strip().lower()


def _get_family(color: str) -> str | None:
    """Return the color family for a given color name."""
    c = _normalise(color)
    if not c:
        return None
    for family, members in COLOR_FAMILIES.items():
        if c in members or c == family:
            return family
    return c


def _is_neutral(color: str | None) -> bool:
    return _normalise(color) in NEUTRAL_COLORS


def _is_complementary(c1: str | None, c2: str | None) -> bool:
    f1 = _get_family(c1)
    f2 = _get_family(c2)
    if not f1 or not f2:
        return False
    return COMPLEMENTARY.get(f1) == f2


def _same_family(c1: str | None, c2: str | None) -> bool:
    f1 = _get_family(c1)
    f2 = _get_family(c2)
    return bool(f1 and f2 and f1 == f2)


def _is_bright(color: str | None) -> bool:
    c = _normalise(color)
    return c and c not in NEUTRAL_COLORS


def _pattern_is_busy(pattern: str | None) -> bool:
    p = _normalise(pattern)
    return p in {"printed", "floral", "striped", "checked", "plaid", "polka dot"}


# ── Pair scoring ──

def score_pair_color(c1: str | None, c2: str | None) -> float:
    """Score 0–1 for how well two colors pair together."""
    if not c1 or not c2:
        return 0.5

    if _is_neutral(c1) or _is_neutral(c2):
        return 0.9

    if _same_family(c1, c2):
        return 0.8

    if _is_complementary(c1, c2):
        return 0.75

    return 0.4


def score_outfit(items: list[ClothingItem]) -> tuple[float, str]:
    """Score an outfit (list of 2-3 items) and return (score, reason)."""
    if not items:
        return 0.0, "Empty outfit"

    colors = [i.color for i in items]
    patterns = [i.pattern for i in items]

    # Base score from color pairing
    color_scores = []
    for i in range(len(colors)):
        for j in range(i + 1, len(colors)):
            color_scores.append(score_pair_color(colors[i], colors[j]))

    base = sum(color_scores) / len(color_scores) if color_scores else 0.5

    # Penalty for multiple busy patterns
    busy_count = sum(1 for p in patterns if _pattern_is_busy(p))
    if busy_count >= 2:
        base *= 0.5

    # Bonus for complementary
    comp_bonus = 0.0
    comp_reason = ""
    for i in range(len(colors)):
        for j in range(i + 1, len(colors)):
            if _is_complementary(colors[i], colors[j]):
                comp_bonus = 0.15
                comp_reason = f"{_normalise(colors[i])} + {_normalise(colors[j])} are complementary"
                break
        if comp_bonus:
            break

    # Bonus for monochrome
    mono_bonus = 0.0
    mono_reason = ""
    if all(_same_family(colors[0], c) for c in colors[1:] if c):
        mono_bonus = 0.1
        mono_reason = f"monochrome {_get_family(colors[0])} palette"

    final = min(base + comp_bonus + mono_bonus, 1.0)

    # Build reason
    reasons = []
    if comp_reason:
        reasons.append(comp_reason)
    if mono_reason:
        reasons.append(mono_reason)
    if busy_count >= 2:
        reasons.append("multiple busy patterns clash")
    if all(_is_neutral(c) for c in colors if c):
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
