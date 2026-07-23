from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel

from app.config import VALID_BODY_TYPES


# ── User ──

class UserBase(BaseModel):
    name: str
    email: str
    gender: Optional[str] = None
    target_gender: Optional[str] = None
    style_preference: Optional[str] = None
    body_type: Optional[str] = None


class UserCreate(UserBase):
    pass


class UserResponse(UserBase):
    id: int
    photo_consent: bool = False
    consent_given_at: Optional[datetime] = None
    consent_version: Optional[str] = None
    photo_url: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Consent ──

class ConsentIn(BaseModel):
    consent_version: str


class ConsentResponse(BaseModel):
    photo_consent: bool
    consent_given_at: Optional[datetime] = None
    consent_version: Optional[str] = None
    photo_url: Optional[str] = None


class PhotoUrlIn(BaseModel):
    image_url: str


# ── Body type ──

BodyType = Literal[
    "rectangle",
    "hourglass",
    "pear",
    "apple",
    "inverted_triangle",
]


class BodyTypeIn(BaseModel):
    body_type: BodyType


# ── ClothingItem ──

class ClothingItemBase(BaseModel):
    image_url: Optional[str] = None
    category: str
    color: Optional[str] = None
    pattern: Optional[str] = None
    occasion_tag: Optional[str] = None
    season: Optional[str] = None
    brand: Optional[str] = None
    name: Optional[str] = None
    formality: Optional[str] = None
    target_gender: Optional[str] = "unisex"
    fabric_type: Optional[str] = None
    fit_type: Optional[str] = None
    sleeve_length: Optional[str] = None
    formality_score: Optional[int] = None
    tags: Optional[str] = None
    style_tags: Optional[str] = None


class ClothingItemCreate(ClothingItemBase):
    user_id: int


class ClothingItemUpdate(BaseModel):
    image_url: Optional[str] = None
    category: Optional[str] = None
    color: Optional[str] = None
    pattern: Optional[str] = None
    occasion_tag: Optional[str] = None
    season: Optional[str] = None
    brand: Optional[str] = None
    name: Optional[str] = None
    formality: Optional[str] = None
    target_gender: Optional[str] = None
    fabric_type: Optional[str] = None
    fit_type: Optional[str] = None
    sleeve_length: Optional[str] = None
    formality_score: Optional[int] = None
    tags: Optional[str] = None
    style_tags: Optional[str] = None


class ClothingItemResponse(ClothingItemBase):
    id: int
    user_id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ── CalendarEntry ──

class CalendarEntryBase(BaseModel):
    date: date
    occasion_tag: Optional[str] = None
    locked_outfit_id: Optional[int] = None


class CalendarEntryCreate(CalendarEntryBase):
    user_id: int


class CalendarEntryUpdate(BaseModel):
    date: Optional[date] = None
    occasion_tag: Optional[str] = None
    locked_outfit_id: Optional[int] = None


class CalendarEntryResponse(CalendarEntryBase):
    id: int
    user_id: int
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Try-On ──

class TryOnResultOut(BaseModel):
    job_id: str
    status: str
    result_image_url: str | None = None
    error_message: str | None = None
    error_type: str | None = None
    model_used: str | None = None
    latency_ms: int | None = None
    created_at: str


# ── OutfitFeedback ──

class OutfitFeedbackIn(BaseModel):
    user_id: int
    outfit_item_ids: list[int]
    liked: bool


class OutfitFeedbackResponse(OutfitFeedbackIn):
    id: int
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Closet Gaps ──

class ClosetGapResponse(BaseModel):
    missing_category: str
    reason: str
    search_query: str



