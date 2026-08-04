from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.config import VALID_BODY_TYPES


# ── Auth ──

class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    name: Optional[str] = None

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if not any(ch.isupper() for ch in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(ch.isdigit() for ch in v):
            raise ValueError("Password must contain at least one number")
        return v


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class RefreshIn(BaseModel):
    refresh_token: str


class LogoutIn(BaseModel):
    refresh_token: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


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


class AuthUserResponse(UserResponse):
    """User payload returned by /auth/register and /auth/login."""


class RegisterResponse(TokenPair):
    user: UserResponse


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
    subcategory: Optional[str] = None
    embellishments: Optional[str] = None
    garment_length: Optional[str] = None


class ClothingItemCreate(ClothingItemBase):
    pass


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
    subcategory: Optional[str] = None
    embellishments: Optional[str] = None
    garment_length: Optional[str] = None


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
    try_on_result_id: Optional[int] = None


class CalendarEntryCreate(CalendarEntryBase):
    pass


class CalendarEntryUpdate(BaseModel):
    date: Optional[date] = None
    occasion_tag: Optional[str] = None
    locked_outfit_id: Optional[int] = None
    try_on_result_id: Optional[int] = None


class CalendarEntryResponse(CalendarEntryBase):
    id: int
    user_id: int
    try_on_result_id: int | None = None
    try_on_result_image_url: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Try-On ──

class TryOnResultOut(BaseModel):
    id: int
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
    outfit_item_ids: list[int]
    liked: bool


class OutfitFeedbackResponse(OutfitFeedbackIn):
    id: int
    user_id: int
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Closet Gaps ──

class ClosetGapResponse(BaseModel):
    missing_category: str
    reason: str
    search_query: str
    shopping_links: list[dict] = []



