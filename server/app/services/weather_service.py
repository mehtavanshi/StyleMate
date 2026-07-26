"""Weather lookup + temperature-appropriate wardrobe filtering.

Needs WEATHER_API_KEY (OpenWeatherMap). Without it ``get_weather`` returns
None and the caller falls back to unfiltered suggestions — the feature
degrades, it never errors.
"""

from __future__ import annotations

import logging
import os

import httpx
from cachetools import TTLCache

from app.retry import call_with_retry

logger = logging.getLogger(__name__)

WEATHER_API_KEY = os.environ.get("WEATHER_API_KEY")
WEATHER_API_URL = os.environ.get(
    "WEATHER_API_URL", "https://api.openweathermap.org/data/2.5/weather"
)
DEFAULT_CITY = os.environ.get("WEATHER_DEFAULT_CITY", "Mumbai")

# Weather changes slowly and the free tier is rate-limited: 30 min per city.
_cache: TTLCache = TTLCache(maxsize=50, ttl=1800)

# (min_c, max_c) → what to wear at that temperature. Ranges are inclusive of
# min, exclusive of max, and cover -10..50°C without gaps.
TEMP_RULES: list[tuple[float, float, dict]] = [
    (30, 60, {"season": "summer", "fabrics": ["cotton", "linen", "silk", "rayon"]}),
    (22, 30, {"season": "summer", "fabrics": ["cotton", "linen", "denim", "rayon"]}),
    (15, 22, {"season": "spring", "fabrics": ["cotton", "denim", "knit", "polyester"]}),
    (8, 15, {"season": "fall", "fabrics": ["cotton", "wool", "denim", "knit"]}),
    (-50, 8, {"season": "winter", "fabrics": ["wool", "leather", "knit", "fleece"]}),
]

# Layers we only suggest when it is genuinely cool.
_WARM_ONLY_CATEGORIES = {"outerwear"}
MAX_OUTERWEAR_TEMP_C = 22.0


def rule_for_temp(temp_c: float) -> dict:
    """Season + fabric guidance for a temperature. Always returns a rule."""
    for low, high, rule in TEMP_RULES:
        if low <= temp_c < high:
            return rule
    return TEMP_RULES[-1][1]


def get_weather(city: str | None = None) -> dict | None:
    """Current conditions for a city, or None when unavailable.

    Shape: {"city", "temp_c", "condition", "humidity", "icon"}.
    """
    target = city or DEFAULT_CITY
    if not WEATHER_API_KEY:
        logger.info("WEATHER_API_KEY not set — weather features disabled")
        return None

    cached = _cache.get(target.lower())
    if cached is not None:
        return cached

    params = {"q": target, "appid": WEATHER_API_KEY, "units": "metric"}
    try:
        with httpx.Client(timeout=15.0) as client:
            resp = call_with_retry(lambda: client.get(WEATHER_API_URL, params=params))
        resp.raise_for_status()
        data = resp.json()
        weather = {
            "city": data.get("name") or target,
            "temp_c": float(data["main"]["temp"]),
            "condition": (data.get("weather") or [{}])[0].get("main", "unknown"),
            "humidity": data["main"].get("humidity"),
            "icon": (data.get("weather") or [{}])[0].get("icon"),
        }
    except Exception as exc:
        logger.warning("Weather lookup failed for %s: %s", target, exc)
        return None

    _cache[target.lower()] = weather
    return weather


def filter_items_by_weather(items: list, temp_c: float) -> list:
    """Drop items that fight the temperature.

    Keeps anything season-neutral (all-season / unset) plus items matching the
    temperature's season, and drops outerwear when it's warm. Returns the
    original list untouched if filtering would leave too little to build an
    outfit from — a filtered-to-nothing wardrobe is worse than a loose match.
    """
    rule = rule_for_temp(temp_c)
    season = rule["season"]

    kept = []
    for item in items:
        item_season = (getattr(item, "season", None) or "").strip().lower()
        category = (getattr(item, "category", None) or "").strip().lower()
        if category in _WARM_ONLY_CATEGORIES and temp_c > MAX_OUTERWEAR_TEMP_C:
            continue
        if item_season and item_season not in (season, "all-season", "all season"):
            continue
        kept.append(item)

    # ponytail: 3-item floor as the "can still make an outfit" test, not a real
    # per-category check. Tighten if weather outfits come back lopsided.
    if len(kept) < 3:
        return items
    return kept
