from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import WardrobeItem
from app.schemas import WardrobeItemCreate, WardrobeItemUpdate, WardrobeItemResponse

router = APIRouter(prefix="/wardrobe", tags=["wardrobe"])


@router.get("/", response_model=list[WardrobeItemResponse])
def list_items(
    category: str | None = None,
    season: str | None = None,
    occasion: str | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(WardrobeItem)
    if category:
        query = query.filter(WardrobeItem.category == category)
    if season:
        query = query.filter(WardrobeItem.season == season)
    if occasion:
        query = query.filter(WardrobeItem.occasion == occasion)
    return query.order_by(WardrobeItem.created_at.desc()).all()


@router.post("/", response_model=WardrobeItemResponse, status_code=201)
def create_item(item: WardrobeItemCreate, db: Session = Depends(get_db)):
    db_item = WardrobeItem(**item.model_dump())
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    return db_item


@router.get("/{item_id}", response_model=WardrobeItemResponse)
def get_item(item_id: int, db: Session = Depends(get_db)):
    item = db.query(WardrobeItem).filter(WardrobeItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


@router.put("/{item_id}", response_model=WardrobeItemResponse)
def update_item(item_id: int, updates: WardrobeItemUpdate, db: Session = Depends(get_db)):
    item = db.query(WardrobeItem).filter(WardrobeItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    for key, value in updates.model_dump(exclude_unset=True).items():
        setattr(item, key, value)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/{item_id}")
def delete_item(item_id: int, db: Session = Depends(get_db)):
    item = db.query(WardrobeItem).filter(WardrobeItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    db.delete(item)
    db.commit()
    return {"detail": "Item deleted"}
