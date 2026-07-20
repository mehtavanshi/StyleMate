"""AI-powered style advisor that uses Gemini to suggest outfit completions
for a single wardrobe item, returning structured suggestions for shoes,
accessories, and layering pieces with styling reasoning."""

from __future__ import annotations

import json
import logging

import httpx
from pydantic import BaseModel

from app.models import ClothingItem
from app.retry import call_with_retry
from app.routers.tagging import GEMINI_API_KEY, GEMINI_API_URL, GEMINI_MODEL

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


def get_style_advice(item: ClothingItem) -> StyleAdvice:
    if not GEMINI_API_KEY:
        logger.warning("GEMINI_API_KEY not set — returning empty style advice")
        return StyleAdvice(shoes=[], accessories=[], layering=[], reasoning="")

    parts: list[str] = []
    if item.category:
        parts.append(item.category)
    if item.color:
        parts.append(item.color)
    if item.pattern and item.pattern != "solid":
        parts.append(item.pattern)
    if item.fit_type:
        parts.append(f"{item.fit_type}-fit")
    if item.fabric_type:
        parts.append(item.fabric_type)

    item_description = " ".join(parts) if parts else "cloth item"

    prompt = PROMPT_TEMPLATE.format(
        item_description=item_description,
        target_gender=item.target_gender or "person",
        season=item.season or "any",
        occasion=item.occasion_tag or "any",
    )

    api_url = GEMINI_API_URL.replace("{model}", GEMINI_MODEL)

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.4,
            "maxOutputTokens": 500,
        },
    }

    headers = {
        "x-goog-api-key": GEMINI_API_KEY,
        "Content-Type": "application/json",
    }

    try:
        with httpx.Client(timeout=30.0) as client:
            resp = call_with_retry(lambda: client.post(api_url, json=payload, headers=headers))
        resp.raise_for_status()
        data = resp.json()
        raw_text = data["candidates"][0]["content"]["parts"][0]["text"]

        parsed = _parse_advice_response(raw_text)
        if parsed is None:
            logger.warning("Gemini returned invalid JSON for style advice: %s", raw_text[:200])
            return StyleAdvice(shoes=[], accessories=[], layering=[], reasoning="")

        return StyleAdvice(
            shoes=parsed.get("shoes", []),
            accessories=parsed.get("accessories", []),
            layering=parsed.get("layering", []),
            reasoning=parsed.get("reasoning", ""),
        )

    except Exception as exc:
        logger.warning("get_style_advice failed for item=%s: %s", item.id, exc, exc_info=True)
        return StyleAdvice(shoes=[], accessories=[], layering=[], reasoning="")
