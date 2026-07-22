import json
import logging
import os
import uuid
from datetime import date, datetime, time, timedelta, timezone

from pydantic import BaseModel
from sqlalchemy import text

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ClothingItem, TryOnResult, User
from app.schemas import TryOnResultOut
from app.storage import get_storage_provider
from app.tasks import execute_tryon_job, run_tryon_job

logger = logging.getLogger(__name__)

router = APIRouter(tags=["try-on"])


# ── Request/Response models ──

class TryOnRenderIn(BaseModel):
    garment_ids: list[int]


class TryOnJobOut(BaseModel):
    job_id: str
    status: str
    rate_limit_remaining: int | None = None
    rate_limit_limit: int | None = None
    rate_limit_resets_at: str | None = None


class TryOnUsageOut(BaseModel):
    used: int
    limit: int
    remaining: int
    resets_at: str


# ── Helpers ──

SIGNED_URL_EXPIRY = 300


def _sign_result_url(storage_key: str | None) -> str | None:
    if not storage_key:
        return None
    return get_storage_provider().get_signed_url(storage_key, expires_in=SIGNED_URL_EXPIRY)


def _get_tryon_usage(db: Session, user_id: int) -> tuple[int, int, str]:
    """Return (used, daily_limit, resets_at_iso) for the current day."""
    today = date.today()
    daily_limit = int(os.getenv("TRYON_DAILY_LIMIT", "5"))
    used = db.query(TryOnResult).filter(
        TryOnResult.user_id == user_id,
        TryOnResult.status == "completed",
        TryOnResult.created_at >= datetime.combine(today, time.min, tzinfo=timezone.utc),
    ).count()
    resets_at = datetime.combine(
        today + timedelta(days=1), time.min, tzinfo=timezone.utc
    ).isoformat()
    return used, daily_limit, resets_at


def _dispatch_tryon_job(job_id: str) -> None:
    """Try Celery first; fall back to a background thread when Redis is unavailable."""
    try:
        run_tryon_job.delay(job_id)
    except Exception:
        logger.warning("Celery unavailable, running try-on job %s in background thread", job_id)
        import threading
        t = threading.Thread(target=execute_tryon_job, args=(job_id,), daemon=True)
        t.start()


# ── Endpoints ──

@router.get("/try-on/usage/{user_id}", response_model=TryOnUsageOut)
def get_tryon_usage(user_id: int, db: Session = Depends(get_db)):
    """Return the current daily try-on usage for a user."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    used, limit, resets_at = _get_tryon_usage(db, user_id)
    return TryOnUsageOut(
        used=used,
        limit=limit,
        remaining=max(limit - used, 0),
        resets_at=resets_at,
    )


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

    # ── Rate limit check ──
    usage_count, daily_limit, resets_at = _get_tryon_usage(db, user_id)

    if usage_count >= daily_limit:
        raise HTTPException(
            status_code=429,
            detail={
                "error": "rate_limit_exceeded",
                "message": f"Daily try-on limit exceeded ({daily_limit}/day). Resets at midnight UTC.",
                "limit": daily_limit,
                "used": usage_count,
                "resets_at": resets_at,
            },
        )

    # Validate all garments
    if not body.garment_ids:
        raise HTTPException(status_code=400, detail="garment_ids must not be empty")

    garments_data = []
    for gid in body.garment_ids:
        garment = db.query(ClothingItem).filter(ClothingItem.id == gid).first()
        if not garment:
            raise HTTPException(status_code=404, detail=f"Garment {gid} not found")
        if garment.user_id != user_id:
            raise HTTPException(status_code=403, detail=f"Garment {gid} does not belong to you")
        if not garment.image_url:
            raise HTTPException(status_code=400, detail=f"Garment {gid} has no image")
        garments_data.append({
            "id": garment.id,
            "image_url": garment.image_url,
            "category": garment.category,
        })

    job_id = str(uuid.uuid4())
    record = TryOnResult(
        user_id=user_id,
        job_id=job_id,
        status="pending",
        outfit_items_json=json.dumps(garments_data),
    )
    db.add(record)
    db.commit()

    _dispatch_tryon_job(job_id)

    remaining = daily_limit - usage_count - 1  # -1 because this job will count
    return TryOnJobOut(
        job_id=job_id,
        status="pending",
        rate_limit_remaining=max(remaining, 0),
        rate_limit_limit=daily_limit,
        rate_limit_resets_at=resets_at,
    )


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
        error_type=record.error_type,
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
            error_type=r.error_type,
            model_used=r.model_used,
            latency_ms=r.latency_ms,
            created_at=r.created_at.isoformat() if r.created_at else "",
        )
        for r in results
    ]
