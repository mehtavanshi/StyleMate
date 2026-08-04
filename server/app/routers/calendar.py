from dateutil import parser as date_parser
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from datetime import date

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models import CalendarEntry, TryOnResult, User
from app.schemas import (
    CalendarEntryCreate,
    CalendarEntryResponse,
    CalendarEntryUpdate,
)
from app.services.calendar_service import check_outfit_repeat, get_item_wear_history

router = APIRouter(prefix="/calendar-entries", tags=["calendar"])

# Wear analytics sit outside the /calendar-entries CRUD prefix so the paths
# read as the plan specifies (/calendar/analytics, /calendar/repeat-check).
analytics_router = APIRouter(prefix="/calendar", tags=["calendar"])


def _get_entry_or_404(entry_id: int, db: Session) -> CalendarEntry:
    entry = db.query(CalendarEntry).filter(CalendarEntry.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Calendar entry not found")
    return entry


def _check_owner(entry: CalendarEntry, user_id: int) -> None:
    if entry.user_id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized")


def _entry_response(entry: CalendarEntry, db: Session) -> dict:
    try_on_result = (
        db.query(TryOnResult)
        .filter(TryOnResult.id == entry.try_on_result_id)
        .first()
        if entry.try_on_result_id
        else None
    )
    return {
        "id": entry.id,
        "user_id": entry.user_id,
        "date": entry.date,
        "occasion_tag": entry.occasion_tag,
        "locked_outfit_id": entry.locked_outfit_id,
        "try_on_result_id": entry.try_on_result_id,
        "try_on_result_image_url": try_on_result.result_image_url if try_on_result else None,
        "created_at": entry.created_at,
    }


@analytics_router.get("/analytics")
def calendar_analytics(
    days: int = 30,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Wear frequency over the last N days, from locked calendar outfits."""
    return get_item_wear_history(current_user.id, max(1, min(days, 365)), db)


@analytics_router.get("/repeat-check")
def repeat_check(
    outfit_item_ids: str,
    days: int = 30,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
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
    return check_outfit_repeat(current_user.id, item_ids, db, days=max(1, min(days, 365)))


class TryOnImageLink(BaseModel):
    try_on_result_id: int


@router.post("/", response_model=CalendarEntryResponse, status_code=201)
def create_entry(
    entry: CalendarEntryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    db_entry = CalendarEntry(**entry.model_dump(), user_id=current_user.id)
    db.add(db_entry)
    db.commit()
    db.refresh(db_entry)
    return _entry_response(db_entry, db)


@router.get("/", response_model=list[CalendarEntryResponse])
def list_entries(
    start_date: str | None = None,
    end_date: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(CalendarEntry).outerjoin(
        TryOnResult, CalendarEntry.try_on_result_id == TryOnResult.id
    )
    query = query.filter(CalendarEntry.user_id == current_user.id)
    if start_date:
        parsed = date_parser.parse(start_date).date()
        query = query.filter(CalendarEntry.date >= parsed)
    if end_date:
        parsed = date_parser.parse(end_date).date()
        query = query.filter(CalendarEntry.date <= parsed)
    entries = query.order_by(CalendarEntry.date.asc()).all()
    return [_entry_response(e, db) for e in entries]


@router.patch("/{entry_id}", response_model=CalendarEntryResponse)
def update_entry(
    entry_id: int,
    updates: CalendarEntryUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    entry = _get_entry_or_404(entry_id, db)
    _check_owner(entry, current_user.id)
    for key, value in updates.model_dump(exclude_unset=True).items():
        setattr(entry, key, value)
    db.commit()
    db.refresh(entry)
    return _entry_response(entry, db)


@router.patch("/{entry_id}/try-on-image", response_model=CalendarEntryResponse)
def link_try_on_image(
    entry_id: int,
    payload: TryOnImageLink,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    entry = db.query(CalendarEntry).filter(CalendarEntry.id == entry_id).first()
    if not entry:
        today = date.today().isoformat()
        entry = CalendarEntry(
            user_id=current_user.id,
            date=today,
            try_on_result_id=payload.try_on_result_id,
        )
        db.add(entry)
    else:
        _check_owner(entry, current_user.id)
        entry.try_on_result_id = payload.try_on_result_id
    db.commit()
    db.refresh(entry)
    return _entry_response(entry, db)
