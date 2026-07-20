"""Shopping provider abstraction + concurrent multi-provider search.

A ``SHOPPING_PROVIDERS`` env var (comma-separated list) selects the active
backends, e.g. ``flipkart,meesho``.  Calling code uses the top-level
``search_all_providers(query)`` function to query all active providers
concurrently via ``asyncio.gather``; each provider's results are returned
tagged with their source platform so callers can distinguish them.
"""

from __future__ import annotations

import logging
import os
from abc import ABC, abstractmethod
from pathlib import Path
from urllib.parse import quote_plus

from cachetools import TTLCache
from dotenv import load_dotenv
from pydantic import BaseModel
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

import httpx

logger = logging.getLogger(__name__)

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

# Active shopping providers — a comma-separated list.
# Default: flipkart, meesho (amazon can be added once eligible).
_SHOPPING_PROVIDERS_RAW = os.environ.get("SHOPPING_PROVIDERS", "flipkart,meesho")
SHOPPING_PROVIDERS = [p.strip() for p in _SHOPPING_PROVIDERS_RAW.split(",") if p.strip()]

FLIPKART_AFFILIATE_ID = os.environ.get("FLIPKART_AFFILIATE_ID")
FLIPKART_AFFILIATE_TOKEN = os.environ.get("FLIPKART_AFFILIATE_TOKEN")
FLIPKART_API_BASE = os.environ.get(
    "FLIPKART_API_BASE",
    "https://affiliate-api.flipkart.net/affiliate/1.0/search.json",
)

MEESHO_SEARCH_URL = os.environ.get(
    "MEESHO_SEARCH_URL", "https://www.meesho.com/search"
)

AMAZON_AFFILIATE_TAG = os.environ.get("AMAZON_AFFILIATE_TAG")
AMAZON_SEARCH_URL = os.environ.get(
    "AMAZON_SEARCH_URL", "https://www.amazon.in/s"
)


class Product(BaseModel):
    name: str
    image_url: str
    price: float
    currency: str = "INR"
    affiliate_link: str
    source: str = "flipkart"


class ProviderResult(BaseModel):
    platform: str
    products: list[Product]


def _is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        return status == 429 or status >= 500
    return False


class ShoppingProvider(ABC):
    @abstractmethod
    async def search(self, query: str) -> list[Product]:
        raise NotImplementedError


class FlipkartProvider(ShoppingProvider):
    def __init__(
        self,
        affiliate_id: str | None = None,
        affiliate_token: str | None = None,
        api_base: str | None = None,
    ) -> None:
        self.affiliate_id = affiliate_id or FLIPKART_AFFILIATE_ID
        self.affiliate_token = affiliate_token or FLIPKART_AFFILIATE_TOKEN
        self.api_base = api_base or FLIPKART_API_BASE
        self._cache: TTLCache = TTLCache(maxsize=500, ttl=1800)

    @staticmethod
    def _normalize_query(query: str) -> str:
        return " ".join((query or "").lower().split())

    async def search(self, query: str) -> list[Product]:
        key = self._normalize_query(query)
        if key in self._cache:
            return self._cache[key]

        if not self.affiliate_id or not self.affiliate_token:
            logger.warning(
                "Flipkart affiliate credentials missing (FLIPKART_AFFILIATE_ID / "
                "FLIPKART_AFFILIATE_TOKEN); returning no products."
            )
            return []

        try:
            payload = await self._fetch(key)
        except Exception as exc:
            logger.error(
                "Flipkart search for %r failed after all retries; returning no "
                "products. Last error: %s",
                query,
                exc,
            )
            return []

        products = _parse_flipkart_response(payload)
        self._cache[key] = products
        return products

    @retry(
        wait=wait_exponential(multiplier=1, min=2, max=10),
        stop=stop_after_attempt(3),
        retry=retry_if_exception(_is_retryable),
        reraise=True,
    )
    async def _fetch(self, query: str) -> dict:
        headers = {
            "Fk-Affiliate-Id": self.affiliate_id,
            "Fk-Affiliate-Token": self.affiliate_token,
            "Accept": "application/json",
        }
        params = {"query": query}

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(self.api_base, params=params, headers=headers)
            resp.raise_for_status()
            return resp.json()


