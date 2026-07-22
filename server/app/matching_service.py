from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.orm import Session

from app.models import ClothingItem
from app.pairing_engine import HSL_MAP
from app.shopping_links import build_google_shopping_link, build_meesho_search_link

logger = logging.getLogger(__name__)


# ── Helpers ──

def _hex_to_hsl(hex_color: str) -> tuple[float, float, float]:
    hex_color = hex_color.lstrip("#")
    r, g, b = int(hex_color[0:2], 16) / 255.0, int(hex_color[2:4], 16) / 255.0, int(hex_color[4:6], 16) / 255.0
    mx, mn = max(r, g, b), min(r, g, b)
    l = (mx + mn) / 2.0
    if mx == mn:
        return 0.0, 0.0, l
    d = mx - mn
    s = d / (1.0 - abs(2.0 * l - 1.0))
    if mx == r:
        h = ((g - b) / d) % 6.0
    elif mx == g:
        h = (b - r) / d + 2.0
    else:
        h = (r - g) / d + 4.0
    return h * 60.0, s, l


def _is_neutral(hsl: tuple[float, float, float]) -> bool:
    _, s, l = hsl
    if s < 0.15:
        return True
    if l < 0.15:
        return True
    if l > 0.85:
        return True
    h = hsl[0]
    if 210 <= h <= 270 and s < 0.5 and l < 0.45:
        return True
    if 30 <= h <= 60 and s < 0.4 and l > 0.6:
        return True
    return False


def _hue_diff(h1: float, h2: float) -> float:
    d = abs(h1 - h2) % 360
    return min(d, 360 - d)


def _get_item_color_hex(item: ClothingItem) -> str | None:
    if item.color:
        color_lower = item.color.strip().lower()
        known = {
            "black": "#000000", "white": "#FFFFFF", "grey": "#888888",
            "gray": "#888888", "beige": "#F5DEB3", "navy": "#000080",
            "red": "#FF0000", "blue": "#0000FF", "green": "#00FF00",
            "yellow": "#FFFF00", "orange": "#FFA500", "purple": "#800080",
            "pink": "#FFC0CB", "brown": "#A52A2A", "cream": "#FFFDD0",
            "ivory": "#FFFFF0", "tan": "#D2B48C", "maroon": "#800000",
            "teal": "#008080", "olive": "#808000", "coral": "#FF7F50",
            "burgundy": "#800020", "charcoal": "#36454F", "khaki": "#C3B091",
            "mint": "#98FB98", "peach": "#FFDAB9", "lavender": "#E6E6FA",
            "mustard": "#FFDB58", "blush": "#DE5A83", "emerald": "#50C878",
            "crimson": "#DC143C", "indigo": "#4B0082", "turquoise": "#40E0D0",
            "magenta": "#FF00FF", "salmon": "#FA8072", "sky": "#87CEEB",
            "lime": "#00FF00", "wine": "#722F37", "rust": "#B7410E",
            "bronze": "#CD7F32", "silver": "#C0C0C0", "gold": "#FFD700",
            "copper": "#B87333", "nude": "#E3BC9A", "mauve": "#E0B0FF",
            "taupe": "#483C32", "camel": "#C19A6B", "denim": "#1565C0",
        }
        if color_lower in known:
            return known[color_lower]
    return None


_COMPLEMENTARY_CATEGORIES = {
    "top": "bottom",
    "bottom": "top",
    "dress": "footwear",
    "footwear": "top",
    "outerwear": "top",
    "accessory": "top",
}


def get_complementary_category(category: str) -> str | None:
    return _COMPLEMENTARY_CATEGORIES.get(category)


def _nearest_color_name(hex_color: str) -> str:
    hsl = _hex_to_hsl(hex_color)
    h, s, l = hsl
    best = "black"
    best_d = float("inf")
    for name, (hh, ss, ll) in HSL_MAP.items():
        dh = _hue_diff(h, hh) / 180.0
        ds = abs(s - ss / 100.0)
        dl = abs(l - ll / 100.0)
        d = dh * 0.5 + ds * 0.25 + dl * 0.25
        if d < best_d:
            best_d = d
            best = name
    return best


