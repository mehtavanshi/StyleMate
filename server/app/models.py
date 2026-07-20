from sqlalchemy import Boolean, Column, Integer, String, DateTime, Date, Float, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False, index=True)
    gender = Column(String, nullable=True)
    target_gender = Column(String, nullable=True)
    style_preference = Column(String, nullable=True)
    body_type = Column(String, nullable=True)
    photo_consent = Column(Boolean, default=False)
    consent_given_at = Column(DateTime(timezone=True), nullable=True)
    consent_version = Column(String, nullable=True)
    photo_url = Column(String, nullable=True)
    photo_storage_key = Column(String, nullable=True)
    last_activity_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    clothing_items = relationship("ClothingItem", back_populates="user")
    calendar_entries = relationship("CalendarEntry", back_populates="user")
    try_on_results = relationship("TryOnResult", back_populates="user", cascade="all, delete-orphan")


class ClothingItem(Base):
    __tablename__ = "clothing_items"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    image_url = Column(String, nullable=True)
    category = Column(String, nullable=False)
    color = Column(String, nullable=True)
    pattern = Column(String, nullable=True)
    occasion_tag = Column(String, nullable=True)
    season = Column(String, nullable=True)
    brand = Column(String, nullable=True)
    name = Column(String, nullable=True)
    formality = Column(String, nullable=True)
    target_gender = Column(String, nullable=True, default="unisex")
    fabric_type = Column(String, nullable=True)
    fit_type = Column(String, nullable=True)
    sleeve_length = Column(String, nullable=True)
    formality_score = Column(Integer, nullable=True)
    tags = Column(Text, nullable=True)
    style_tags = Column(Text, nullable=True)
    embedding_json = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    user = relationship("User", back_populates="clothing_items")


class CalendarEntry(Base):
    __tablename__ = "calendar_entries"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    date = Column(Date, nullable=False)
    occasion_tag = Column(String, nullable=True)
    locked_outfit_id = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="calendar_entries")


class TryOnResult(Base):
    __tablename__ = "try_on_results"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(String(36), unique=True, index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    status = Column(String(20), nullable=False, default="pending")
    outfit_items_json = Column(Text, nullable=True)
    result_image_url = Column(String, nullable=True)
    error_message = Column(Text, nullable=True)
    model_used = Column(String(50), nullable=True)
    latency_ms = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="try_on_results")


class OutfitFeedback(Base):
    __tablename__ = "outfit_feedback"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    outfit_item_ids = Column(Text, nullable=False)
    liked = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User")



