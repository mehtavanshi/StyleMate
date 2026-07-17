"""Shopping provider abstraction + Flipkart affiliate client.

Mirrors the tagging provider pattern: a single ``SHOPPING_PROVIDER`` config
constant selects the active backend, so additional providers (e.g. Amazon,
Myntra) can be added later without touching calling code.
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

# Primary shopping provider: Flipkart affiliate API.
SHOPPING_PROVIDER = os.environ.get("SHOPPING_PROVIDER", "flipkart")
FLIPKART_AFFILIATE_ID = os.environ.get("FLIPKART_AFFILIATE_ID")
FLIPKART_AFFILIATE_TOKEN = os.environ.get("FLIPKART_AFFILIATE_TOKEN")
FLIPKART_API_BASE = os.environ.get(
    "FLIPKART_API_BASE",
    "https://affiliate-api.flipkart.net/affiliate/1.0/search.json",
)

# Meesho has no public product API; the provider only builds a deep link to
# its search-results page for the query string.
MEESHO_SEARCH_URL = os.environ.get(
    "MEESHO_SEARCH_URL", "https://www.meesho.com/search"
)


class Product(BaseModel):
    name: str
    image_url: str
    price: float
    currency: str = "INR"
    affiliate_link: str
    source: str = "flipkart"


def _is_retryable(exc: BaseException) -> bool:
    """Retry only on 429 (rate limit) and 5xx (server errors)."""
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        return status == 429 or status >= 500
    return False


class ShoppingProvider(ABC):
    """Abstract base class for shopping/search providers."""

    @abstractmethod
    async def search(self, query: str) -> list[Product]:
        """Return products matching ``query``."""
        raise NotImplementedError


class FlipkartProvider(ShoppingProvider):
    """Flipkart affiliate product search via the affiliate API.

    Requires ``FLIPKART_AFFILIATE_ID`` and ``FLIPKART_AFFILIATE_TOKEN``.
    When either is missing the provider still constructs (so config is
    valid) but ``search`` returns an empty list and logs a warning, rather
    than raising on import.

    Results are cached per normalized query (30 min TTL, 500 entries) and
    failed requests are retried with exponential backoff (only on 429 / 5xx).
    """

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
        except Exception as exc:  # all retries exhausted
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
            # Raises httpx.HTTPStatusError on 4xx/5xx; retry predicate only
            # allows 429 and 5xx through, so other 4xx fail fast.
            resp.raise_for_status()
            return resp.json()


def _parse_flipkart_response(payload: dict) -> list[Product]:
    """Extract ``Product`` records from a Flipkart affiliate search response.

    The affiliate search JSON nests results under ``products`` with a
    ``productBaseInfoV1`` block containing the display attributes.
    """
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
    """Meesho deep-link fallback.

    Meesho exposes no public product-search API, so this provider makes no
    network call. Instead it returns a single ``Product`` whose
    ``affiliate_link`` deep-links to Meesho's search-results page for the
    query. The link is cached per normalized query like the other providers.
    """

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


def get_shopping_provider() -> ShoppingProvider:
    """Return the configured shopping provider instance.

    Selected via the ``SHOPPING_PROVIDER`` env var (defaults to "flipkart").
    """
    provider = SHOPPING_PROVIDER
    if provider == "flipkart":
        return FlipkartProvider()
    if provider == "meesho":
        return MeeshoProvider()
    raise ValueError(f"Unknown SHOPPING_PROVIDER: {provider!r}")
