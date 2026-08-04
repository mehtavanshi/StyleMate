from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from datetime import datetime, timezone

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models import CalendarEntry, TryOnResult, User
from app.schemas import BodyTypeIn, ConsentIn, ConsentResponse, PhotoUrlIn, UserResponse
from app.storage import get_storage_provider

router = APIRouter(prefix="/users", tags=["users"])


def _touch_activity(user: User, db: Session) -> None:
    user.last_activity_at = datetime.now(timezone.utc)
    db.commit()


def _consent_response(user: User) -> ConsentResponse:
    signed_url = None
    if user.photo_url:
        provider = get_storage_provider()
        signed_url = provider.get_signed_url(user.photo_url)
    return ConsentResponse(
        photo_consent=bool(user.photo_consent),
        consent_given_at=user.consent_given_at,
        consent_version=user.consent_version,
        photo_url=signed_url,
    )


@router.get("/me", response_model=UserResponse)
def get_me(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _touch_activity(current_user, db)
    return current_user


@router.post("/me/body-type", response_model=UserResponse)
def set_body_type(
    body_type_in: BodyTypeIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    current_user.body_type = body_type_in.body_type
    _touch_activity(current_user, db)
    # score_pair weights style tags by body type, so every cached pair for this
    # user is now priced against the wrong body type.
    from app.pair_cache import invalidate_user

    invalidate_user(db, current_user.id)
    db.commit()
    db.refresh(current_user)
    return current_user


@router.get("/me/consent", response_model=ConsentResponse)
def get_consent(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _touch_activity(current_user, db)
    return _consent_response(current_user)


@router.post("/me/consent", response_model=ConsentResponse)
def give_consent(
    consent_in: ConsentIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    current_user.photo_consent = True
    current_user.consent_given_at = datetime.now(timezone.utc)
    current_user.consent_version = consent_in.consent_version
    _touch_activity(current_user, db)
    db.commit()
    db.refresh(current_user)
    return _consent_response(current_user)


@router.put("/me/photo", response_model=UserResponse)
def set_user_photo(
    photo_in: PhotoUrlIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    current_user.photo_url = photo_in.image_url
    current_user.photo_storage_key = photo_in.image_url
    _touch_activity(current_user, db)
    db.commit()
    db.refresh(current_user)
    return current_user


@router.delete("/me/photo", status_code=204)
def delete_user_photo(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    user_id = current_user.id
    if not current_user.photo_url:
        return

    provider = get_storage_provider()
    provider.delete_file(current_user.photo_url)

    db.query(CalendarEntry).filter(
        CalendarEntry.user_id == user_id,
        CalendarEntry.try_on_result_id.isnot(None),
    ).update({CalendarEntry.try_on_result_id: None})
    db.query(TryOnResult).filter(TryOnResult.user_id == user_id).delete()
    current_user.photo_url = None
    current_user.photo_storage_key = None
    _touch_activity(current_user, db)
    db.commit()
