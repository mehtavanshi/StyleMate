"""
Try-on service with provider abstraction.

TRYON_PROVIDER env var selects the active provider at startup:
  - "self_hosted" (default): calls a self-hosted inference endpoint
  - "fashn": uses Fashn.ai API
  - "kling": uses Kling API

All providers read credentials from environment variables — never hardcoded.
"""

import asyncio
import hashlib
import logging
import os
import time
from abc import ABC, abstractmethod

import httpx
from cachetools import TTLCache
from pydantic import BaseModel
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from app.storage import get_storage_provider

logger = logging.getLogger(__name__)


# ── Error types ──
# These map to distinct user-facing messages in the endpoint layer.

class TryOnError(Exception):
    """Base try-on error."""

class TryOnInputError(TryOnError):
    """Bad input — photo or garment was rejected by the provider."""

class TryOnAuthError(TryOnError):
    """Invalid or missing API key."""

class TryOnTimeoutError(TryOnError):
    """Provider request timed out."""

class TryOnProviderDownError(TryOnError):
    """Provider returned a 5xx or network error."""

class TryOnRateLimitError(TryOnError):
    """Provider returned 429 — too many requests."""


# ── Result model ──

class RenderResult(BaseModel):
    result_image_url: str
    result_storage_key: str
    model_used: str
    category: str
    cached: bool = False


# ── Normalized categories ──
# The caller (product catalog) passes these values.  They map to each
# provider's expected format internally.

VALID_CATEGORIES = frozenset({"upper_body", "lower_body", "dresses/full_body"})

FASHN_CATEGORY_MAP: dict[str, str] = {
    "upper_body": "upper_body",
    "lower_body": "lower_body",
    "dresses/full_body": "dresses",
}
KLING_CATEGORY_MAP: dict[str, str] = {
    "upper_body": "upper_body",
    "lower_body": "lower_body",
    "dresses/full_body": "dresses/full_body",
}


# ── Photo hashing ──
# Keyed off storage key so re-uploading a photo produces a different hash
# and automatically invalidates old cached renders.

_photo_hash_cache: TTLCache = TTLCache(maxsize=100, ttl=300)


def _hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _compute_photo_hash(photo_storage_key: str) -> str:
    """SHA-256 of the photo file content.  Result cached 5 min per key."""
    cached = _photo_hash_cache.get(photo_storage_key)
    if cached:
        return cached

    provider = get_storage_provider()
    data = provider.read_file(photo_storage_key)
    h = _hash_bytes(data)
    _photo_hash_cache[photo_storage_key] = h
    return h


# ── Render cache ──
# In-memory TTL cache keyed by f"{photo_hash}:{garment_image_url}".

CACHE_TTL_SECONDS = int(os.getenv("TRYON_CACHE_TTL_SECONDS", str(7 * 24 * 3600)))
_render_cache: TTLCache = TTLCache(maxsize=500, ttl=CACHE_TTL_SECONDS)


# ── Provider interface ──

class TryOnProvider(ABC):
    """Abstract try-on provider."""

    @abstractmethod
    async def render(
        self,
        user_photo_url: str,
        garment_image_url: str,
        category: str,
    ) -> RenderResult:
        ...


# ── SelfHostedProvider ──
# Calls a self-hosted inference endpoint (IDM-VTON / CatVTON / etc.).

class SelfHostedProvider(TryOnProvider):
    def __init__(self) -> None:
        self.endpoint = os.getenv("TRYON_SELF_HOSTED_URL", "http://localhost:8001/render")
        self.timeout = int(os.getenv("TRYON_SELF_HOSTED_TIMEOUT", "60"))

    async def render(
        self,
        user_photo_url: str,
        garment_image_url: str,
        category: str,
    ) -> RenderResult:
        provider = get_storage_provider()
        user_signed = provider.get_signed_url(user_photo_url)
        garment_signed = provider.get_signed_url(garment_image_url)

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(
                    self.endpoint,
                    json={
                        "model_image_url": user_signed,
                        "garment_image_url": garment_signed,
                        "category": category,
                    },
                )
        except httpx.ConnectError as exc:
            raise TryOnProviderDownError(f"Cannot reach self-hosted endpoint: {exc}")
        except httpx.TimeoutException as exc:
            raise TryOnTimeoutError(f"Self-hosted endpoint timed out: {exc}")

        if resp.status_code in (400, 422):
            raise TryOnInputError(resp.text)
        if resp.status_code in (401, 403):
            raise TryOnAuthError(resp.text)
        if resp.status_code == 429:
            raise TryOnRateLimitError(resp.text)
        if resp.status_code >= 500:
            raise TryOnProviderDownError(
                f"Self-hosted endpoint returned {resp.status_code}: {resp.text}"
            )
        resp.raise_for_status()

        result_key = provider.save_file(resp.content, "tryon_result.png", "image/png")
        result_url = provider.get_signed_url(result_key)

        return RenderResult(
            result_image_url=result_url,
            result_storage_key=result_key,
            model_used="self_hosted",
            category=category,
        )


