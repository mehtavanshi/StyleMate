from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.pairing_engine import find_gaps, build_search_query
from app.shopping_service import Product, get_shopping_provider

router = APIRouter(tags=["shopping-suggestions"])

# Cap the number of gaps we turn into searches so a single request never
# triggers an excessive number of upstream (rate-limited) API calls.
MAX_GAPS = 3


class ProductResponse(BaseModel):
    name: str
    image_url: str
    price: float
    currency: str
    affiliate_link: str
    source: str


class ShoppingGroupResponse(BaseModel):
    gap_reason: str
    missing_category: str
    search_query: str
    products: list[ProductResponse]


@router.get("/shopping-suggestions", response_model=list[ShoppingGroupResponse])
async def shopping_suggestions(
    user_id: int = Query(..., description="User whose wardrobe gaps to fill"),
    target_gender: str | None = Query(None),
    occasion_tag: str | None = Query(None),
    db: Session = Depends(get_db),
):
    """Detect wardrobe gaps, build a search query per gap, and fetch products.

    Pure counting (`find_gaps`) plus deterministic query generation
    (`build_search_query`) run locally; only the final provider search hits
    an external API, and that is limited to the top ``MAX_GAPS`` gaps.
    """
    gaps = find_gaps(user_id, db)[:MAX_GAPS]
    if not gaps:
        return []

    provider = get_shopping_provider()

    groups: list[ShoppingGroupResponse] = []
    for gap in gaps:
        query = build_search_query(
            gap, db, target_gender=target_gender, occasion_tag=occasion_tag
        )
        try:
            products: list[Product] = await provider.search(query)
        except Exception as exc:  # never let one provider failure 500 the request
            raise HTTPException(
                status_code=502, detail=f"Shopping provider error: {exc}"
            )

        groups.append(
            ShoppingGroupResponse(
                gap_reason=gap.reason,
                missing_category=gap.missing_category,
                search_query=query,
                products=[ProductResponse(**p.model_dump()) for p in products],
            )
        )

    return groups
