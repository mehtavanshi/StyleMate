#!/usr/bin/env python3
"""Seed the database with a demo user and sample clothing items with real images."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal, engine, Base
from app.models import User, ClothingItem
from app import models  # noqa: F401

Base.metadata.create_all(bind=engine)

SAMPLE_ITEMS = [
    {
        "name": "White Oxford Shirt",
        "category": "top",
        "color": "white",
        "pattern": "solid",
        "occasion_tag": "formal",
        "season": "all-season",
        "brand": "Ralph Lauren",
        "formality": "business",
        "image_url": "/uploads/oxford-shirt.jpg",
    },
    {
        "name": "Blue Denim Jeans",
        "category": "bottom",
        "color": "blue",
        "pattern": "solid",
        "occasion_tag": "casual",
        "season": "all-season",
        "brand": "Levi's",
        "formality": "casual",
        "image_url": "/uploads/denim-jeans.jpg",
    },
    {
        "name": "Black Leather Jacket",
        "category": "outerwear",
        "color": "black",
        "pattern": "solid",
        "occasion_tag": "party",
        "season": "fall",
        "brand": "Zara",
        "formality": "smart casual",
        "image_url": "/uploads/leather-jacket.jpg",
    },
    {
        "name": "Navy Blue Chinos",
        "category": "bottom",
        "color": "navy",
        "pattern": "solid",
        "occasion_tag": "office",
        "season": "spring",
        "brand": "Uniqlo",
        "formality": "smart casual",
        "image_url": "/uploads/navy-chinos.jpg",
    },
    {
        "name": "White Running Sneakers",
        "category": "footwear",
        "color": "white",
        "pattern": "solid",
        "occasion_tag": "casual",
        "season": "all-season",
        "brand": "Nike",
        "formality": "casual",
        "image_url": "/uploads/white-sneakers.jpg",
    },
    {
        "name": "Black Crew Neck T-Shirt",
        "category": "top",
        "color": "black",
        "pattern": "solid",
        "occasion_tag": "casual",
        "season": "all-season",
        "brand": "H&M",
        "formality": "casual",
        "image_url": "/uploads/black-tshirt.jpg",
    },
    {
        "name": "Floral Summer Dress",
        "category": "dress",
        "color": "pink",
        "pattern": "printed",
        "occasion_tag": "party",
        "season": "summer",
        "brand": "ASOS",
        "formality": "casual",
        "image_url": "/uploads/floral-dress.jpg",
    },
    {
        "name": "Grey Pullover Hoodie",
        "category": "top",
        "color": "grey",
        "pattern": "solid",
        "occasion_tag": "casual",
        "season": "winter",
        "brand": "Champion",
        "formality": "casual",
        "image_url": "/uploads/grey-hoodie.jpg",
    },
]


def seed():
    db = SessionLocal()
    try:
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

        existing = db.query(ClothingItem).filter(ClothingItem.user_id == user.id).all()
        if existing:
            print(f"Clearing {len(existing)} old items...")
            for item in existing:
                db.delete(item)
            db.flush()

        for item_data in SAMPLE_ITEMS:
            item = ClothingItem(user_id=user.id, **item_data)
            db.add(item)
            print(f"  + {item_data['name']} ({item_data['category']})")

        db.commit()
        print(f"\nSeeded {len(SAMPLE_ITEMS)} items with real images for {user.name}.")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
