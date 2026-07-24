from fastapi import APIRouter, File, HTTPException, UploadFile

from app.storage import get_storage_provider

router = APIRouter(tags=["upload"])

ALLOWED_TYPES = {
    "image/jpeg", "image/png", "image/gif", "image/webp",
    "image/heic", "image/heif",
}
MAX_SIZE_MB = 10


@router.post("/upload-image")
async def upload_image(file: UploadFile = File(...)):
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type: {file.content_type}. "
            f"Allowed: {', '.join(sorted(ALLOWED_TYPES))}",
        )

    content = await file.read()
    size_mb = len(content) / (1024 * 1024)
    if size_mb > MAX_SIZE_MB:
        raise HTTPException(
            status_code=400,
            detail=f"File too large: {size_mb:.1f}MB. Max allowed is {MAX_SIZE_MB}MB.",
        )

    provider = get_storage_provider()
    storage_key = provider.save_file(content, file.filename or "upload", file.content_type)
    image_url = provider.get_file_url(storage_key)

    return {"image_url": image_url}
