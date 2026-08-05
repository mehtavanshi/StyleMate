import logging
from threading import Thread

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.matching_service import complete_outfit, suggest_matches
from app.models import ClothingItem
from app.pair_cache import invalidate_item
from app.routers.tagging import score_to_formality_label
from app.schemas import ClothingItemCreate, ClothingItemUpdate, ClothingItemResponse
from app.tasks import execute_embedding_job, run_embedding_job

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/clothing", tags=["clothing"])


def dispatch_embedding_job(item_id: int) -> None:
    """Queue the embedding computation; same Celery-then-thread ladder as try-on.

    A bare Thread was lost on restart, so an item created just before a deploy
    kept a neutral 0.5 similarity forever. Celery retries it instead.
    """
    try:
        run_embedding_job.delay(item_id)
    except Exception:
        logger.warning(
            "Celery unavailable, computing embedding for item %s in a thread", item_id
        )
        Thread(target=execute_embedding_job, args=(item_id,), daemon=True).start()


@router.get("/", response_model=list[ClothingItemResponse])
def list_items(
    user_id: int | None = None,
    category: str | None = None,
    season: str | None = None,
    occasion_tag: str | None = None,
    target_gender: str | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(ClothingItem)
    if user_id is not None:
        query = query.filter(ClothingItem.user_id == user_id)
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
def create_item(item: ClothingItemCreate, db: Session = Depends(get_db)):
    db_item = ClothingItem(**item.model_dump())
    db_item.formality = score_to_formality_label(db_item.formality_score)
    db.add(db_item)
    db.commit()
    db.refresh(db_item)

    dispatch_embedding_job(db_item.id)

    return db_item


@router.get("/{item_id}", response_model=ClothingItemResponse)
def get_item(item_id: int, db: Session = Depends(get_db)):
    item = db.query(ClothingItem).filter(ClothingItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


@router.put("/{item_id}", response_model=ClothingItemResponse)
def update_item(item_id: int, updates: ClothingItemUpdate, db: Session = Depends(get_db)):
    item = db.query(ClothingItem).filter(ClothingItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
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
def delete_item(item_id: int, db: Session = Depends(get_db)):
    item = db.query(ClothingItem).filter(ClothingItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
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
):
    return suggest_matches(item_id, category, db, limit=limit)


@router.get("/{item_id}/complete-outfit")
def item_complete_outfit(item_id: int, db: Session = Depends(get_db)):
    return complete_outfit(item_id, db)