# ── FashnProvider ──
# https://docs.fashn.ai/

class FashnProvider(TryOnProvider):
    BASE_URL = "https://api.fashn.ai/v1"
    POLL_INTERVAL = 2

    def __init__(self) -> None:
        self.api_key = os.getenv("TRYON_FASHN_API_KEY", "")
        if not self.api_key:
            logger.warning("TRYON_FASHN_API_KEY not set — FashnProvider will fail at runtime")
        self.timeout = int(os.getenv("TRYON_FASHN_TIMEOUT", "120"))

    async def _submit_job(self, model_url: str, garment_url: str, category: str) -> str:
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(
                    f"{self.BASE_URL}/run",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json={
                        "model_image": model_url,
                        "garment_image": garment_url,
                        "category": FASHN_CATEGORY_MAP.get(category, category),
                        "mode": "quality",
                    },
                )
        except httpx.ConnectError as exc:
            raise TryOnProviderDownError(f"Cannot reach Fashn API: {exc}")
        except httpx.TimeoutException as exc:
            raise TryOnTimeoutError(f"Fashn submit timed out: {exc}")

        if resp.status_code == 400:
            raise TryOnInputError(resp.text)
        if resp.status_code == 401:
            raise TryOnAuthError(resp.text)
        if resp.status_code == 429:
            raise TryOnRateLimitError(resp.text)
        if resp.status_code >= 500:
            raise TryOnProviderDownError(resp.text)
        resp.raise_for_status()

        data = resp.json()
        if data.get("status") == "completed":
            return data["output"][0]
        return data["id"]

    async def _poll_job(self, job_id: str) -> str:
        deadline = time.monotonic() + self.timeout
        while time.monotonic() < deadline:
            await asyncio.sleep(self.POLL_INTERVAL)
            try:
                async with httpx.AsyncClient(timeout=30) as client:
                    resp = await client.get(
                        f"{self.BASE_URL}/run/{job_id}",
                        headers={"Authorization": f"Bearer {self.api_key}"},
                    )
            except httpx.ConnectError as exc:
                raise TryOnProviderDownError(f"Cannot reach Fashn API: {exc}")
            except httpx.TimeoutException:
                raise TryOnTimeoutError("Fashn poll timed out")
            resp.raise_for_status()
            data = resp.json()
            if data.get("status") == "completed":
                return data["output"][0]
            if data.get("status") == "failed":
                raise TryOnInputError(data.get("error", "Fashn job failed"))
        raise TryOnTimeoutError("Fashn job did not complete within timeout")

    async def render(
        self,
        user_photo_url: str,
        garment_image_url: str,
        category: str,
    ) -> RenderResult:
        provider = get_storage_provider()
        user_signed = provider.get_signed_url(user_photo_url)
        garment_signed = provider.get_signed_url(garment_image_url)

        result_url = await self._submit_job(user_signed, garment_signed, category)
        if not result_url.startswith("http"):
            result_url = await self._poll_job(result_url)

        try:
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.get(result_url)
        except httpx.ConnectError as exc:
            raise TryOnProviderDownError(f"Cannot download Fashn result: {exc}")
        except httpx.TimeoutException as exc:
            raise TryOnTimeoutError(f"Fashn result download timed out: {exc}")
        resp.raise_for_status()

        result_key = provider.save_file(resp.content, "tryon_result.png", "image/png")
        signed = provider.get_signed_url(result_key)

        return RenderResult(
            result_image_url=signed,
            result_storage_key=result_key,
            model_used="fashn",
            category=category,
        )


# ── KlingProvider ──
# https://docs.kling.com/

