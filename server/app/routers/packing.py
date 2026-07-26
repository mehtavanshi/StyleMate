from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.packing_service import PURPOSES, generate_packing_list

router = APIRouter(prefix="/packing", tags=["packing"])


class PackingRequest(BaseModel):
    destination: str
    duration: int
    purpose: str = "leisure"
    user_id: int = 1


@router.get("/purposes")
def list_purposes():
    return {"purposes": list(PURPOSES)}


@router.post("/packing-list")
def get_packing_list(req: PackingRequest, db: Session = Depends(get_db)):
    return generate_packing_list(
        req.destination.strip() or "your destination",
        req.duration,
        req.purpose,
        req.user_id,
        db,
    )
