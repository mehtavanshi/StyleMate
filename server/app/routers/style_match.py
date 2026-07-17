from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.style_match import generate_style_match, style_match_to_dict

router = APIRouter(tags=["style-match"])


@router.get("/style-match")
async def style_match(
    item_id: int = Query(..., description="Wardrobe item to generate matches for"),
    db: Session = Depends(get_db),
):
    """Generate personalized style-match suggestions for a single item."""
    try:
        result = generate_style_match(item_id, db)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return style_match_to_dict(result)
