import asyncio
import logging
from typing import Any

from cachetools import TTLCache
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import ClothingItem
from app.shopping_service import search_all_providers
from app.style_advisor import explain_outfit, get_style_advice

logger = logging.getLogger(__name__)

router = APIRouter(tags=["style-advice"])

_cache: TTLCache = TTLCache(maxsize=200, ttl=1800)


class SuggestionWithProducts(BaseModel):
    suggestion: str
    products: list[dict[str, Any]]


class StyleAdviceResponse(BaseModel):
    shoes: list[SuggestionWithProducts]
    accessories: list[SuggestionWithProducts]
    layering: list[SuggestionWithProducts]
    reasoning: str


class ExplainOutfitIn(BaseModel):
    outfit_item_ids: list[int]
    user_id: int = 1


@router.post("/explain-outfit")
def explain_outfit_endpoint(payload: ExplainOutfitIn, db: Session = Depends(get_db)):
    """Stylist-voice explanation of why an outfit works.

    Falls back to the pairing engine's own reason text when Gemini is
    unreachable, so the client never has to handle an empty response.
    """
    items = (
        db.query(ClothingItem)
        # joinedload: explain_outfit reads items[0].user for the body type, and
        # a lazy load fired an extra SELECT on every expansion.
        .options(joinedload(ClothingItem.user))
        .filter(
            ClothingItem.id.in_(payload.outfit_item_ids),
            # Arbitrary ids used to be accepted, so any caller could read back
            # a description of someone else's wardrobe.
            ClothingItem.user_id == payload.user_id,
        )
        .all()
    )
    if not items:
        raise HTTPException(status_code=404, detail="No items found for those IDs")
    return {"explanation": explain_outfit(items, db)}


async def _search_one(suggestion: str, gender: str | None = None) -> list[dict[str, Any]]:
    query = suggestion
    if gender and gender.lower() not in ("unisex", "unknown"):
        query = f"{gender} {suggestion}"
    try:
        provider_results = await search_all_providers(query)
        seen: set[str] = set()
        with_images: list[dict[str, Any]] = []
        without_images: list[dict[str, Any]] = []
        for pr in provider_results:
            for p in pr.products:
                key = p.affiliate_link or p.name
                if key in seen:
                    continue
                seen.add(key)
                if p.image_url:
                    with_images.append(p.model_dump())
                else:
                    without_images.append(p.model_dump())
        return (with_images + without_images)[:3]
    except Exception as exc:
        logger.warning("_search_one for %r failed: %s", suggestion, exc)
        return []


@router.get("/style-advice")
async def style_advice_endpoint(
    item_id: int,
    db: Session = Depends(get_db),
):
    cached = _cache.get(item_id)
    if cached is not None:
        return cached

    item = db.query(ClothingItem).filter(ClothingItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    advice = get_style_advice(item)

    suggestions: list[tuple[str, str]] = []
    for s in advice.shoes:
        suggestions.append(("shoes", s))
    for s in advice.accessories:
        suggestions.append(("accessories", s))
    for s in advice.layering:
        suggestions.append(("layering", s))

    gender = item.target_gender
    if suggestions:
        results = await asyncio.gather(*[_search_one(s, gender) for _, s in suggestions])
    else:
        results = []

    shoes_list: list[dict[str, Any]] = []
    accessories_list: list[dict[str, Any]] = []
    layering_list: list[dict[str, Any]] = []

    for (category, suggestion), products in zip(suggestions, results):
        item = SuggestionWithProducts(suggestion=suggestion, products=products)
        d = item.model_dump()
        if category == "shoes":
            shoes_list.append(d)
        elif category == "accessories":
            accessories_list.append(d)
        elif category == "layering":
            layering_list.append(d)

    response = StyleAdviceResponse(
        shoes=shoes_list,
        accessories=accessories_list,
        layering=layering_list,
        reasoning=advice.reasoning,
    )

    _cache[item_id] = response.model_dump()
    return response.model_dump()
