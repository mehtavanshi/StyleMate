"""
Try-on service with provider abstraction.

TRYON_PROVIDER env var selects the active provider at startup:
  - "self_hosted" (default): calls a self-hosted inference endpoint
  - "fashn": uses Fashn.ai API
  - "kling": uses Kling API
  - "free_hf_space": free public Hugging Face Space via gradio_client

All providers read credentials from environment variables — never hardcoded.
"""

import asyncio
import base64
import hashlib
import logging
import os
import random
import tempfile
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

class ProviderUnavailableError(TryOnError):
    """Free provider is cold-starting, rate-limited, or the Space is down.

    Unlike transient errors (TryOnTimeoutError etc.) this is NOT retried
    automatically — a shared free resource should not be hammered.
    """


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

# Maps DB clothing item category → try-on API category.
# "top" and "outerwear" both use "upper_body" for the API,
# but are kept distinct here so render_outfit() can order passes correctly.
CATEGORY_TRYON_MAP: dict[str, str] = {
    "top": "upper_body",
    "outerwear": "upper_body",
    "bottom": "lower_body",
    "dress": "dresses/full_body",
}

# Categories that participate in multi-pass try-on (order matters).
_OUTFIT_ORDER: list[str] = ["top", "bottom", "outerwear"]

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


# ── FAL Provider ──
# Uses FAL.ai's hosted IDM-VTON endpoint (or similar).
# Set FAL_KEY env var for authentication.

class FalProvider(TryOnProvider):
    """Calls FAL.ai's hosted virtual try-on API (IDM-VTON)."""

    MODEL = os.getenv("TRYON_FAL_MODEL", "fal-ai/idm-vton")
    TIMEOUT = int(os.getenv("TRYON_FAL_TIMEOUT", "120"))

    def __init__(self) -> None:
        self.api_key = os.getenv("FAL_KEY", "")
        if not self.api_key:
            logger.warning("FAL_KEY not set — FalProvider will fail at runtime")

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
            async with httpx.AsyncClient(timeout=self.TIMEOUT) as client:
                resp = await client.post(
                    f"https://fal.run/{self.MODEL}",
                    headers={
                        "Authorization": f"Key {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "human_image_url": user_signed,
                        "garment_image_url": garment_signed,
                    },
                )
        except httpx.ConnectError as exc:
            raise TryOnProviderDownError(f"Cannot reach FAL API: {exc}")
        except httpx.TimeoutException as exc:
            raise TryOnTimeoutError(f"FAL request timed out: {exc}")

        if resp.status_code in (400, 422):
            raise TryOnInputError(resp.text)
        if resp.status_code in (401, 403):
            raise TryOnAuthError(resp.text)
        if resp.status_code == 429:
            raise TryOnRateLimitError(resp.text)
        if resp.status_code >= 500:
            raise TryOnProviderDownError(f"FAL returned {resp.status_code}: {resp.text}")
        resp.raise_for_status()

        data = resp.json()
        images = data.get("images", [])
        if not images:
            raise TryOnProviderDownError("FAL returned no images")
        result_url = images[0].get("url", "")
        if not result_url:
            raise TryOnProviderDownError("FAL image URL is empty")

        try:
            async with httpx.AsyncClient(timeout=60) as dl:
                img_resp = await dl.get(result_url)
        except httpx.ConnectError as exc:
            raise TryOnProviderDownError(f"Cannot download FAL result: {exc}")
        except httpx.TimeoutException as exc:
            raise TryOnTimeoutError(f"FAL result download timed out: {exc}")
        img_resp.raise_for_status()

        result_key = provider.save_file(img_resp.content, "tryon_result.png", "image/png")
        signed = provider.get_signed_url(result_key)

        return RenderResult(
            result_image_url=signed,
            result_storage_key=result_key,
            model_used="fal",
            category=category,
        )


# ── FreeSelfHostedProvider ──
# Calls a public Hugging Face Space via gradio_client.
# Reads images from local storage (gradio_client needs local file paths),
# uploads result back to our storage bucket.
# Images are preprocessed to 768×1024 to match IDM-VTON's expected input.

import io as _io  # for in-memory PNG encoding

