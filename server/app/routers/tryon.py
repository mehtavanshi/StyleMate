import json
import logging
import uuid

from pydantic import BaseModel

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ClothingItem, TryOnResult, User
from app.schemas import TryOnResultOut
from app.storage import get_storage_provider
from app.tasks import run_tryon_job

logger = logging.getLogger(__name__)

router = APIRouter(tags=["try-on"])


# ── Request/Response models ──

class TryOnRenderIn(BaseModel):
    garment_id: int


class TryOnJobOut(BaseModel):
    job_id: str
    status: str


# ── Helpers ──

SIGNED_URL_EXPIRY = 300


def _sign_result_url(storage_key: str | None) -> str | None:
    if not storage_key:
        return None
    return get_storage_provider().get_signed_url(storage_key, expires_in=SIGNED_URL_EXPIRY)


# ── Endpoints ──

@router.post("/try-on", response_model=TryOnJobOut, status_code=202)
def submit_tryon(
    body: TryOnRenderIn,
    request: Request,
    db: Session = Depends(get_db),
):
    """Submit a try-on job. Returns a job_id for polling."""
    x_user_id = request.headers.get("X-User-ID")
    if not x_user_id or not x_user_id.isdigit():
        raise HTTPException(status_code=401, detail="X-User-ID header required")
    user_id = int(x_user_id)

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if not user.photo_url:
        raise HTTPException(
            status_code=400,
            detail="Upload your body photo first via the Profile screen.",
        )
    if not user.photo_consent:
        raise HTTPException(
            status_code=400,
            detail="Photo consent not given.",
        )

    garment = db.query(ClothingItem).filter(ClothingItem.id == body.garment_id).first()
    if not garment:
        raise HTTPException(status_code=404, detail="Garment not found")
    if garment.user_id != user_id:
        raise HTTPException(status_code=403, detail="Garment does not belong to you")
    if not garment.image_url:
        raise HTTPException(status_code=400, detail="Garment has no image")

    job_id = str(uuid.uuid4())
    record = TryOnResult(
        user_id=user_id,
        job_id=job_id,
        status="pending",
        outfit_items_json=json.dumps([{
            "id": garment.id,
            "image_url": garment.image_url,
            "category": garment.category,
        }]),
    )
    db.add(record)
    db.commit()

    run_tryon_job.delay(job_id)

    return TryOnJobOut(job_id=job_id, status="pending")


@router.get("/try-on/{job_id}", response_model=TryOnResultOut)
def get_tryon_job(job_id: str, db: Session = Depends(get_db)):
    """Poll a try-on job's status."""
    record = db.query(TryOnResult).filter_by(job_id=job_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Job not found")

    return TryOnResultOut(
        job_id=record.job_id,
        status=record.status,
        result_image_url=_sign_result_url(record.result_image_url),
        error_message=record.error_message,
        model_used=record.model_used,
        latency_ms=record.latency_ms,
        created_at=record.created_at.isoformat() if record.created_at else "",
    )


@router.get("/try-on/results/{user_id}", response_model=list[TryOnResultOut])
def list_tryon_results(user_id: int, db: Session = Depends(get_db)):
    """List all try-on results for a user, newest first."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    results = (
        db.query(TryOnResult)
        .filter(TryOnResult.user_id == user_id)
        .order_by(TryOnResult.created_at.desc())
        .all()
    )
    return [
        TryOnResultOut(
            job_id=r.job_id,
            status=r.status,
            result_image_url=_sign_result_url(r.result_image_url),
            error_message=r.error_message,
            model_used=r.model_used,
            latency_ms=r.latency_ms,
            created_at=r.created_at.isoformat() if r.created_at else "",
        )
        for r in results
    ]
