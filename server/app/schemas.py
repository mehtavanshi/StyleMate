from datetime import datetime
from typing import Optional

from pydantic import BaseModel


# ── User ──

class UserBase(BaseModel):
    name: str
    email: str
    gender: Optional[str] = None
    target_gender: Optional[str] = None
    style_preference: Optional[str] = None


class UserCreate(UserBase):
    pass


class UserResponse(UserBase):
    id: int
    created_at: datetime

    model_config = {"from_attributes": True}


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
    tags: Optional[str] = None


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


class ClothingItemResponse(ClothingItemBase):
    id: int
    user_id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