class FreeSelfHostedProvider(TryOnProvider):
    """Virtual try-on via a free public Hugging Face Space."""

    PERSON_WIDTH = 768
    PERSON_HEIGHT = 1024
    GARMENT_WIDTH = 768
    GARMENT_HEIGHT = 1024
    RETRY_WAIT_SECONDS = 45

    GARMENT_DESC_MAP: dict[str, str] = {
        "upper_body": "a top",
        "lower_body": "a bottom",
        "dresses/full_body": "a dress",
    }

    def __init__(self) -> None:
        self.space_id = os.getenv("FREE_PROVIDER_SPACE_ID", "")
        self.hf_token = os.getenv("HF_TOKEN", "")
        self.timeout = int(os.getenv("FREE_PROVIDER_SPACE_TIMEOUT", "90"))
        if not self.space_id:
            logger.warning(
                "FREE_PROVIDER_SPACE_ID not set — "
                "FreeSelfHostedProvider will fail at runtime"
            )
        if not self.hf_token:
            logger.warning(
                "HF_TOKEN not set — FreeSelfHostedProvider may be rejected by the Space"
            )

    @staticmethod
    def _space_url(space_id: str) -> str:
        """Convert 'user/space-name' → 'https://user-space-name.hf.space'."""
        slug = space_id.replace("/", "-").replace("_", "-").lower()
        return f"https://{slug}.hf.space"

    async def _wake_space(self) -> None:
        """Send a lightweight GET to the Space URL to trigger GPU wake-up."""
        url = self._space_url(self.space_id)
        headers = {"Authorization": f"Bearer {self.hf_token}"} if self.hf_token else {}
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(url, headers=headers)
                logger.info("HF Space wake-up ping → %s (HTTP %d)", url, resp.status_code)
        except Exception as exc:
            logger.warning("HF Space wake-up ping failed: %s", exc)

    def _is_cold_start_error(self, exc: Exception) -> bool:
        """Check if the error indicates the Space's GPU is not yet ready."""
        exc_str = str(exc).lower()
        return any(kw in exc_str for kw in (
            "accelerator", "cold", "starting", "booting", "no gpu", "gpu not",
        ))

    @staticmethod
    def _resize_and_center_crop(
        img_bytes: bytes, target_w: int, target_h: int
    ) -> bytes:
        """Resize image to exact target dimensions using center-crop strategy.

        1. Scale so the image fully covers the target rectangle (no black bars).
        2. Center-crop to exact target dimensions.
        3. Encode as PNG and return bytes.
        """
        from PIL import Image

        img = Image.open(_io.BytesIO(img_bytes)).convert("RGB")
        src_w, src_h = img.size

        if src_w == target_w and src_h == target_h:
            return img_bytes

        # Scale to cover the target rectangle
        scale = max(target_w / src_w, target_h / src_h)
        new_w = int(src_w * scale)
        new_h = int(src_h * scale)
        img = img.resize((new_w, new_h), Image.LANCZOS)

        # Center-crop to exact target
        left = (new_w - target_w) // 2
        top_crop = (new_h - target_h) // 2
        img = img.crop((left, top_crop, left + target_w, top_crop + target_h))

        buf = _io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()

    async def render(
        self,
        user_photo_url: str,
        garment_image_url: str,
        category: str,
    ) -> RenderResult:
        from gradio_client import Client, handle_file  # lazy import (optional dep)

        provider = get_storage_provider()
        user_bytes = provider.read_file(user_photo_url)
        garment_bytes = provider.read_file(garment_image_url)

        user_bytes = self._resize_and_center_crop(
            user_bytes, self.PERSON_WIDTH, self.PERSON_HEIGHT
        )
        garment_bytes = self._resize_and_center_crop(
            garment_bytes, self.GARMENT_WIDTH, self.GARMENT_HEIGHT
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            user_path = os.path.join(tmp_dir, "user_photo.png")
            garment_path = os.path.join(tmp_dir, "garment_image.png")

            with open(user_path, "wb") as f:
                f.write(user_bytes)
            with open(garment_path, "wb") as f:
                f.write(garment_bytes)

            garment_des = self.GARMENT_DESC_MAP.get(category, "a top")
            seed = random.randint(0, 2**31 - 1)

            logger.info(
                "HF try-on: category=%s garment_des='%s' seed=%d "
                "person=%dx%d garment=%dx%d",
                category, garment_des, seed,
                self.PERSON_WIDTH, self.PERSON_HEIGHT,
                self.GARMENT_WIDTH, self.GARMENT_HEIGHT,
            )

            # Ping the Space to trigger GPU wake-up before creating client
            await self._wake_space()

            result = await self._try_predict(
                user_path, garment_path, garment_des, seed
            )

            # predict() returns (output_image, masked_image) — we want the first
            output = result[0] if isinstance(result, tuple) else result

            # output may be a URL or a local file path returned by the Space
            if isinstance(output, str) and output.startswith("http"):
                img_resp = httpx.get(output, timeout=60)
                img_resp.raise_for_status()
                img_bytes = img_resp.content
            else:
                with open(output, "rb") as f:
                    img_bytes = f.read()

            result_key = provider.save_file(
                img_bytes, "tryon_result.png", "image/png"
            )
            signed = provider.get_signed_url(result_key)

            return RenderResult(
                result_image_url=signed,
                result_storage_key=result_key,
                model_used="free_hf_space",
                category=category,
            )

    async def _try_predict(
        self, user_path: str, garment_path: str, garment_des: str, seed: int
    ):
        """Call predict() with one retry for cold-start / accelerator errors."""
        from gradio_client import Client, handle_file  # lazy import
        from gradio_client.exceptions import AppError

        for attempt in range(2):
            try:
                client = Client(
                    self.space_id,
                    token=self.hf_token or None,
                    httpx_kwargs={"timeout": self.timeout},
                )
                logger.info(
                    "HF predict attempt %d/2: garment_des='%s' seed=%d",
                    attempt + 1, garment_des, seed,
                )
                result = await asyncio.to_thread(
                    lambda: client.predict(
                        dict={
                            "background": handle_file(user_path),
                            "layers": [],
                            "composite": handle_file(user_path),
                        },
                        garm_img=handle_file(garment_path),
                        garment_des=garment_des,
                        is_checked=True,
                        is_checked_crop=False,
                        denoise_steps=30,
                        seed=seed,
                        api_name="/tryon",
                    )
                )
                return result

            except AppError as exc:
                exc_str = str(exc).lower()
                if any(kw in exc_str for kw in ("quota", "zerogpu", "try again in")):
                    raise ProviderUnavailableError(
                        f"HF Space quota exhausted: {exc}"
                    ) from exc
                raise

            except Exception as exc:
                exc_str = str(exc).lower()
                if isinstance(exc, (httpx.TimeoutException, httpx.ConnectError)):
                    raise ProviderUnavailableError(
                        f"HF Space unavailable (network): {exc}"
                    ) from exc

                is_cold = self._is_cold_start_error(exc)
                if is_cold and attempt == 0:
                    logger.warning(
                        "HF Space cold-start detected (attempt 1/2), "
                        "retrying in %ds...",
                        self.RETRY_WAIT_SECONDS,
                    )
                    await asyncio.sleep(self.RETRY_WAIT_SECONDS)
                    continue

                if any(kw in exc_str for kw in (
                    "timeout", "queue", "unavailable", "busy",
                )):
                    raise ProviderUnavailableError(
                        f"HF Space unavailable: {exc}"
                    ) from exc

                if is_cold:
                    raise ProviderUnavailableError(
                        f"HF Space GPU unavailable after retry. "
                        f"Please try again in a few minutes."
                    ) from exc

                raise


# ── GeminiTryOnProvider ──
# Uses the Gemini API's generateContent endpoint with responseModalities
# ["TEXT", "IMAGE"] to produce a virtual try-on result.

class GeminiTryOnProvider(TryOnProvider):
    DEFAULT_MODEL = "gemini-2.5-flash-image"
    PRO_MODEL = "gemini-3-pro-image-preview"
    BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"
    TIMEOUT = int(os.getenv("TRYON_GEMINI_TIMEOUT", "120"))

    def __init__(self) -> None:
        self.api_key = os.getenv("GEMINI_IMAGE_API_KEY", "")
        if not self.api_key:
            logger.warning(
                "GEMINI_IMAGE_API_KEY not set — GeminiTryOnProvider will fail at runtime"
            )
        self.model = os.getenv("TRYON_GEMINI_MODEL", self.DEFAULT_MODEL)

    async def render(
        self,
        user_photo_url: str,
        garment_image_url: str,
        category: str,
    ) -> RenderResult:
        storage = get_storage_provider()

        user_bytes = await self._load_image(user_photo_url, storage)
        garment_bytes = await self._load_image(garment_image_url, storage)

        user_b64 = base64.b64encode(user_bytes).decode()
        garment_b64 = base64.b64encode(garment_bytes).decode()

        prompt = self._build_prompt(category)

        b64_result = await self._generate_image(user_b64, garment_b64, prompt)
        img_bytes = base64.b64decode(b64_result)

        result_key = storage.save_file(img_bytes, "tryon_result.png", "image/png")
        signed = storage.get_signed_url(result_key)

        return RenderResult(
            result_image_url=signed,
            result_storage_key=result_key,
            model_used=self.model,
            category=category,
        )

    async def _load_image(self, url_or_key: str, storage) -> bytes:
        if url_or_key.startswith("http"):
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(url_or_key)
                resp.raise_for_status()
                return resp.content
        return storage.read_file(url_or_key)

    def _build_prompt(self, category: str) -> str:
        garment_desc = {
            "upper_body": "a top",
            "lower_body": "bottom clothing",
            "dresses/full_body": "a dress",
        }.get(category, "a garment")
        return (
            "You are a professional virtual try-on system. "
            f"I will show you a photo of a person and {garment_desc}. "
            "Please dress the person in the exact garment shown, preserving their face, body, and identity exactly. "
            "Maintain the exact color, pattern, logo, and texture of the garment. "
            "Match the lighting and framing of the original photo. "
            "Produce a full-body, studio-quality result."
        )

    async def _generate_image(self, user_b64: str, garment_b64: str, prompt: str) -> str:
        url = f"{self.BASE_URL}/{self.model}:generateContent?key={self.api_key}"
        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": prompt},
                        {"inlineData": {"mimeType": "image/jpeg", "data": user_b64}},
                        {"inlineData": {"mimeType": "image/jpeg", "data": garment_b64}},
                    ]
                }
            ],
            "generationConfig": {
                "responseModalities": ["TEXT", "IMAGE"],
            },
        }

        try:
            async with httpx.AsyncClient(timeout=self.TIMEOUT) as client:
                resp = await client.post(url, json=payload)
        except httpx.ConnectError as exc:
            raise TryOnProviderDownError(f"Cannot reach Gemini API: {exc}")
        except httpx.TimeoutException:
            raise TryOnTimeoutError("Gemini request timed out")

        if resp.status_code in (400, 422):
            raise TryOnInputError(resp.text)
        if resp.status_code in (401, 403):
            raise TryOnAuthError(resp.text)
        if resp.status_code == 429:
            raise TryOnRateLimitError(resp.text)
        if resp.status_code >= 500:
            raise TryOnProviderDownError(
                f"Gemini API returned {resp.status_code}: {resp.text}"
            )
        resp.raise_for_status()

        data = resp.json()
        for candidate in data.get("candidates", []):
            for part in candidate.get("content", {}).get("parts", []):
                if "inlineData" in part:
                    return part["inlineData"]["data"]

        finish_reason = data.get("candidates", [{}])[0].get("finishReason", "")
        if finish_reason in ("SAFETY", "RECITATION"):
            raise TryOnInputError(
                f"Gemini blocked the image: {finish_reason}"
            )
        raise TryOnProviderDownError("Gemini returned no image in response")


