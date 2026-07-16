#!/usr/bin/env python3
"""Seed the database with a demo user and 5 sample clothing items."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal, engine, Base
from app.models import User, ClothingItem
from app import models  # noqa: F401

# Ensure tables exist
Base.metadata.create_all(bind=engine)

SAMPLE_ITEMS = [
    {
        "name": "White Oxford Shirt",
        "category": "top",
        "color": "white",
        "pattern": "solid",
        "occasion_tag": "formal",
        "season": "all",
        "brand": "Ralph Lauren",
        "formality": "business",
    },
    {
        "name": "Blue Denim Jeans",
        "category": "bottom",
        "color": "blue",
        "pattern": "solid",
        "occasion_tag": "casual",
        "season": "all",
        "brand": "Levi's",
        "formality": "casual",
    },
    {
        "name": "Black Leather Jacket",
        "category": "outerwear",
        "color": "black",
        "pattern": "solid",
        "occasion_tag": "casual",
        "season": "fall",
        "brand": "Zara",
        "formality": "smart casual",
    },
    {
        "name": "Navy Blue Chinos",
        "category": "bottom",
        "color": "navy",
        "pattern": "solid",
        "occasion_tag": "smart casual",
        "season": "spring",
        "brand": "Uniqlo",
        "formality": "smart casual",
    },
    {
        "name": "White Running Sneakers",
        "category": "shoes",
        "color": "white",
        "pattern": "solid",
        "occasion_tag": "athletic",
        "season": "all",
        "brand": "Nike",
        "formality": "casual",
    },
]


def seed():
    db = SessionLocal()
    try:
        # Check if user already exists
        user = db.query(User).filter(User.email == "demo@stylemate.app").first()
        if not user:
            user = User(
                name="Demo User",
                email="demo@stylemate.app",
                gender="unspecified",
                style_preference="minimalist",
            )
            db.add(user)
            db.flush()
            print(f"Created user: {user.name} (id={user.id})")
        else:
            print(f"User already exists: {user.name} (id={user.id})")

        existing_count = db.query(ClothingItem).filter(ClothingItem.user_id == user.id).count()
        if existing_count > 0:
            print(f"User already has {existing_count} items. Skipping seed.")
            return

        for item_data in SAMPLE_ITEMS:
            item = ClothingItem(user_id=user.id, **item_data)
            db.add(item)
            print(f"  + {item_data['name']}")

        db.commit()
        print(f"\nSeeded {len(SAMPLE_ITEMS)} clothing items for {user.name}.")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