def _parse_flipkart_response(payload: dict) -> list[Product]:
    products: list[Product] = []
    raw_list = payload.get("products") or []

    for entry in raw_list:
        info = (entry or {}).get("productBaseInfoV1")
        if not info:
            continue
        try:
            price_block = info.get("flipkartSellingPrice") or info.get("price") or {}
            price = float(price_block.get("amount", 0))
            currency = price_block.get("currency", "INR")
            products.append(
                Product(
                    name=info.get("title", "Unknown"),
                    image_url=info.get("imageUrls", {}).get("200x200") or "",
                    price=price,
                    currency=currency,
                    affiliate_link=info.get("productUrl", ""),
                    source="flipkart",
                )
            )
        except (TypeError, ValueError) as exc:
            logger.warning("Skipping malformed Flipkart product: %s", exc)
            continue

    return products


class MeeshoProvider(ShoppingProvider):
    def __init__(self, search_url: str | None = None) -> None:
        self.search_url = search_url or MEESHO_SEARCH_URL
        self._cache: TTLCache = TTLCache(maxsize=500, ttl=1800)

    @staticmethod
    def _normalize_query(query: str) -> str:
        return " ".join((query or "").lower().split())

    async def search(self, query: str) -> list[Product]:
        key = self._normalize_query(query)
        if key in self._cache:
            return self._cache[key]

        link = f"{self.search_url}?q={quote_plus(key)}"
        product = Product(
            name=key,
            image_url="",
            price=0.0,
            currency="INR",
            affiliate_link=link,
            source="meesho",
        )
        self._cache[key] = [product]
        return [product]


class AmazonProvider(ShoppingProvider):
    def __init__(
        self,
        affiliate_tag: str | None = None,
        search_url: str | None = None,
    ) -> None:
        self.affiliate_tag = affiliate_tag or AMAZON_AFFILIATE_TAG
        self.search_url = search_url or AMAZON_SEARCH_URL
        self._cache: TTLCache = TTLCache(maxsize=500, ttl=1800)

    @staticmethod
    def _normalize_query(query: str) -> str:
        return " ".join((query or "").lower().split())

    async def search(self, query: str) -> list[Product]:
        key = self._normalize_query(query)
        if key in self._cache:
            return self._cache[key]

        url = f"{self.search_url}?k={quote_plus(key)}"
        if self.affiliate_tag:
            url += f"&tag={quote_plus(self.affiliate_tag)}"

        product = Product(
            name=key,
            image_url="",
            price=0.0,
            currency="INR",
            affiliate_link=url,
            source="amazon",
        )
        self._cache[key] = [product]
        return [product]


# ---------------------------------------------------------------------------
# Provider registry — maps platform name → provider class
# ---------------------------------------------------------------------------
_PROVIDER_CLASSES: dict[str, type[ShoppingProvider]] = {
    "flipkart": FlipkartProvider,
    "meesho": MeeshoProvider,
    "amazon": AmazonProvider,
}


def get_shopping_providers() -> list[ShoppingProvider]:
    """Build and return provider instances for every platform in
    ``SHOPPING_PROVIDERS``.

    Unknown platform names are logged and silently skipped so a typo in the
    env var doesn't crash the application.
    """
    instances: list[ShoppingProvider] = []
    for name in SHOPPING_PROVIDERS:
        cls = _PROVIDER_CLASSES.get(name)
        if cls is None:
            logger.warning(
                "Unknown shopping provider %r in SHOPPING_PROVIDERS; skipping. "
                "Supported: %s",
                name,
                ", ".join(sorted(_PROVIDER_CLASSES)),
            )
            continue
        instances.append(cls())
    return instances


async def search_all_providers(query: str) -> list[ProviderResult]:
    """Search every active provider concurrently.

    Each provider's ``search()`` is run with ``asyncio.gather``.  If a
    single provider fails (exception or timeout) it is caught, logged, and
    returned as an empty product list — other providers are unaffected.

    Returns a list of ``ProviderResult`` objects, one per active provider,
    each tagged with the provider's platform name.
    """
    import asyncio

    providers = get_shopping_providers()
    if not providers:
        logger.warning("No active shopping providers configured.")
        return []

    async def _safe_search(provider: ShoppingProvider, platform: str) -> ProviderResult:
        try:
            products = await provider.search(query)
            return ProviderResult(platform=platform, products=products)
        except Exception as exc:
            logger.error(
                "Shopping provider %r failed for query %r: %s",
                platform,
                query,
                exc,
            )
            return ProviderResult(platform=platform, products=[])

    tasks = [_safe_search(p, name) for p, name in zip(providers, SHOPPING_PROVIDERS)]
    results: list[ProviderResult] = await asyncio.gather(*tasks, return_exceptions=True)

    final: list[ProviderResult] = []
    for r in results:
        if isinstance(r, BaseException):
            logger.error("Unexpected error in search_all_providers gather: %s", r)
            continue
        final.append(r)
    return final
