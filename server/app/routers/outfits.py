from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.pairing_engine import OutfitSuggestion, suggest_outfits

router = APIRouter(tags=["outfit-suggestions"])


class OutfitItemResponse(BaseModel):
    id: int
    name: str | None
    category: str
    color: str | None
    pattern: str | None
    image_url: str | None
    target_gender: str | None = None


class OutfitSuggestionResponse(BaseModel):
    items: list[OutfitItemResponse]
    score: float
    reason: str


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
        )
        for r in results
    ]