# ── Provider factory ──
# Reads TRYON_PROVIDER at import time (startup), not per-request.

_PROVIDER_INSTANCE: TryOnProvider | None = None


def get_try_on_provider() -> TryOnProvider:
    """Return the active try-on provider (cached after first call)."""
    global _PROVIDER_INSTANCE
    if _PROVIDER_INSTANCE is not None:
        return _PROVIDER_INSTANCE

    name = os.getenv("TRYON_PROVIDER", "fal").lower()
    if name == "fashn":
        _PROVIDER_INSTANCE = FashnProvider()
    elif name == "kling":
        _PROVIDER_INSTANCE = KlingProvider()
    elif name == "fal":
        _PROVIDER_INSTANCE = FalProvider()
    elif name == "free_hf_space":
        if not os.getenv("FREE_PROVIDER_SPACE_ID"):
            logger.warning(
                "FREE_PROVIDER_SPACE_ID is not set — "
                "FreeSelfHostedProvider calls will fail"
            )
        logger.warning(
            "Using free non-commercial try-on provider — not licensed for "
            "commercial use, no uptime SLA. Switch TRYON_PROVIDER before launch."
        )
        _PROVIDER_INSTANCE = FreeSelfHostedProvider()
    elif name == "gemini":
        if not os.getenv("GEMINI_IMAGE_API_KEY"):
            logger.warning(
                "GEMINI_IMAGE_API_KEY is not set — "
                "GeminiTryOnProvider calls will fail"
            )
        _PROVIDER_INSTANCE = GeminiTryOnProvider()
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


