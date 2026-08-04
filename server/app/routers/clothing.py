from threading import Thread

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database import SessionLocal, get_db
from app.matching_service import complete_outfit, suggest_matches
from app.models import ClothingItem, User
from app.pair_cache import invalidate_item
from app.routers.tagging import score_to_formality_label
from app.schemas import ClothingItemCreate, ClothingItemUpdate, ClothingItemResponse
from app.style_embeddings import compute_and_store_embedding

router = APIRouter(prefix="/clothing", tags=["clothing"])


def _get_item_or_404(item_id: int, db: Session) -> ClothingItem:
    item = db.query(ClothingItem).filter(ClothingItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


def _check_owner(item: ClothingItem, user_id: int) -> None:
    if item.user_id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized")


@router.get("/", response_model=list[ClothingItemResponse])
def list_items(
    category: str | None = None,
    season: str | None = None,
    occasion_tag: str | None = None,
    target_gender: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(ClothingItem).filter(ClothingItem.user_id == current_user.id)
    if category:
        query = query.filter(ClothingItem.category == category)
    if season:
        query = query.filter(ClothingItem.season == season)
    if occasion_tag:
        query = query.filter(ClothingItem.occasion_tag.contains(occasion_tag))
    if target_gender:
        query = query.filter(ClothingItem.target_gender == target_gender)
    return query.order_by(ClothingItem.created_at.desc()).all()


@router.post("/", response_model=ClothingItemResponse, status_code=201)
def create_item(
    item: ClothingItemCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    db_item = ClothingItem(**item.model_dump(), user_id=current_user.id)
    db_item.formality = score_to_formality_label(db_item.formality_score)
    db.add(db_item)
    db.commit()
    db.refresh(db_item)

    def _bg_compute():
        session = SessionLocal()
        try:
            compute_and_store_embedding(db_item.id, session)
            # The embedding feeds score_pair, so any pair scored before it
            # landed used a neutral 0.5 similarity and is now stale.
            invalidate_item(session, db_item.id)
            session.commit()
        finally:
            session.close()

    Thread(target=_bg_compute, daemon=True).start()

    return db_item


@router.get("/{item_id}", response_model=ClothingItemResponse)
def get_item(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    item = _get_item_or_404(item_id, db)
    _check_owner(item, current_user.id)
    return item


@router.put("/{item_id}", response_model=ClothingItemResponse)
def update_item(
    item_id: int,
    updates: ClothingItemUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    item = _get_item_or_404(item_id, db)
    _check_owner(item, current_user.id)
    for key, value in updates.model_dump(exclude_unset=True).items():
        setattr(item, key, value)
    # Always re-derive formality from score so the two never drift
    # regardless of which path set formality_score (AI, manual, or edit).
    item.formality = score_to_formality_label(item.formality_score)
    # Colour/category/season edits change how this item scores against
    # everything else, so its cached pairs have to go.
    invalidate_item(db, item_id)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/{item_id}")
def delete_item(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    item = _get_item_or_404(item_id, db)
    _check_owner(item, current_user.id)
    invalidate_item(db, item_id)
    db.delete(item)
    db.commit()
    return {"detail": "Item deleted"}


@router.get("/{item_id}/suggestions")
def item_suggestions(
    item_id: int,
    category: str,
    limit: int = 10,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    item = _get_item_or_404(item_id, db)
    _check_owner(item, current_user.id)
    return suggest_matches(item_id, category, db, limit=limit)


@router.get("/{item_id}/complete-outfit")
def item_complete_outfit(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    item = _get_item_or_404(item_id, db)
    _check_owner(item, current_user.id)
    return complete_outfit(item_id, db)
