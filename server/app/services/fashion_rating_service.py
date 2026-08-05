"""AI fashion rating — send an outfit photo to Gemini Vision, get scores back."""

from __future__ import annotations

import logging

from cachetools import TTLCache

from app.style_advisor import gemini_json

logger = logging.getLogger(__name__)

# Same photo → same rating; don't burn free-tier calls on a re-tap.
_cache: TTLCache = TTLCache(maxsize=100, ttl=3600)

SCORE_FIELDS = (
    "overall_style",
    "color_harmony",
    "fit",
    "occasion_match",
    "silhouette_balance",
)

PROMPT = """Analyze this outfit photo as a professional fashion critic.
Rate on a scale of 1-10 for each:
- overall_style: overall visual appeal and coordination
- color_harmony: how well colors work together
- fit: how well clothes fit the wearer
- occasion_match: suitability for the inferred context
- silhouette_balance: proportions and visual weight

Also suggest 3 specific, actionable improvements.
Return ONLY valid JSON with NO markdown formatting:
{
  "overall_style": {"score": 0-10, "reason": "..."},
  "color_harmony": {"score": 0-10, "reason": "..."},
  "fit": {"score": 0-10, "reason": "..."},
  "occasion_match": {"score": 0-10, "reason": "..."},
  "silhouette_balance": {"score": 0-10, "reason": "..."},
  "suggestions": ["...", "...", "..."],
  "vibe_tags": ["...", "..."],
  "primary_colors_detected": ["...", "..."]
}

Judge only what is visible. If the photo shows no person or no outfit, return
{"error": "no outfit visible"} instead."""


def _clean_score(raw) -> dict | None:
    """Coerce one {"score", "reason"} block, dropping anything malformed."""
    if not isinstance(raw, dict):
        return None
    score = raw.get("score")
    if isinstance(score, str):
        try:
            score = float(score)
        except ValueError:
            return None
    if not isinstance(score, (int, float)):
        return None
    return {
        "score": round(max(0.0, min(10.0, float(score))), 1),
        "reason": str(raw.get("reason") or "")[:200],
    }


def rate_outfit_photo(photo_url: str, user_id: int | None = None) -> dict:
    """Structured fashion rating for a photo.

    Returns ``{"available": False, "message": ...}`` when Gemini is unset,
    unreachable, or reports no outfit in frame — the client shows that message
    rather than fabricating scores.
    """
    # Keyed by user too: a bare-URL key served one user's rating to anyone who
    # rated the same URL, and the rating will grow user context over time.
    cache_key = (user_id, photo_url)
    cached = _cache.get(cache_key)
    if cached is not None:
        return cached

    parsed = gemini_json(PROMPT, max_tokens=800, temperature=0.3, image_url=photo_url)

    if not isinstance(parsed, dict):
        return {
            "available": False,
            "message": "Style rating needs a Gemini API key and a reachable photo.",
        }
    if parsed.get("error"):
        return {"available": False, "message": str(parsed["error"])[:200]}

    scores = {f: _clean_score(parsed.get(f)) for f in SCORE_FIELDS}
    scores = {k: v for k, v in scores.items() if v is not None}
    if not scores:
        return {
            "available": False,
            "message": "Could not read a rating from the photo. Try a clearer full-body shot.",
        }

    result = {
        "available": True,
        "scores": scores,
        "average_score": round(
            sum(v["score"] for v in scores.values()) / len(scores), 1
        ),
        "suggestions": [
            str(s)[:200] for s in (parsed.get("suggestions") or []) if isinstance(s, str)
        ][:3],
        "vibe_tags": [
            str(t)[:40] for t in (parsed.get("vibe_tags") or []) if isinstance(t, str)
        ][:5],
        "primary_colors_detected": [
            str(c)[:30]
            for c in (parsed.get("primary_colors_detected") or [])
            if isinstance(c, str)
        ][:5],
    }
    _cache[cache_key] = result
    return result
