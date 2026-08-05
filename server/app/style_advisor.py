"""AI-powered style advisor that uses Gemini to suggest outfit completions
for a single wardrobe item, returning structured suggestions for shoes,
accessories, and layering pieces with styling reasoning.

Also hosts ``gemini_text`` / ``gemini_json`` — the single Gemini call path
shared by every Gemini-backed feature (style advice, outfit explanations,
natural-language outfit queries, packing lists, photo ratings)."""

from __future__ import annotations

import base64
import json
import logging

import httpx
from cachetools import TTLCache
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.models import ClothingItem
from app.retry import call_with_retry
from app.routers.tagging import (
    GEMINI_API_KEY,
    GEMINI_API_URL,
    GEMINI_MODEL,
    _read_image,
)

logger = logging.getLogger(__name__)


class StyleAdvice(BaseModel):
    shoes: list[str] = []
    accessories: list[str] = []
    layering: list[str] = []
    reasoning: str = ""


PROMPT_TEMPLATE = """You are a professional fashion stylist. Suggest shoes,
accessories, and optional layering pieces that go well WITH this item:

{item_description}

This item is for {target_gender}, typically worn in {season} for {occasion} occasions.

Rules:
- Suggest items that COMPLEMENT and CONTRAST with the piece above — never
  suggest something in the same category or same color
- Be specific (e.g. "brown leather loafers" not "shoes",
  "gold hoop earrings" not "earrings")
- Keep each suggestion under 6 words — they will be used as shopping
  search queries
- For women: draw from womenswear accessories (earrings, bracelet,
  necklace, handbag, scarf, hair accessory)
- For men: draw from menswear accessories (belt, socks, tie, watch,
  cufflinks, pocket square)
- For unisex: suggest broadly wearable options (sunglasses, watch,
  crossbody bag, cap)
- Only suggest layering (jacket, blazer, cardigan, shawl) if season is
  winter OR occasion is formal/office — otherwise return an empty list,
  don't force one
- Never suggest espadrilles
- Don't invent details about the item not mentioned above

Return ONLY valid JSON, no markdown:
{{
  "shoes": ["specific shoe suggestion", "specific shoe suggestion"],
  "accessories": ["specific accessory 1", "specific accessory 2",
                   "specific accessory 3"],
  "layering": ["layering piece if needed"],
  "reasoning": "one sentence explaining why these pair well"
}}"""


def _parse_advice_response(raw_text: str) -> dict | None:
    text = raw_text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def gemini_text(
    prompt: str,
    max_tokens: int = 500,
    temperature: float = 0.4,
    image_url: str | None = None,
    timeout: float = 60.0,
) -> str | None:
    """One Gemini generateContent call. Returns the raw text, or None on failure.

    Every Gemini-backed feature routes through here so the key check, retry,
    timeout, and error swallowing live in exactly one place. Pass
    ``image_url`` to attach an image (Gemini Vision).
    """
    if not GEMINI_API_KEY:
        logger.warning("GEMINI_API_KEY not set — skipping Gemini call")
        return None

    parts: list[dict] = [{"text": prompt}]
    if image_url:
        try:
            image_data, content_type = _read_image(image_url)
        except Exception as exc:
            logger.warning("gemini_text could not read image %s: %s", image_url, exc)
            return None
        parts.append(
            {
                "inline_data": {
                    "mime_type": content_type.split(";")[0],
                    "data": base64.b64encode(image_data).decode(),
                }
            }
        )

    payload = {
        "contents": [{"parts": parts}],
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_tokens,
        },
    }
    headers = {"x-goog-api-key": GEMINI_API_KEY, "Content-Type": "application/json"}
    api_url = GEMINI_API_URL.replace("{model}", GEMINI_MODEL)

    try:
        with httpx.Client(timeout=timeout) as client:
            resp = call_with_retry(
                lambda: client.post(api_url, json=payload, headers=headers)
            )
        resp.raise_for_status()
        return resp.json()["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as exc:
        logger.warning("Gemini call failed: %s", exc, exc_info=True)
        return None


def gemini_json(
    prompt: str,
    max_tokens: int = 500,
    temperature: float = 0.2,
    image_url: str | None = None,
    timeout: float = 60.0,
) -> dict | None:
    """``gemini_text`` + markdown-fence-tolerant JSON parse. None on failure."""
    raw = gemini_text(prompt, max_tokens, temperature, image_url, timeout)
    if raw is None:
        return None
    parsed = _parse_advice_response(raw)
    if parsed is None:
        logger.warning("Gemini returned non-JSON: %s", raw[:200])
    return parsed


# ── Outfit explanations (Feature 4.2) ──

# Explanations are deterministic per item set, so cache them and keep the
# Gemini free tier out of the loop when a card is expanded repeatedly.
_explain_cache: TTLCache = TTLCache(maxsize=200, ttl=1800)

EXPLAIN_PROMPT = """You are a professional stylist. These items are being worn
together:

{item_descriptions}

The blended compatibility score is {score}, with sub-scores: {breakdown}.

Explain in 2-3 conversational sentences why this outfit works (or doesn't
work). Be specific — mention the colors, textures, and silhouettes named
above. Never invent an item or a detail that isn't listed. Return plain text,
no markdown, no JSON."""


def describe_item(item: ClothingItem) -> str:
    """Short human phrase for an item, e.g. 'white slim-fit cotton top'."""
    parts = [
        p
        for p in (
            item.color,
            item.pattern if item.pattern and item.pattern != "solid" else None,
            f"{item.fit_type}-fit" if item.fit_type else None,
            item.fabric_type,
            item.subcategory or item.category,
        )
        if p
    ]
    return " ".join(parts) or "clothing item"


def explain_outfit(items: list[ClothingItem], db: Session) -> str:
    """Natural-language stylist explanation for why a set of items works.

    Falls back to the pairing engine's own reason string when Gemini is
    unavailable, so the endpoint always returns something useful.
    """
    from app.pairing_engine import score_outfit

    if not items:
        return ""

    key = tuple(sorted(i.id for i in items))
    cached = _explain_cache.get(key)
    if cached is not None:
        return cached

    user = items[0].user
    score, reason, breakdown = score_outfit(
        items, getattr(user, "body_type", None) if user else None
    )

    explanation = gemini_text(
        EXPLAIN_PROMPT.format(
            item_descriptions="\n".join(f"- {describe_item(i)}" for i in items),
            score=round(score, 2),
            breakdown=", ".join(f"{k} {v}" for k, v in sorted(breakdown.items())),
        ),
        max_tokens=250,
        temperature=0.5,
    )

    text = (explanation or "").strip() or reason
    _explain_cache[key] = text
    return text


def get_style_advice(item: ClothingItem) -> StyleAdvice:
    prompt = PROMPT_TEMPLATE.format(
        item_description=describe_item(item),
        target_gender=item.target_gender or "person",
        season=item.season or "any",
        occasion=item.occasion_tag or "any",
    )

    parsed = gemini_json(prompt, max_tokens=500, temperature=0.4)
    if parsed is None:
        return StyleAdvice(shoes=[], accessories=[], layering=[], reasoning="")

    return StyleAdvice(
        shoes=parsed.get("shoes", []),
        accessories=parsed.get("accessories", []),
        layering=parsed.get("layering", []),
        reasoning=parsed.get("reasoning", ""),
    )
