"""Natural-language outfit request → structured suggestion params.

"something for an interview tomorrow" → {"occasion_tag": "office",
"formality_level": 4, ...}. Gemini does the extraction; a keyword fallback
covers the no-API-key / API-down case so /smart-outfit always answers.
"""

from __future__ import annotations

import logging

from app.style_advisor import gemini_json

logger = logging.getLogger(__name__)

OCCASIONS = (
    "casual",
    "office",
    "ethnic",
    "party",
    "formal",
    "loungewear",
    "travel",
)
SEASONS = ("spring", "summer", "fall", "winter", "all-season")
GENDERS = ("men", "women", "unisex")
VIBES = ("minimal", "colorful", "classic", "edgy", "bohemian", "sporty")

PROMPT = """Extract structured outfit parameters from this user request.
Return ONLY valid JSON with NO markdown formatting.
User request: "{query}"

Fields:
- occasion_tag: "casual" | "office" | "ethnic" | "party" | "formal" | "loungewear" | "travel" | null
- formality_level: 1-5 integer (1=casual, 5=black tie) | null
- season: "spring" | "summer" | "fall" | "winter" | "all-season" | null
- target_gender: "men" | "women" | "unisex" | null
- vibe: "minimal" | "colorful" | "classic" | "edgy" | "bohemian" | "sporty" | null

If a field can't be inferred, set it to null. Do NOT guess."""

# Words that map straight onto an occasion when Gemini isn't available.
_KEYWORDS: dict[str, str] = {
    "interview": "office",
    "work": "office",
    "office": "office",
    "meeting": "office",
    "presentation": "office",
    "wedding": "formal",
    "formal": "formal",
    "gala": "formal",
    "ceremony": "formal",
    "party": "party",
    "club": "party",
    "birthday": "party",
    "date": "party",
    "diwali": "ethnic",
    "festival": "ethnic",
    "puja": "ethnic",
    "traditional": "ethnic",
    "ethnic": "ethnic",
    "gym": "loungewear",
    "lounge": "loungewear",
    "home": "loungewear",
    "sleep": "loungewear",
    "travel": "travel",
    "trip": "travel",
    "flight": "travel",
    "brunch": "casual",
    "casual": "casual",
    "weekend": "casual",
}

_FORMALITY_BY_OCCASION = {
    "loungewear": 1,
    "casual": 2,
    "travel": 2,
    "ethnic": 4,
    "office": 4,
    "party": 3,
    "formal": 5,
}

_SEASON_KEYWORDS = {
    "summer": "summer",
    "hot": "summer",
    "monsoon": "summer",
    "winter": "winter",
    "cold": "winter",
    "snow": "winter",
    "spring": "spring",
    "fall": "fall",
    "autumn": "fall",
}


def _clean(value, allowed: tuple[str, ...]) -> str | None:
    """Keep a Gemini field only if it is one of the values we asked for."""
    if not isinstance(value, str):
        return None
    v = value.strip().lower()
    return v if v in allowed else None


def _fallback_params(query: str) -> dict:
    """Keyword extraction — used when Gemini is unavailable or returns junk."""
    q = query.lower()
    occasion = next((occ for word, occ in _KEYWORDS.items() if word in q), None)
    season = next((s for word, s in _SEASON_KEYWORDS.items() if word in q), None)
    gender = next((g for g in GENDERS if g in q), None)
    return {
        "occasion_tag": occasion,
        "formality_level": _FORMALITY_BY_OCCASION.get(occasion or ""),
        "season": season,
        "target_gender": gender,
        "vibe": next((v for v in VIBES if v in q), None),
        "source": "keywords",
    }


def parse_query_to_params(query: str) -> dict:
    """Return suggestion params for a free-text request.

    ``source`` tells the caller which path produced the params ("gemini" or
    "keywords") so the endpoint can report a matching confidence level.
    """
    parsed = gemini_json(PROMPT.format(query=query), max_tokens=200, temperature=0.1)
    if not isinstance(parsed, dict):
        return _fallback_params(query)

    level = parsed.get("formality_level")
    if not isinstance(level, int) or not 1 <= level <= 5:
        level = None

    params = {
        "occasion_tag": _clean(parsed.get("occasion_tag"), OCCASIONS),
        "formality_level": level,
        "season": _clean(parsed.get("season"), SEASONS),
        "target_gender": _clean(parsed.get("target_gender"), GENDERS),
        "vibe": _clean(parsed.get("vibe"), VIBES),
        "source": "gemini",
    }

    # Gemini answered but inferred nothing usable — keywords may still help.
    if not any(params[k] for k in ("occasion_tag", "season", "target_gender", "vibe")):
        fallback = _fallback_params(query)
        if fallback["occasion_tag"]:
            return fallback

    return params
