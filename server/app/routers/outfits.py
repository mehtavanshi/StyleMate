from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import OutfitFeedback
from app.pairing_engine import OutfitSuggestion, suggest_outfits
from app.schemas import OutfitFeedbackResponse, OutfitFeedbackIn

router = APIRouter(tags=["outfit-suggestions"])


class OutfitItemResponse(BaseModel):
    id: int
    name: str | None
    category: str
    color: str | None
    pattern: str | None
    fabric_type: str | None = None
    fit_type: str | None = None
    sleeve_length: str | None = None
    image_url: str | None
    target_gender: str | None = None


class OutfitSuggestionResponse(BaseModel):
    items: list[OutfitItemResponse]
    score: float
    reason: str
    breakdown: dict[str, float] = {}


@router.get("/outfit-suggestions", response_model=list[OutfitSuggestionResponse])
def get_outfit_suggestions(
    user_id: int = 1,
    occasion_tag: str | None = None,
    target_gender: str | None = None,
    limit: int = 5,
    db: Session = Depends(get_db),
):
    results = suggest_outfits(db, user_id, occasion_tag, target_gender, limit)
    return [
        OutfitSuggestionResponse(
            items=[OutfitItemResponse(**i) for i in r.items],
            score=r.score,
            reason=r.reason,
            breakdown=r.breakdown,
        )
        for r in results
    ]


@router.post("/outfit-feedback", response_model=OutfitFeedbackResponse)
def create_outfit_feedback(
    payload: OutfitFeedbackIn,
    db: Session = Depends(get_db),
):
    import json

    db_feedback = OutfitFeedback(
        user_id=payload.user_id,
        outfit_item_ids=json.dumps(payload.outfit_item_ids),
        liked=1 if payload.liked else 0,
    )
    db.add(db_feedback)
    db.commit()
    db.refresh(db_feedback)

    return OutfitFeedbackResponse(
        id=db_feedback.id,
        user_id=db_feedback.user_id,
        outfit_item_ids=payload.outfit_item_ids,
        liked=payload.liked,
        created_at=db_feedback.created_at,
    )