# ── Outfit orchestration ──
# Renders multiple garments in sequence (top → bottom → outerwear).
# Each pass feeds its result back as the "person" photo for the next pass.
# Dress garments use a single pass and skip all other categories.

async def render_outfit(
    user_photo_url: str,
    garments: list[dict],
) -> RenderResult:
    """Render an outfit (1-3 garments) onto a user photo.

    Each garment dict must have: id, image_url, category (DB category).
    - dress: single pass (dresses/full_body), ignores other garments.
    - top + bottom + outerwear: sequential passes in that order.
    - partial combos (e.g. just top+bottom) work too.

    Returns the final RenderResult after all passes.
    Raises TryOnError on failure.
    """
    # Categorize garments
    top = None
    bottom = None
    outerwear = None
    dress = None

    for g in garments:
        db_cat = g.get("category", "")
        if db_cat == "dress":
            dress = g
        elif db_cat == "top" and top is None:
            top = g
        elif db_cat == "outerwear":
            outerwear = g
        elif db_cat == "bottom" and bottom is None:
            bottom = g

    provider = get_try_on_provider()

    garment_summary = " | ".join(
        f"id={g['id']} cat={g['category']}" for g in garments
    )
    logger.info("render_outfit: %d garment(s): %s", len(garments), garment_summary)

    # Dress → single pass
    if dress:
        cat = CATEGORY_TRYON_MAP["dress"]
        logger.info("render_outfit PASS 1/1: dress %s → %s", dress["id"], cat)
        return await _render_with_retry(provider, user_photo_url, dress["image_url"], cat)

    # Multi-pass: top → bottom → outerwear
    current_photo = user_photo_url
    result = None
    total_passes = (1 if top else 0) + (1 if bottom else 0) + (1 if outerwear else 0)
    pass_num = 0

    if top:
        pass_num += 1
        cat = CATEGORY_TRYON_MAP["top"]
        logger.info("render_outfit PASS %d/%d: top %s → %s", pass_num, total_passes, top["id"], cat)
        result = await _render_with_retry(provider, current_photo, top["image_url"], cat)
        current_photo = result.result_storage_key

    if bottom:
        pass_num += 1
        cat = CATEGORY_TRYON_MAP["bottom"]
        logger.info("render_outfit PASS %d/%d: bottom %s → %s", pass_num, total_passes, bottom["id"], cat)
        result = await _render_with_retry(provider, current_photo, bottom["image_url"], cat)
        current_photo = result.result_storage_key

    if outerwear:
        pass_num += 1
        cat = CATEGORY_TRYON_MAP["outerwear"]
        logger.info("render_outfit PASS %d/%d: outerwear %s → %s", pass_num, total_passes, outerwear["id"], cat)
        result = await _render_with_retry(provider, current_photo, outerwear["image_url"], cat)

    if result is None:
        raise TryOnInputError("No valid try-on garments provided")

    return result


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

    # 3. Normalize category (DB category → try-on API category)
    cat = CATEGORY_TRYON_MAP.get(garment_category, "upper_body")

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
