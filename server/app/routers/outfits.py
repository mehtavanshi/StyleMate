from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ClothingItem, OutfitFeedback
from app.pairing_engine import OutfitSuggestion, build_capsule, suggest_outfits
from app.schemas import OutfitFeedbackResponse, OutfitFeedbackIn
from app.services.nlp_router import parse_query_to_params
from app.services.weather_service import (
    filter_items_by_weather,
    get_weather,
    rule_for_temp,
)

router = APIRouter(tags=["outfit-suggestions"])


class OutfitItemResponse(BaseModel):
    id: int
    name: str | None
    category: str
    color: str | None
    pattern: str | None
    fabric_type: str | None = None
    fit_type: str | None = None
    sleeve_length: str | None = None
    image_url: str | None
    target_gender: str | None = None


class OutfitSuggestionResponse(BaseModel):
    items: list[OutfitItemResponse]
    score: float
    reason: str
    breakdown: dict[str, float] = {}


class OutfitSuggestionsResponse(BaseModel):
    outfits: list[OutfitSuggestionResponse]
    total: int


@router.get("/outfit-suggestions", response_model=OutfitSuggestionsResponse)
def get_outfit_suggestions(
    user_id: int = 1,
    occasion_tag: str | None = None,
    target_gender: str | None = None,
    limit: int = 5,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    result = suggest_outfits(db, user_id, occasion_tag, target_gender, limit, offset=offset)
    return OutfitSuggestionsResponse(
        outfits=[_to_response(r) for r in result["items"]],
        total=result["total"],
    )


def _to_response(r: OutfitSuggestion) -> OutfitSuggestionResponse:
    return OutfitSuggestionResponse(
        items=[OutfitItemResponse(**i) for i in r.items],
        score=r.score,
        reason=r.reason,
        breakdown=r.breakdown,
    )


# ── Smart outfit generator (Feature 4.3) ──


class SmartOutfitIn(BaseModel):
    query: str
    limit: int = 5
    user_id: int = 1


class SmartOutfitResponse(BaseModel):
    query: str
    params: dict
    confidence: str
    outfits: list[OutfitSuggestionResponse]


@router.post("/smart-outfit", response_model=SmartOutfitResponse)
def smart_outfit(payload: SmartOutfitIn, db: Session = Depends(get_db)):
    """Free-text request ("interview tomorrow") → filtered outfit suggestions.

    Confidence reflects how much of the request we could actually pin down:
    a Gemini parse that resolved several fields is "high", keyword-only is
    "low". The suggestions themselves come from the same pairing engine.
    """
    params = parse_query_to_params(payload.query)
    inferred = sum(
        1
        for key in ("occasion_tag", "formality_level", "season", "target_gender", "vibe")
        if params.get(key)
    )
    if params.get("source") == "gemini" and inferred >= 2:
        confidence = "high"
    elif inferred >= 1:
        confidence = "medium"
    else:
        confidence = "low"

    result = suggest_outfits(
        db,
        payload.user_id,
        occasion_tag=params.get("occasion_tag"),
        target_gender=params.get("target_gender"),
        limit=payload.limit,
    )

    # Nothing matched the parsed occasion — better to show the user's best
    # general outfits than an empty screen, so retry unfiltered.
    if not result["items"] and params.get("occasion_tag"):
        result = suggest_outfits(db, payload.user_id, limit=payload.limit)
        confidence = "low"

    return SmartOutfitResponse(
        query=payload.query,
        params=params,
        confidence=confidence,
        outfits=[_to_response(r) for r in result["items"]],
    )


# ── Weather-based recommendation (Feature 4.4) ──


class WeatherOutfitResponse(BaseModel):
    weather: dict | None
    guidance: dict | None
    outfit: OutfitSuggestionResponse | None
    message: str | None = None


@router.get("/weather-outfit", response_model=WeatherOutfitResponse)
def weather_outfit(
    city: str | None = None,
    user_id: int = 1,
    db: Session = Depends(get_db),
):
    """Today's pick, filtered to what suits the current temperature.

    With no WEATHER_API_KEY (or an unreachable API) it returns the plain top
    suggestion plus a message, rather than failing the request.
    """
    weather = get_weather(city)
    items = db.query(ClothingItem).filter(ClothingItem.user_id == user_id).all()

    if weather is None:
        result = suggest_outfits(db, user_id, limit=1)
        return WeatherOutfitResponse(
            weather=None,
            guidance=None,
            outfit=_to_response(result["items"][0]) if result["items"] else None,
            message="Weather unavailable — set WEATHER_API_KEY for temperature-aware picks.",
        )

    filtered = filter_items_by_weather(items, weather["temp_c"])
    result = suggest_outfits(db, user_id, limit=1, items=filtered)
    guidance = rule_for_temp(weather["temp_c"])

    return WeatherOutfitResponse(
        weather=weather,
        guidance=guidance,
        outfit=_to_response(result["items"][0]) if result["items"] else None,
        message=None if result["items"] else "No weather-appropriate outfit in your wardrobe yet.",
    )


# ── Capsule wardrobe builder (Feature 4.6) ──


class CapsuleRequest(BaseModel):
    target_item_count: int = 20
    occasion_tag: str | None = None
    locked_item_ids: list[int] = []
    user_id: int = 1


@router.post("/capsule-wardrobe")
def capsule_wardrobe(req: CapsuleRequest, db: Session = Depends(get_db)):
    """The N items from the wardrobe that produce the most wearable outfits."""
    return build_capsule(
        req.user_id,
        target_count=max(2, min(req.target_item_count, 40)),
        occasion_filter=req.occasion_tag,
        db=db,
        locked_item_ids=req.locked_item_ids,
    )


@router.post("/outfit-feedback", response_model=OutfitFeedbackResponse)
def create_outfit_feedback(
    payload: OutfitFeedbackIn,
    db: Session = Depends(get_db),
):
    import json

    db_feedback = OutfitFeedback(
        user_id=payload.user_id,
        outfit_item_ids=json.dumps(payload.outfit_item_ids),
        liked=1 if payload.liked else 0,
    )
    db.add(db_feedback)
    db.commit()
    db.refresh(db_feedback)

    return OutfitFeedbackResponse(
        id=db_feedback.id,
        user_id=db_feedback.user_id,
        outfit_item_ids=payload.outfit_item_ids,
        liked=payload.liked,
        created_at=db_feedback.created_at,
    )
