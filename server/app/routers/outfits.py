from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Outfit, OutfitItem, WardrobeItem
from app.schemas import OutfitCreate, OutfitResponse

router = APIRouter(prefix="/outfits", tags=["outfits"])


@router.get("/", response_model=list[OutfitResponse])
def list_outfits(db: Session = Depends(get_db)):
    return db.query(Outfit).order_by(Outfit.created_at.desc()).all()


@router.post("/", response_model=OutfitResponse, status_code=201)
def create_outfit(outfit_in: OutfitCreate, db: Session = Depends(get_db)):
    outfit = Outfit(
        name=outfit_in.name,
        occasion=outfit_in.occasion,
        season=outfit_in.season,
        score=outfit_in.score,
        notes=outfit_in.notes,
    )
    db.add(outfit)
    db.flush()

    for item_id in outfit_in.item_ids:
        item = db.query(WardrobeItem).filter(WardrobeItem.id == item_id).first()
        if not item:
            raise HTTPException(status_code=404, detail=f"Wardrobe item {item_id} not found")
        db.add(OutfitItem(outfit_id=outfit.id, wardrobe_item_id=item_id))

    db.commit()
    db.refresh(outfit)
    return outfit


@router.get("/{outfit_id}", response_model=OutfitResponse)
def get_outfit(outfit_id: int, db: Session = Depends(get_db)):
    outfit = db.query(Outfit).filter(Outfit.id == outfit_id).first()
    if not outfit:
        raise HTTPException(status_code=404, detail="Outfit not found")
    return outfit


@router.delete("/{outfit_id}")
def delete_outfit(outfit_id: int, db: Session = Depends(get_db)):
    outfit = db.query(Outfit).filter(Outfit.id == outfit_id).first()
    if not outfit:
        raise HTTPException(status_code=404, detail="Outfit not found")
    db.delete(outfit)
    db.commit()
    return {"detail": "Outfit deleted"}
