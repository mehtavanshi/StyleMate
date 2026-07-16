from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ClothingItem
from app.schemas import ClothingItemCreate, ClothingItemUpdate, ClothingItemResponse

router = APIRouter(prefix="/clothing", tags=["clothing"])


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
        query = query.filter(ClothingItem.occasion_tag == occasion_tag)
    if target_gender:
        query = query.filter(ClothingItem.target_gender == target_gender)
    return query.order_by(ClothingItem.created_at.desc()).all()


@router.post("/", response_model=ClothingItemResponse, status_code=201)
def create_item(item: ClothingItemCreate, db: Session = Depends(get_db)):
    db_item = ClothingItem(**item.model_dump())
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
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
    db.commit()
    db.refresh(item)
    return item


@router.delete("/{item_id}")
def delete_item(item_id: int, db: Session = Depends(get_db)):
    item = db.query(ClothingItem).filter(ClothingItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    db.delete(item)
    db.commit()
    return {"detail": "Item deleted"}
