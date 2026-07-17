from dateutil import parser as date_parser
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import CalendarEntry
from app.schemas import (
    CalendarEntryCreate,
    CalendarEntryResponse,
    CalendarEntryUpdate,
)

router = APIRouter(prefix="/calendar-entries", tags=["calendar"])


@router.post("/", response_model=CalendarEntryResponse, status_code=201)
def create_entry(entry: CalendarEntryCreate, db: Session = Depends(get_db)):
    db_entry = CalendarEntry(**entry.model_dump())
    db.add(db_entry)
    db.commit()
    db.refresh(db_entry)
    return db_entry


@router.get("/", response_model=list[CalendarEntryResponse])
def list_entries(
    user_id: int | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(CalendarEntry)
    if user_id is not None:
        query = query.filter(CalendarEntry.user_id == user_id)
    if start_date:
        parsed = date_parser.parse(start_date).date()
        query = query.filter(CalendarEntry.date >= parsed)
    if end_date:
        parsed = date_parser.parse(end_date).date()
        query = query.filter(CalendarEntry.date <= parsed)
    return query.order_by(CalendarEntry.date.asc()).all()


@router.patch("/{entry_id}", response_model=CalendarEntryResponse)
def update_entry(
    entry_id: int,
    updates: CalendarEntryUpdate,
    db: Session = Depends(get_db),
):
    entry = db.query(CalendarEntry).filter(CalendarEntry.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Calendar entry not found")
    for key, value in updates.model_dump(exclude_unset=True).items():
        setattr(entry, key, value)
    db.commit()
    db.refresh(entry)
    return entry
