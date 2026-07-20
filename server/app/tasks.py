import asyncio
import json
import logging
import time

from app.celery_app import celery_app
from app.database import SessionLocal
from app.models import TryOnResult, User
from app.try_on_service import TryOnError, generate_tryon

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


@celery_app.task(bind=True, max_retries=2, default_retry_delay=10)
def run_tryon_job(self, job_id: str) -> None:
    db = SessionLocal()
    record = None
    try:
        record = db.query(TryOnResult).filter_by(job_id=job_id).first()
        if not record:
            return

        _save_result(job_id, status="processing")

        items = json.loads(record.outfit_items_json) if record.outfit_items_json else []
        garment = items[0] if items else {}

        user = db.query(User).filter(User.id == record.user_id).first()
        if not user or not user.photo_url:
            _save_result(job_id, status="failed", error_message="User or photo not found")
            return

        start = time.time()
        result = asyncio.run(generate_tryon(
            user_photo_url=user.photo_url,
            garment_image_url=garment.get("image_url", ""),
            garment_category=garment.get("category", "upper_body"),
        ))
        latency_ms = int((time.time() - start) * 1000)

        _save_result(
            job_id,
            status="completed",
            result_image_url=result.result_storage_key,
            model_used=result.model_used,
            latency_ms=latency_ms,
        )

        logger.info(
            "tryon.render provider=%s garment_id=%s latency_ms=%d success=True",
            result.model_used, garment.get("id"), latency_ms,
        )

    except TryOnError as exc:
        garment_id = "?"
        if record and record.outfit_items_json:
            try:
                garment_id = (json.loads(record.outfit_items_json) or [{}])[0].get("id", "?")
            except Exception:
                pass
        _save_result(job_id, status="failed", error_message=str(exc))
        logger.info("tryon.render garment_id=%s success=False error=%s", garment_id, exc)

    except Exception:
        garment_id = "?"
        if record and record.outfit_items_json:
            try:
                garment_id = (json.loads(record.outfit_items_json) or [{}])[0].get("id", "?")
            except Exception:
                pass
        if record:
            _save_result(job_id, status="failed", error_message="Internal error")
        logger.exception("tryon.render unexpected error for job_id=%s garment_id=%s", job_id, garment_id)

    finally:
        db.close()
