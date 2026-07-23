from dateutil import parser as date_parser
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from datetime import date

from app.database import get_db
from app.models import CalendarEntry, TryOnResult
from app.schemas import (
    CalendarEntryCreate,
    CalendarEntryResponse,
    CalendarEntryUpdate,
)

router = APIRouter(prefix="/calendar-entries", tags=["calendar"])


class TryOnImageLink(BaseModel):
    try_on_result_id: int


@router.post("/", response_model=CalendarEntryResponse, status_code=201)
def create_entry(entry: CalendarEntryCreate, db: Session = Depends(get_db)):
    db_entry = CalendarEntry(**entry.model_dump())
    db.add(db_entry)
    db.commit()
    db.refresh(db_entry)

    try_on_result = (
        db.query(TryOnResult)
        .filter(TryOnResult.id == db_entry.try_on_result_id)
        .first()
        if db_entry.try_on_result_id
        else None
    )

    return {
        "id": db_entry.id,
        "user_id": db_entry.user_id,
        "date": db_entry.date,
        "occasion_tag": db_entry.occasion_tag,
        "locked_outfit_id": db_entry.locked_outfit_id,
        "try_on_result_id": db_entry.try_on_result_id,
        "try_on_result_image_url": try_on_result.result_image_url if try_on_result else None,
        "created_at": db_entry.created_at,
    }


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
    return [
        {
            "id": e.id,
            "user_id": e.user_id,
            "date": e.date,
            "occasion_tag": e.occasion_tag,
            "locked_outfit_id": e.locked_outfit_id,
            "try_on_result_id": e.try_on_result_id,
            "try_on_result_image_url": e.try_on_result.result_image_url if e.try_on_result else None,
            "created_at": e.created_at,
        }
        for e in entries
    ]


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


@router.patch("/{entry_id}/try-on-image", response_model=CalendarEntryResponse)
def link_try_on_image(
    entry_id: int,
    payload: TryOnImageLink,
    db: Session = Depends(get_db),
):
    entry = db.query(CalendarEntry).filter(CalendarEntry.id == entry_id).first()
    if not entry:
        today = date.today().isoformat()
        entry = CalendarEntry(
            user_id=1,
            date=today,
            try_on_result_id=payload.try_on_result_id,
        )
        db.add(entry)
    else:
        entry.try_on_result_id = payload.try_on_result_id
    db.commit()
    db.refresh(entry)

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
