import json

from dateutil import parser as date_parser
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import CalendarEntry, ClothingItem, TryOnResult
from app.schemas import (
    CalendarEntryCreate,
    CalendarEntryResponse,
    CalendarEntryUpdate,
)
from app.services.calendar_service import (
    check_outfit_repeat,
    get_item_wear_history,
    locked_item_ids,
)

router = APIRouter(prefix="/calendar-entries", tags=["calendar"])

# Wear analytics sit outside the /calendar-entries CRUD prefix so the paths
# read as the plan specifies (/calendar/analytics, /calendar/repeat-check).
analytics_router = APIRouter(prefix="/calendar", tags=["calendar"])


@analytics_router.get("/analytics")
def calendar_analytics(
    user_id: int = 1,
    days: int = 30,
    db: Session = Depends(get_db),
):
    """Wear frequency over the last N days, from locked calendar outfits."""
    return get_item_wear_history(user_id, max(1, min(days, 365)), db)


@analytics_router.get("/repeat-check")
def repeat_check(
    outfit_item_ids: str,
    user_id: int = 1,
    days: int = 30,
    db: Session = Depends(get_db),
):
    """Flag over-worn items in a candidate outfit. ``outfit_item_ids``: "1,2,3"."""
    try:
        item_ids = [int(part) for part in outfit_item_ids.split(",") if part.strip()]
    except ValueError:
        raise HTTPException(
            status_code=422, detail="outfit_item_ids must be comma-separated integers"
        )
    if not item_ids:
        raise HTTPException(status_code=422, detail="outfit_item_ids is required")
    return check_outfit_repeat(user_id, item_ids, db, days=max(1, min(days, 365)))


class TryOnImageLink(BaseModel):
    try_on_result_id: int


def _serialize(entry: CalendarEntry, db: Session) -> dict:
    """One response shape for every calendar endpoint.

    Four hand-rolled copies of this dict meant a new field (the locked outfit's
    items) had to be added in four places or silently go missing from some
    responses.
    """
    item_ids = locked_item_ids(entry)
    items = (
        db.query(ClothingItem).filter(ClothingItem.id.in_(item_ids)).all()
        if item_ids
        else []
    )
    by_id = {i.id: i for i in items}
    return {
        "id": entry.id,
        "user_id": entry.user_id,
        "date": entry.date,
        "occasion_tag": entry.occasion_tag,
        "locked_outfit_id": entry.locked_outfit_id,
        "locked_item_ids": item_ids or None,
        # Ordered as locked, so the client renders top-then-bottom-then-shoes.
        "locked_outfit_items": [
            {
                "id": i.id,
                "name": i.name,
                "category": i.category,
                "color": i.color,
                "image_url": i.image_url,
            }
            for i in (by_id.get(iid) for iid in item_ids)
            if i is not None
        ],
        "try_on_result_id": entry.try_on_result_id,
        "try_on_result_image_url": (
            entry.try_on_result.result_image_url if entry.try_on_result else None
        ),
        "created_at": entry.created_at,
    }


def _apply_updates(entry: CalendarEntry, updates: dict) -> None:
    """Assign updates, JSON-encoding the item-id list for the Text column."""
    for key, value in updates.items():
        if key == "locked_item_ids":
            entry.locked_item_ids = json.dumps(value) if value else None
        else:
            setattr(entry, key, value)


@router.post("/", response_model=CalendarEntryResponse, status_code=201)
def create_entry(entry: CalendarEntryCreate, db: Session = Depends(get_db)):
    db_entry = CalendarEntry()
    _apply_updates(db_entry, entry.model_dump())
    db.add(db_entry)
    db.commit()
    db.refresh(db_entry)
    return _serialize(db_entry, db)


@router.get("/", response_model=list[CalendarEntryResponse])
def list_entries(
    user_id: int | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(CalendarEntry).outerjoin(
        TryOnResult, CalendarEntry.try_on_result_id == TryOnResult.id
    )
    if user_id is not None:
        query = query.filter(CalendarEntry.user_id == user_id)
    if start_date:
        parsed = date_parser.parse(start_date).date()
        query = query.filter(CalendarEntry.date >= parsed)
    if end_date:
        parsed = date_parser.parse(end_date).date()
        query = query.filter(CalendarEntry.date <= parsed)
    entries = query.order_by(CalendarEntry.date.asc()).all()
    return [_serialize(e, db) for e in entries]


@router.patch("/{entry_id}", response_model=CalendarEntryResponse)
def update_entry(
    entry_id: int,
    updates: CalendarEntryUpdate,
    db: Session = Depends(get_db),
):
    entry = db.query(CalendarEntry).filter(CalendarEntry.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Calendar entry not found")
    _apply_updates(entry, updates.model_dump(exclude_unset=True))
    db.commit()
    db.refresh(entry)
    return _serialize(entry, db)


@router.patch("/{entry_id}/try-on-image", response_model=CalendarEntryResponse)
def link_try_on_image(
    entry_id: int,
    payload: TryOnImageLink,
    db: Session = Depends(get_db),
):
    entry = db.query(CalendarEntry).filter(CalendarEntry.id == entry_id).first()
    if not entry:
        # Was fabricating a today-dated entry owned by user 1, which both
        # ignored the requested entry_id and attributed it to the wrong user.
        raise HTTPException(status_code=404, detail=f"Calendar entry {entry_id} not found")
    entry.try_on_result_id = payload.try_on_result_id
    db.commit()
    db.refresh(entry)
    return _serialize(entry, db)
