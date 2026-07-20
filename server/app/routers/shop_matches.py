import logging
from typing import Any

from cachetools import TTLCache
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ClothingItem
from app.shopping_service import Product, search_all_providers, SHOPPING_PROVIDERS
from app.style_embeddings import rank_by_visual_fit, RankedProduct
from app.style_match import build_item_match_queries

logger = logging.getLogger(__name__)

router = APIRouter(tags=["shop-matches"])

_cache: TTLCache = TTLCache(maxsize=500, ttl=1800)


class ShopMatchProduct(BaseModel):
    name: str
    image_url: str
    price: float
    currency: str
    affiliate_link: str
    source: str
    similarity_score: float | None = None
    fit_type: str | None = None


class ShopMatchGroup(BaseModel):
    label: str
    ai_top_picks: list[ShopMatchProduct]
    flipkart_products: list[ShopMatchProduct]
    amazon_products: list[ShopMatchProduct]
    meesho_search_link: ShopMatchProduct | None


# Platforms whose product images support visual ranking.
_IMAGE_PLATFORMS = {"flipkart", "amazon"}


def _to_shop_match(rp: RankedProduct) -> ShopMatchProduct:
    return ShopMatchProduct(
        name=rp.product.name,
        image_url=rp.product.image_url,
        price=rp.product.price,
        currency=rp.product.currency,
        affiliate_link=rp.product.affiliate_link,
        source=rp.product.source,
        similarity_score=rp.similarity_score,
    )


@router.get("/items/{item_id}/shop-matches")
async def get_shop_matches(
    item_id: int,
    refresh: bool = False,
    db: Session = Depends(get_db),
):
    if refresh:
        _cache.pop(item_id, None)
    else:
        cached = _cache.get(item_id)
        if cached is not None:
            return cached

    item = db.query(ClothingItem).filter(ClothingItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    match_queries = build_item_match_queries(item_id, db)

    groups: list[dict[str, Any]] = []

    for mq in match_queries:
        label: str = mq["label"]
        query: str = mq["query"]

        provider_results = await search_all_providers(query)

        flipkart_ranked: list[RankedProduct] = []
        amazon_ranked: list[RankedProduct] = []
        meesho_link: ShopMatchProduct | None = None

        for pr in provider_results:
            platform = pr.platform
            products = pr.products

            if not products:
                continue

            if platform in _IMAGE_PLATFORMS:
                ranked = rank_by_visual_fit(item_id, products, db)
                if platform == "flipkart":
                    flipkart_ranked = ranked[:5]
                elif platform == "amazon":
                    amazon_ranked = ranked[:5]

            elif platform == "meesho":
                p = products[0]
                meesho_link = ShopMatchProduct(
                    name=p.name,
                    image_url=p.image_url,
                    price=p.price,
                    currency=p.currency,
                    affiliate_link=p.affiliate_link,
                    source=p.source,
                    fit_type=item.fit_type,
                )

        all_image_ranked = flipkart_ranked + amazon_ranked
        all_image_ranked.sort(
            key=lambda r: r.similarity_score or 0.0, reverse=True
        )
        ai_top_picks = [_to_shop_match(rp) for rp in all_image_ranked[:3]]

        groups.append(
            {
                "label": label,
                "ai_top_picks": [p.model_dump() for p in ai_top_picks],
                "flipkart_products": [_to_shop_match(rp).model_dump() for rp in flipkart_ranked],
                "amazon_products": [_to_shop_match(rp).model_dump() for rp in amazon_ranked],
                "meesho_search_link": meesho_link.model_dump() if meesho_link else None,
            }
        )

    _cache[item_id] = groups
    return groups
