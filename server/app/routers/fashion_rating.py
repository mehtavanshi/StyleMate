from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.services.fashion_rating_service import rate_outfit_photo

router = APIRouter(prefix="/fashion-rating", tags=["fashion-rating"])


class RatingRequest(BaseModel):
    image_url: str | None = None
    user_id: int = 1


@router.post("/rate")
def rate_photo(req: RatingRequest, db: Session = Depends(get_db)):
    """Rate an outfit photo. Falls back to the user's consented photo.

    Rating the stored photo requires consent to have been given — the same
    gate the try-on flow uses.
    """
    image_url = req.image_url
    if not image_url:
        user = db.query(User).filter(User.id == req.user_id).first()
        if not user or not user.photo_url:
            raise HTTPException(
                status_code=400,
                detail="No photo to rate — upload one or pass image_url.",
            )
        if not user.photo_consent:
            raise HTTPException(
                status_code=403, detail="Photo consent required before rating."
            )
        image_url = user.photo_url

    return rate_outfit_photo(image_url)
