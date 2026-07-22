import asyncio
import json
import logging
import time

from app.celery_app import celery_app
from app.database import SessionLocal
from app.models import TryOnResult, User
from app.try_on_service import (
    TryOnError,
    TryOnInputError,
    TryOnProviderDownError,
    TryOnRateLimitError,
    TryOnTimeoutError,
    render_outfit,
)

logger = logging.getLogger(__name__)


def _save_result(job_id: str, **fields) -> None:
    db = SessionLocal()
    try:
        record = db.query(TryOnResult).filter_by(job_id=job_id).first()
        if not record:
            logger.warning("tryon.task job_id=%s record not found", job_id)
            return
        for k, v in fields.items():
            setattr(record, k, v)
        db.commit()
    finally:
        db.close()


def execute_tryon_job(job_id: str) -> None:
    """Core try-on logic — usable both by Celery and inline fallback."""
    db = SessionLocal()
    record = None
    try:
        record = db.query(TryOnResult).filter_by(job_id=job_id).first()
        if not record:
            return

        _save_result(job_id, status="processing")

        items = json.loads(record.outfit_items_json) if record.outfit_items_json else []

        user = db.query(User).filter(User.id == record.user_id).first()
        if not user or not user.photo_url:
            _save_result(job_id, status="failed", error_message="User or photo not found")
            return

        start = time.time()
        result = asyncio.run(render_outfit(
            user_photo_url=user.photo_url,
            garments=items,
        ))
        latency_ms = int((time.time() - start) * 1000)

        _save_result(
            job_id,
            status="completed",
            result_image_url=result.result_storage_key,
            model_used=result.model_used,
            latency_ms=latency_ms,
        )

        garment_ids_str = ",".join(str(g.get("id", "?")) for g in items)
        logger.info(
            "tryon.render provider=%s garment_ids=%s latency_ms=%d success=True",
            result.model_used, garment_ids_str, latency_ms,
        )

    except TryOnInputError as exc:
        garment_id = _extract_garment_id(record)
        _save_result(job_id, status="failed", error_message=str(exc), error_type="bad_photo")
        logger.info("tryon.render garment_id=%s success=False error=bad_photo", garment_id)

    except (TryOnTimeoutError, TryOnProviderDownError) as exc:
        garment_id = _extract_garment_id(record)
        _save_result(job_id, status="failed", error_message=str(exc), error_type="provider_error")
        logger.info("tryon.render garment_id=%s success=False error=provider_error", garment_id)

    except TryOnRateLimitError as exc:
        garment_id = _extract_garment_id(record)
        _save_result(job_id, status="failed", error_message=str(exc), error_type="rate_limit")
        logger.info("tryon.render garment_id=%s success=False error=rate_limit", garment_id)

    except TryOnError as exc:
        garment_id = _extract_garment_id(record)
        _save_result(job_id, status="failed", error_message=str(exc), error_type="provider_error")
        logger.info("tryon.render garment_id=%s success=False error=provider_error", garment_id)

    except Exception:
        garment_id = _extract_garment_id(record)
        if record:
            _save_result(job_id, status="failed", error_message="Internal error")
        logger.exception("tryon.render unexpected error for job_id=%s garment_id=%s", job_id, garment_id)

    finally:
        db.close()


def _extract_garment_id(record: TryOnResult | None) -> str:
    if record and record.outfit_items_json:
        try:
            return (json.loads(record.outfit_items_json) or [{}])[0].get("id", "?")
        except Exception:
            pass
    return "?"


@celery_app.task(bind=True, max_retries=2, default_retry_delay=10)
def run_tryon_job(self, job_id: str) -> None:
    execute_tryon_job(job_id)