class KlingProvider(TryOnProvider):
    BASE_URL = "https://api.kling.com/v1/images/virtual-try-on"
    POLL_INTERVAL = 2

    def __init__(self) -> None:
        self.api_key = os.getenv("TRYON_KLING_API_KEY", "")
        self.model = os.getenv("TRYON_KLING_MODEL", "kling-v1.6")
        if not self.api_key:
            logger.warning("TRYON_KLING_API_KEY not set — KlingProvider will fail at runtime")
        self.timeout = int(os.getenv("TRYON_KLING_TIMEOUT", "120"))

    async def _submit_job(self, model_url: str, garment_url: str, category: str) -> str:
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(
                    self.BASE_URL,
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json={
                        "model_image_url": model_url,
                        "garment_image_url": garment_url,
                        "category": KLING_CATEGORY_MAP.get(category, category),
                        "model_name": self.model,
                    },
                )
        except httpx.ConnectError as exc:
            raise TryOnProviderDownError(f"Cannot reach Kling API: {exc}")
        except httpx.TimeoutException as exc:
            raise TryOnTimeoutError(f"Kling submit timed out: {exc}")

        if resp.status_code == 400:
            raise TryOnInputError(resp.text)
        if resp.status_code == 401:
            raise TryOnAuthError(resp.text)
        if resp.status_code == 429:
            raise TryOnRateLimitError(resp.text)
        if resp.status_code >= 500:
            raise TryOnProviderDownError(resp.text)
        resp.raise_for_status()

        data = resp.json()
        task_id = data.get("data", {}).get("task_id")
        if not task_id:
            raise TryOnProviderDownError("Kling did not return a task_id")
        return task_id

    async def _poll_job(self, task_id: str) -> str:
        deadline = time.monotonic() + self.timeout
        while time.monotonic() < deadline:
            await asyncio.sleep(self.POLL_INTERVAL)
            try:
                async with httpx.AsyncClient(timeout=30) as client:
                    resp = await client.get(
                        f"{self.BASE_URL}/{task_id}",
                        headers={"Authorization": f"Bearer {self.api_key}"},
                    )
            except httpx.ConnectError as exc:
                raise TryOnProviderDownError(f"Cannot reach Kling API: {exc}")
            except httpx.TimeoutException:
                raise TryOnTimeoutError("Kling poll timed out")
            resp.raise_for_status()
            data = resp.json()
            status = data.get("data", {}).get("status")
            if status == "succeed":
                return data["data"]["result_image_url"]
            if status == "failed":
                raise TryOnInputError(
                    data.get("data", {}).get("error", "Kling job failed")
                )
        raise TryOnTimeoutError("Kling job did not complete within timeout")

    async def render(
        self,
        user_photo_url: str,
        garment_image_url: str,
        category: str,
    ) -> RenderResult:
        provider = get_storage_provider()
        user_signed = provider.get_signed_url(user_photo_url)
        garment_signed = provider.get_signed_url(garment_image_url)

        task_id = await self._submit_job(user_signed, garment_signed, category)
        result_url = await self._poll_job(task_id)

        try:
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.get(result_url)
        except httpx.ConnectError as exc:
            raise TryOnProviderDownError(f"Cannot download Kling result: {exc}")
        except httpx.TimeoutException as exc:
            raise TryOnTimeoutError(f"Kling result download timed out: {exc}")
        resp.raise_for_status()

        result_key = provider.save_file(resp.content, "tryon_result.png", "image/png")
        signed = provider.get_signed_url(result_key)

        return RenderResult(
            result_image_url=signed,
            result_storage_key=result_key,
            model_used=self.model,
            category=category,
        )


# ── Provider factory ──
# Reads TRYON_PROVIDER at import time (startup), not per-request.

_PROVIDER_INSTANCE: TryOnProvider | None = None


def get_try_on_provider() -> TryOnProvider:
    """Return the active try-on provider (cached after first call)."""
    global _PROVIDER_INSTANCE
    if _PROVIDER_INSTANCE is not None:
        return _PROVIDER_INSTANCE

    name = os.getenv("TRYON_PROVIDER", "self_hosted").lower()
    if name == "fashn":
        _PROVIDER_INSTANCE = FashnProvider()
    elif name == "kling":
        _PROVIDER_INSTANCE = KlingProvider()
    else:
        _PROVIDER_INSTANCE = SelfHostedProvider()

    logger.info("Active try-on provider: %s", type(_PROVIDER_INSTANCE).__name__)
    return _PROVIDER_INSTANCE


# ── Retry logic ──
# Transient errors (timeout, 5xx, 429) get retried with exponential backoff.
# Input errors and auth errors are NOT retried.

def _is_transient(exc: BaseException) -> bool:
    return isinstance(exc, (TryOnTimeoutError, TryOnProviderDownError, TryOnRateLimitError))


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=2, max=30),
    retry=retry_if_exception(_is_transient),
    reraise=True,
)
async def _render_with_retry(
    provider: TryOnProvider,
    user_photo_url: str,
    garment_image_url: str,
    category: str,
) -> RenderResult:
    return await provider.render(
        user_photo_url=user_photo_url,
        garment_image_url=garment_image_url,
        category=category,
    )


# ── Main entry point ──

async def generate_tryon(
    user_photo_url: str,
    garment_image_url: str,
    garment_category: str = "upper_body",
) -> RenderResult:
    """Render a garment onto a user photo.

    Steps:
      1. Hash the user photo for a cache key.
      2. Check the in-memory render cache.
      3. Normalize the garment category.
      4. Call the active provider with retry for transient errors.
      5. Persist the rendered image to object storage.
      6. Cache the result keyed by (photo_hash, garment_image_url).
      7. Return a RenderResult.

    Raises TryOnError subclasses — callers should map these to HTTP responses.
    """
    # 1. Hash photo
    photo_hash = _compute_photo_hash(user_photo_url)
    ck = f"{photo_hash}:{garment_image_url}"

    # 2. Check cache
    cached = _render_cache.get(ck)
    if cached is not None:
        logger.debug("Try-on cache hit for key=%s", ck)
        return RenderResult(**cached, cached=True)

    # 3. Normalize category
    cat = garment_category if garment_category in VALID_CATEGORIES else "upper_body"

    # 4. Render
    try_on_provider = get_try_on_provider()
    result = await _render_with_retry(
        try_on_provider,
        user_photo_url=user_photo_url,
        garment_image_url=garment_image_url,
        category=cat,
    )

    # 5. Cache
    _render_cache[ck] = result.model_dump()

    return result
