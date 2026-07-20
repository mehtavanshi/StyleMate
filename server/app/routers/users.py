from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from datetime import datetime, timezone

from app.database import get_db
from app.models import TryOnResult, User
from app.schemas import BodyTypeIn, ConsentIn, ConsentResponse, PhotoUrlIn, UserCreate, UserResponse
from app.storage import get_storage_provider

router = APIRouter(prefix="/users", tags=["users"])


def _get_current_user_id(x_user_id: int = Header(alias="X-User-ID", default=0)) -> int:
    return x_user_id


def _get_user_or_404(user_id: int, db: Session) -> User:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


def _check_owner(user_id: int, current_user_id: int) -> None:
    if current_user_id and current_user_id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized")


def _touch_activity(user: User, db: Session) -> None:
    user.last_activity_at = datetime.now(timezone.utc)
    db.commit()


@router.get("/", response_model=list[UserResponse])
def list_users(db: Session = Depends(get_db)):
    return db.query(User).order_by(User.created_at.desc()).all()


@router.post("/", response_model=UserResponse, status_code=201)
def create_user(user: UserCreate, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == user.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    db_user = User(**user.model_dump())
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


@router.get("/{user_id}", response_model=UserResponse)
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user_id: int = Depends(_get_current_user_id),
):
    _check_owner(user_id, current_user_id)
    user = _get_user_or_404(user_id, db)
    _touch_activity(user, db)
    return user


@router.post("/{user_id}/body-type", response_model=UserResponse)
def set_body_type(
    user_id: int,
    body_type_in: BodyTypeIn,
    db: Session = Depends(get_db),
    current_user_id: int = Depends(_get_current_user_id),
):
    _check_owner(user_id, current_user_id)
    user = _get_user_or_404(user_id, db)
    user.body_type = body_type_in.body_type
    _touch_activity(user, db)
    db.commit()
    db.refresh(user)
    return user


@router.get("/{user_id}/consent", response_model=ConsentResponse)
def get_consent(
    user_id: int,
    db: Session = Depends(get_db),
    current_user_id: int = Depends(_get_current_user_id),
):
    _check_owner(user_id, current_user_id)
    user = _get_user_or_404(user_id, db)
    _touch_activity(user, db)

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


@router.post("/{user_id}/consent", response_model=ConsentResponse)
def give_consent(
    user_id: int,
    consent_in: ConsentIn,
    db: Session = Depends(get_db),
    current_user_id: int = Depends(_get_current_user_id),
):
    _check_owner(user_id, current_user_id)
    user = _get_user_or_404(user_id, db)
    user.photo_consent = True
    user.consent_given_at = datetime.now(timezone.utc)
    user.consent_version = consent_in.consent_version
    _touch_activity(user, db)
    db.commit()
    db.refresh(user)

    signed_url = None
    if user.photo_url:
        provider = get_storage_provider()
        signed_url = provider.get_signed_url(user.photo_url)

    return ConsentResponse(
        photo_consent=True,
        consent_given_at=user.consent_given_at,
        consent_version=user.consent_version,
        photo_url=signed_url,
    )


@router.put("/{user_id}/photo", response_model=UserResponse)
def set_user_photo(
    user_id: int,
    photo_in: PhotoUrlIn,
    db: Session = Depends(get_db),
    current_user_id: int = Depends(_get_current_user_id),
):
    _check_owner(user_id, current_user_id)
    user = _get_user_or_404(user_id, db)
    user.photo_url = photo_in.image_url
    user.photo_storage_key = photo_in.image_url
    _touch_activity(user, db)
    db.commit()
    db.refresh(user)
    return user


@router.delete("/{user_id}/photo", status_code=204)
def delete_user_photo(
    user_id: int,
    db: Session = Depends(get_db),
    current_user_id: int = Depends(_get_current_user_id),
):
    _check_owner(user_id, current_user_id)
    user = _get_user_or_404(user_id, db)

    if not user.photo_url:
        return

    provider = get_storage_provider()
    provider.delete_file(user.photo_url)

    db.query(TryOnResult).filter(TryOnResult.user_id == user_id).delete()
    user.photo_url = None
    user.photo_storage_key = None
    _touch_activity(user, db)
    db.commit()
