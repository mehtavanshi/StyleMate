import logging
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Thread

from dotenv import load_dotenv

# Load .env before anything else reads os.getenv()
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from app.database import Base, SessionLocal, engine, get_db
from app import models  # noqa: F401
from app.config import load_body_type_rules
from app.models import User
from app.celery_app import celery_app  # noqa: F401
from app.routers import users, clothing, upload, tagging, outfits, calendar, shopping, style_match, shop_matches, style_advice, tryon
from app.schemas import ClothingItemCreate, ClothingItemResponse
from app.storage import get_storage_provider
from app.style_embeddings import compute_and_store_embedding

logger = logging.getLogger(__name__)

UPLOADS_DIR = Path(__file__).resolve().parents[1] / "uploads"

Base.metadata.create_all(bind=engine)

load_body_type_rules()

# Ensure demo user exists (id=1) so the app works out of the box.
_db = SessionLocal()
try:
    if not _db.query(User).filter(User.id == 1).first():
        _db.add(User(id=1, name="Demo User", email="demo@stylemate.app"))
        _db.commit()
        logger.info("Created demo user (id=1)")
finally:
    _db.close()

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
app.include_router(calendar.router)
app.include_router(shopping.router)
app.include_router(style_match.router)
app.include_router(shop_matches.router)
app.include_router(style_advice.router)
app.include_router(tryon.router)


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


# ── Background photo cleanup job ──

PHOTO_RETENTION_DAYS = int(os.getenv("PHOTO_RETENTION_DAYS", "90"))
CHECK_INTERVAL_SECONDS = int(os.getenv("PHOTO_CLEANUP_INTERVAL_SECONDS", "86400"))  # 24h


def _cleanup_expired_photos() -> None:
    """Delete photos whose associated account has been inactive for
    PHOTO_RETENTION_DAYS days (using last_activity_at or created_at as a
    fallback).  This is a config value, not hardcoded.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=PHOTO_RETENTION_DAYS)
    db: Session = SessionLocal()
    try:
        expired = (
            db.query(User)
            .filter(
                User.photo_url.isnot(None),
                (
                    (User.last_activity_at.is_(None) & (User.created_at < cutoff))
                    | (User.last_activity_at < cutoff)
                ),
            )
            .all()
        )
        provider = get_storage_provider()
        for user in expired:
            try:
                provider.delete_file(user.photo_url)
                logger.info("Deleted expired photo for user %s", user.id)
            except Exception:
                logger.exception("Failed to delete photo for user %s", user.id)
            user.photo_url = None
            user.photo_storage_key = None
        db.commit()
        if expired:
            logger.info("Photo cleanup: removed %s expired photo(s)", len(expired))
    except Exception:
        logger.exception("Photo cleanup job failed")
    finally:
        db.close()


def _photo_cleanup_loop() -> None:
    while True:
        _cleanup_expired_photos()
        time.sleep(CHECK_INTERVAL_SECONDS)


Thread(target=_photo_cleanup_loop, daemon=True).start()


UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(UPLOADS_DIR)), name="uploads")