def complete_outfit(item_id: int, db: Session) -> dict:
    source = db.query(ClothingItem).filter(ClothingItem.id == item_id).first()
    if not source:
        return {"error": "Item not found"}

    target_cat = get_complementary_category(source.category)
    if not target_cat:
        return {"error": f"No complementary category for '{source.category}'"}

    source_hex = _get_item_color_hex(source)
    color_name = _nearest_color_name(source_hex) if source_hex else ""

    source_occasions = set()
    if source.occasion_tag:
        source_occasions = {o.strip() for o in source.occasion_tag.split(",")}
    primary_occasion = next(iter(source_occasions)) if source_occasions else ""

    # Wardrobe matches
    wardrobe_candidates = (
        db.query(ClothingItem)
        .filter(
            ClothingItem.user_id == source.user_id,
            ClothingItem.category == target_cat,
            ClothingItem.id != item_id,
        )
        .all()
    )

    scored = []
    for candidate in wardrobe_candidates:
        if source_occasions and candidate.occasion_tag:
            cand_occasions = {o.strip() for o in candidate.occasion_tag.split(",")}
            if not source_occasions & cand_occasions:
                continue
        cand_hex = _get_item_color_hex(candidate)
        if source_hex and cand_hex:
            score = color_harmony_score(source_hex, cand_hex)
        else:
            score = 0.5
        scored.append({
            "id": candidate.id,
            "name": candidate.name,
            "category": candidate.category,
            "color": candidate.color,
            "image_url": candidate.image_url,
            "color_harmony_score": round(score, 2),
        })

    scored.sort(key=lambda x: x["color_harmony_score"], reverse=True)

    # Shop queries
    queries: list[str] = []
    parts = [color_name, primary_occasion, target_cat]
    queries.append(" ".join(p for p in parts if p))

    if source_hex:
        hsl = _hex_to_hsl(source_hex)
        comp_h = (hsl[0] + 180) % 360
        comp_name = "black"
        comp_diff = float("inf")
        for name, (hh, ss, ll) in HSL_MAP.items():
            d = _hue_diff(comp_h, hh)
            if d < comp_diff:
                comp_diff = d
                comp_name = name
        if comp_name != color_name:
            comp_parts = [comp_name, primary_occasion, target_cat]
            queries.append(" ".join(p for p in comp_parts if p))

    if source.pattern:
        pattern_parts = [color_name, source.pattern, target_cat]
        pattern_query = " ".join(p for p in pattern_parts if p)
        if pattern_query not in queries:
            queries.append(pattern_query)

    shop_online = []
    for query in queries:
        shop_online.append({
            "query": query,
            "google_shopping_url": build_google_shopping_link(query),
            "meesho_url": build_meesho_search_link(query),
        })

    return {
        "source_item": {
            "id": source.id,
            "name": source.name,
            "category": source.category,
            "color": source.color,
            "image_url": source.image_url,
        },
        "target_category": target_cat,
        "wardrobe_match_count": len(scored),
        "wardrobe_matches": scored[:10],
        "shop_online": shop_online,
    }


# ── Public API ──

def extract_dominant_color(image_path: str) -> Optional[str]:
    try:
        from colorthief import ColorThief
    except ImportError:
        logger.warning("colorthief not installed — install with: pip install colorthief")
        return None

    try:
        ct = ColorThief(image_path)
        rgb = ct.get_color(quality=1)
        return "#{:02X}{:02X}{:02X}".format(*rgb)
    except Exception as exc:
        logger.warning("extract_dominant_color failed for %s: %s", image_path, exc)
        return None


def color_harmony_score(color_a: str, color_b: str) -> float:
    hsl_a = _hex_to_hsl(color_a)
    hsl_b = _hex_to_hsl(color_b)

    if _is_neutral(hsl_a) or _is_neutral(hsl_b):
        return 0.9

    diff = _hue_diff(hsl_a[0], hsl_b[0])

    if 165 <= diff <= 195:
        return 0.9
    if diff <= 30:
        return 0.8
    return 0.3


def suggest_matches(
    item_id: int,
    target_category: str,
    db: Session,
    limit: int = 10,
) -> dict:
    source = db.query(ClothingItem).filter(ClothingItem.id == item_id).first()
    if not source:
        return {"wardrobe_matches": [], "shop_matches": [], "error": "Source item not found"}

    source_color = _get_item_color_hex(source)

    source_occasions = set()
    if source.occasion_tag:
        source_occasions = {o.strip() for o in source.occasion_tag.split(",")}

    wardrobe_candidates = (
        db.query(ClothingItem)
        .filter(
            ClothingItem.user_id == source.user_id,
            ClothingItem.category == target_category,
            ClothingItem.id != item_id,
        )
        .all()
    )

    scored = []
    for candidate in wardrobe_candidates:
        if source_occasions and candidate.occasion_tag:
            cand_occasions = {o.strip() for o in candidate.occasion_tag.split(",")}
            if not source_occasions & cand_occasions:
                continue

        cand_color = _get_item_color_hex(candidate)
        if source_color and cand_color:
            score = color_harmony_score(source_color, cand_color)
        else:
            score = 0.5

        scored.append({
            "id": candidate.id,
            "name": candidate.name,
            "category": candidate.category,
            "color": candidate.color,
            "pattern": candidate.pattern,
            "image_url": candidate.image_url,
            "color_harmony_score": round(score, 2),
        })

    scored.sort(key=lambda x: x["color_harmony_score"], reverse=True)
    wardrobe_matches = scored[:limit]

    query_parts = [target_category]
    if source.color:
        query_parts.append(source.color)
    if source.pattern:
        query_parts.append(source.pattern)
    query = " ".join(query_parts)

    shop_matches = [
        {"store": "Google Shopping", "url": build_google_shopping_link(query)},
        {"store": "Meesho", "url": build_meesho_search_link(query)},
    ]

    return {
        "wardrobe_matches": wardrobe_matches,
        "shop_matches": shop_matches,
    }
