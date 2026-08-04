from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models import ClothingItem, User
from app.style_match import (
    MAX_CANDIDATES_PER_CATEGORY,
    generate_style_match,
    style_match_to_dict,
)

router = APIRouter(tags=["style-match"])


@router.get("/style-match")
async def style_match(
    item_id: int = Query(..., description="Wardrobe item to generate matches for"),
    limit: int = Query(
        MAX_CANDIDATES_PER_CATEGORY,
        ge=1,
        le=30,
        description="Suggestions generated per partner category; raised by 'Load More'",
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generate personalized style-match suggestions for a single item."""
    item = db.query(ClothingItem).filter(ClothingItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    if item.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    try:
        result = generate_style_match(item_id, db, limit=limit)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return style_match_to_dict(result)
