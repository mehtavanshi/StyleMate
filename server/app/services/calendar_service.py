"""Wear-frequency tracking off the calendar's locked outfits.

``CalendarEntry.locked_item_ids`` holds every item in the outfit locked for
that date, so a locked entry is the record of "this whole outfit was worn
then". Rows written before that column existed only carry
``locked_outfit_id`` (the primary item) and are read through the same helper.
"""

from __future__ import annotations

import json
import logging
from collections import Counter
from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.models import CalendarEntry, ClothingItem

logger = logging.getLogger(__name__)

# Wear count at which we nudge the user to switch it up.
REPEAT_WARNING_THRESHOLD = 3
DEFAULT_WINDOW_DAYS = 30


def locked_item_ids(entry: CalendarEntry) -> list[int]:
    """Item ids in an entry's locked outfit, oldest storage format included."""
    raw = getattr(entry, "locked_item_ids", None)
    if raw:
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                return [int(i) for i in parsed]
        except (json.JSONDecodeError, TypeError, ValueError):
            logger.warning("calendar entry %s has unreadable locked_item_ids", entry.id)
    if entry.locked_outfit_id is not None:
        return [entry.locked_outfit_id]
    return []


def _locked_entries(user_id: int, days: int, db: Session) -> list[CalendarEntry]:
    since = date.today() - timedelta(days=days)
    return (
        db.query(CalendarEntry)
        .filter(
            CalendarEntry.user_id == user_id,
            CalendarEntry.locked_outfit_id.isnot(None),
            CalendarEntry.date >= since,
            CalendarEntry.date <= date.today(),
        )
        .all()
    )


def _wear_counts(user_id: int, days: int, db: Session) -> Counter:
    counts: Counter = Counter()
    for entry in _locked_entries(user_id, days, db):
        # Every piece of the outfit counts as worn. Counting only the primary
        # item made anything that was always second or third read as never worn.
        counts.update(locked_item_ids(entry))
    return counts


def get_wear_frequency(
    user_id: int, item_id: int, db: Session, days: int = DEFAULT_WINDOW_DAYS
) -> int:
    """How many times an item was locked in the calendar in the last N days."""
    return _wear_counts(user_id, days, db)[item_id]


def get_item_wear_history(
    user_id: int, days: int = DEFAULT_WINDOW_DAYS, db: Session | None = None
) -> dict:
    """Wear analytics: most-worn items, never-worn items, and totals."""
    if db is None:
        raise ValueError("get_item_wear_history requires a db session")

    counts = _wear_counts(user_id, days, db)
    items = db.query(ClothingItem).filter(ClothingItem.user_id == user_id).all()
    by_id = {i.id: i for i in items}

    def _item_dict(item: ClothingItem, count: int) -> dict:
        return {
            "id": item.id,
            "name": item.name,
            "category": item.category,
            "color": item.color,
            "image_url": item.image_url,
            "wear_count": count,
        }

    worn = [
        _item_dict(by_id[item_id], count)
        for item_id, count in counts.most_common()
        if item_id in by_id
    ]
    never_worn = [_item_dict(i, 0) for i in items if counts[i.id] == 0]

    return {
        "days": days,
        "total_wears": sum(counts.values()),
        "items_worn": len(worn),
        "wardrobe_size": len(items),
        "most_worn": worn,
        "never_worn": never_worn,
    }


def check_outfit_repeat(
    user_id: int,
    item_ids: list[int],
    db: Session,
    days: int = DEFAULT_WINDOW_DAYS,
) -> dict:
    """Warn about over-worn items in a candidate outfit, with a swap to try.

    The alternative is the least-worn item in the same category that isn't
    already in the outfit — the cheapest way to break a repeat.
    """
    counts = _wear_counts(user_id, days, db)
    items = db.query(ClothingItem).filter(ClothingItem.user_id == user_id).all()
    by_id = {i.id: i for i in items}

    warnings = []
    for item_id in item_ids:
        count = counts[item_id]
        if count < REPEAT_WARNING_THRESHOLD:
            continue
        item = by_id.get(item_id)
        if item is None:
            continue

        alternatives = sorted(
            (
                i
                for i in items
                if i.id not in set(item_ids)
                and (i.category or "").lower() == (item.category or "").lower()
            ),
            key=lambda i: counts[i.id],
        )
        alt = alternatives[0] if alternatives else None

        label = item.name or item.category or "this piece"
        message = (
            f"You've worn this {item.category or 'item'} {count} times "
            f"in the last {days} days — try switching it up?"
        )
        warnings.append(
            {
                "item_id": item.id,
                "item_name": label,
                "category": item.category,
                "wear_count": count,
                "message": message,
                "alternative": (
                    {
                        "id": alt.id,
                        "name": alt.name,
                        "category": alt.category,
                        "color": alt.color,
                        "image_url": alt.image_url,
                        "wear_count": counts[alt.id],
                    }
                    if alt
                    else None
                ),
            }
        )

    return {"days": days, "threshold": REPEAT_WARNING_THRESHOLD, "warnings": warnings}
