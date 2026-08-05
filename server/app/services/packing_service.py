"""AI packing assistant — trip details → packing list from the user's wardrobe.

Gemini proposes the ideal category/quantity mix for the trip; we then match it
against what the user actually owns and turn the shortfall into shopping
queries. Without Gemini a rule-of-thumb table stands in, so the feature works
offline too.
"""

from __future__ import annotations

import logging
import os
from collections import defaultdict

from sqlalchemy.orm import Session

from app.models import ClothingItem
from app.pairing_engine import score_pair
from app.style_advisor import gemini_json
from app.style_match import _build_shop_links

logger = logging.getLogger(__name__)

PURPOSES = ("leisure", "business", "beach", "wedding", "adventure")

# The request holds a worker for the whole Gemini round-trip. A deterministic
# fallback table already exists, so cap the wait rather than block for a full
# 60s (plus retries) on a slow call.
# ponytail: bounded blocking call, not a queue. If packing throughput ever
# matters, move it to the Celery job + poll pattern app/tasks.py uses for try-on.
GEMINI_TIMEOUT_S = float(os.getenv("PACKING_GEMINI_TIMEOUT_S", "15"))

# Max items we ever suggest packing per category, whatever the trip length.
MAX_PER_CATEGORY = 7

PROMPT = """You are a packing expert. For a {duration}-day trip to
{destination} for {purpose}, list the ideal clothing to pack.

Return ONLY valid JSON with NO markdown:
{{
  "groups": [
    {{"category": "top", "quantity": 4, "note": "breathable, layerable"}},
    {{"category": "bottom", "quantity": 2, "note": "..."}}
  ],
  "weather_note": "one sentence on the expected weather",
  "tips": ["short packing tip", "short packing tip"]
}}

Rules:
- category must be one of: top, bottom, dress, outerwear, footwear, accessory
- quantity is an integer 1-{max_per_category}
- Account for the destination's climate at this time of year
- Keep notes under 10 words"""

# Fallback: per-day ratios, rounded up, capped. Deliberately boring.
_FALLBACK_RATIOS = {
    "top": 1.0,
    "bottom": 0.5,
    "footwear": 0.2,
    "accessory": 0.3,
    "outerwear": 0.15,
}

_PURPOSE_EXTRAS = {
    "beach": {"dress": 0.3},
    "wedding": {"dress": 0.2, "accessory": 0.4},
    "business": {"outerwear": 0.25},
    "adventure": {"footwear": 0.3},
}


def _fallback_groups(duration: int, purpose: str) -> list[dict]:
    ratios = dict(_FALLBACK_RATIOS)
    for cat, ratio in _PURPOSE_EXTRAS.get(purpose, {}).items():
        ratios[cat] = max(ratios.get(cat, 0.0), ratio)

    groups = []
    for category, ratio in ratios.items():
        qty = min(MAX_PER_CATEGORY, max(1, round(duration * ratio)))
        groups.append({"category": category, "quantity": qty, "note": ""})
    return groups


def _clean_groups(raw) -> list[dict] | None:
    """Keep only well-formed group entries; None if nothing survives."""
    if not isinstance(raw, list):
        return None
    valid_categories = {"top", "bottom", "dress", "outerwear", "footwear", "accessory"}
    groups = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        category = str(entry.get("category", "")).strip().lower()
        quantity = entry.get("quantity")
        if category not in valid_categories or not isinstance(quantity, int):
            continue
        groups.append(
            {
                "category": category,
                "quantity": min(MAX_PER_CATEGORY, max(1, quantity)),
                "note": str(entry.get("note") or "")[:60],
            }
        )
    return groups or None


def generate_packing_list(
    destination: str,
    duration: int,
    purpose: str,
    user_id: int,
    db: Session,
) -> dict:
    """Build a packing list: what to take from the wardrobe, what's missing."""
    duration = max(1, min(duration, 60))
    purpose = purpose if purpose in PURPOSES else "leisure"

    parsed = gemini_json(
        PROMPT.format(
            destination=destination,
            duration=duration,
            purpose=purpose,
            max_per_category=MAX_PER_CATEGORY,
        ),
        max_tokens=600,
        temperature=0.3,
        timeout=GEMINI_TIMEOUT_S,
    ) or {}

    groups = _clean_groups(parsed.get("groups")) or _fallback_groups(duration, purpose)
    ai_backed = _clean_groups(parsed.get("groups")) is not None

    items = db.query(ClothingItem).filter(ClothingItem.user_id == user_id).all()
    by_category: dict[str, list[ClothingItem]] = defaultdict(list)
    for item in items:
        by_category[(item.category or "").strip().lower()].append(item)

    # Within a category, pack the pieces that coordinate best with everything
    # else — a packed item that matches nothing is dead weight in a suitcase.
    versatility: dict[int, float] = {}
    for item in items:
        others = [o for o in items if o.id != item.id]
        if not others:
            versatility[item.id] = 0.0
            continue
        versatility[item.id] = sum(score_pair(item, o)[0] for o in others) / len(others)

    selected_items: list[dict] = []
    missing_groups: list[dict] = []

    for group in groups:
        category = group["category"]
        needed = group["quantity"]
        owned = sorted(
            by_category.get(category, []),
            key=lambda i: versatility.get(i.id, 0.0),
            reverse=True,
        )[:needed]

        for item in owned:
            selected_items.append(
                {
                    "id": item.id,
                    "name": item.name,
                    "category": item.category,
                    "color": item.color,
                    "image_url": item.image_url,
                    "note": group["note"],
                }
            )

        shortfall = needed - len(owned)
        if shortfall > 0:
            query = " ".join(
                p for p in (group["note"].split(",")[0].strip(), category) if p
            )
            missing_groups.append(
                {
                    "category": category,
                    "quantity_needed": shortfall,
                    "note": group["note"],
                    "search_query": query,
                    "shopping_links": _build_shop_links(query),
                }
            )

    tips = [str(t)[:120] for t in (parsed.get("tips") or []) if isinstance(t, str)][:4]

    return {
        "destination": destination,
        "duration": duration,
        "purpose": purpose,
        "weather_note": str(parsed.get("weather_note") or "")[:200],
        "tips": tips,
        "groups": groups,
        "selected_items": selected_items,
        "missing_groups": missing_groups,
        "ai_backed": ai_backed,
    }
