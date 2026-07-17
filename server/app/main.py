from pathlib import Path
from threading import Thread

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from app.database import Base, SessionLocal, engine, get_db
from app import models  # noqa: F401
from app.models import ClothingItem
from app.routers import users, clothing, upload, tagging, outfits
from app.schemas import ClothingItemCreate, ClothingItemResponse
from app.style_embeddings import compute_and_store_embedding

UPLOADS_DIR = Path(__file__).resolve().parents[1] / "uploads"

Base.metadata.create_all(bind=engine)

app = FastAPI(title="StyleMate API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(users.router)
app.include_router(clothing.router)
app.include_router(upload.router)
app.include_router(tagging.router)
app.include_router(outfits.router)


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.post("/clothing-items", response_model=ClothingItemResponse, status_code=201)
def create_clothing_item(item: ClothingItemCreate, db: Session = Depends(get_db)):
    db_item = ClothingItem(**item.model_dump())
    db.add(db_item)
    db.commit()
    db.refresh(db_item)

    def _bg_compute():
        session = SessionLocal()
        try:
            compute_and_store_embedding(db_item.id, session)
        finally:
            session.close()

    Thread(target=_bg_compute, daemon=True).start()

    return db_item


UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(UPLOADS_DIR)), name="uploads")
