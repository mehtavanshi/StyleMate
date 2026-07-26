#!/usr/bin/env python3
"""Add clothing items to an existing wardrobe without deleting anything.

Unlike seed_db.py (which wipes and re-seeds), this only inserts, and skips
names that are already present. Fills the categories the capsule builder needs
but the demo wardrobe lacks: footwear, dress, outerwear, accessory.

    python scripts/seed_more.py [user_id]
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal, engine, Base
from app.models import ClothingItem, User
from app import models  # noqa: F401

Base.metadata.create_all(bind=engine)

# Colors are picked from pairing_engine.HSL_MAP so score_pair_color returns a
# real harmony score instead of falling back to the 0.5 unknown-color default.
ITEMS = [
    # --- footwear: capsule counts top+bottom+shoes, and there were zero shoes
    ("White Leather Sneakers", "footwear", "low_top_sneakers", "white", "solid", "casual", "all-season", "Adidas", "casual", None),
    ("Black Ankle Boots", "footwear", "ankle_boots", "black", "solid", "party", "fall", "Steve Madden", "smart casual", None),
    ("Tan Strappy Sandals", "footwear", "sandals", "tan", "solid", "casual", "summer", "Bata", "casual", None),
    ("Brown Oxford Shoes", "footwear", "oxfords", "brown", "solid", "office", "all-season", "Clarks", "business", None),
    ("Beige Ballet Flats", "footwear", "flats", "beige", "solid", "office", "spring", "Zara", "smart casual", None),

    # --- dress
    ("Black Midi Wrap Dress", "dress", "wrap_dress", "black", "solid", "party", "all-season", "H&M", "smart casual", "knee"),
    ("Olive Shirt Dress", "dress", "shirt_dress", "olive", "solid", "casual", "summer", "Uniqlo", "casual", "knee"),
    ("Navy A-Line Dress", "dress", "a_line_dress", "navy", "solid", "office", "all-season", "Marks & Spencer", "business", "knee"),

    # --- outerwear
    ("Beige Trench Coat", "outerwear", "trench_coat", "beige", "solid", "office", "fall", "Zara", "business", "knee"),
    ("Denim Jacket", "outerwear", "denim_jacket", "blue", "solid", "casual", "spring", "Levi's", "casual", "waist"),
    ("Grey Wool Blazer", "outerwear", "blazer", "grey", "solid", "office", "winter", "Van Heusen", "business", "hip"),

    # --- accessory
    ("Brown Leather Belt", "accessory", "waist_belt", "brown", "solid", "office", "all-season", "Hidesign", "business", None),
    ("Gold Hoop Earrings", "accessory", "jhumkas", "gold", "solid", "party", "all-season", "Accessorize", "smart casual", None),
    ("Black Crossbody Bag", "accessory", "potli_bag", "black", "solid", "casual", "all-season", "Baggit", "casual", None),

    # --- more tops, so the greedy picker has neutrals to build around
    ("Cream Silk Blouse", "top", "regular_top", "cream", "solid", "office", "all-season", "Mango", "business", "hip"),
    ("Grey Crew Neck Tee", "top", "regular_top", "grey", "solid", "casual", "all-season", "Uniqlo", "casual", "hip"),
    ("Olive Utility Shirt", "top", "regular_top", "olive", "solid", "casual", "fall", "H&M", "casual", "hip"),
    ("Burgundy Knit Sweater", "top", "waist_length_top", "burgundy", "solid", "casual", "winter", "Marks & Spencer", "smart casual", "hip"),
    ("Navy Striped Shirt", "top", "regular_top", "navy", "striped", "casual", "spring", "Zara", "smart casual", "hip"),

    # --- more bottoms
    ("Black Tailored Trousers", "bottom", "trousers", "black", "solid", "office", "all-season", "Van Heusen", "business", "ankle"),
    ("Khaki Wide Leg Pants", "bottom", "wide_leg", "khaki", "solid", "office", "summer", "Uniqlo", "smart casual", "ankle"),
    ("White Denim Shorts", "bottom", "shorts", "white", "solid", "casual", "summer", "Levi's", "casual", "thigh"),
    ("Navy Pleated Midi Skirt", "bottom", "pleated_skirt", "navy", "solid", "office", "all-season", "Mango", "smart casual", "knee"),
    ("Grey Joggers", "bottom", "joggers", "grey", "solid", "casual", "winter", "Nike", "casual", "ankle"),
]

FIELDS = (
    "name", "category", "subcategory", "color", "pattern",
    "occasion_tag", "season", "brand", "formality", "garment_length",
)


def seed(user_id: int) -> None:
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            sys.exit(f"No user with id={user_id}. Run scripts/seed_db.py first.")

        existing = db.query(ClothingItem).filter(ClothingItem.user_id == user_id).all()
        have = {(i.name or "").strip().lower() for i in existing}

        # Reuse a real image from the same category so the closet grid isn't
        # full of placeholders. New categories have none, so they stay null —
        # the UI already guards on a missing image_url.
        image_by_cat: dict[str, str] = {}
        for i in existing:
            if i.image_url and i.category not in image_by_cat:
                image_by_cat[i.category] = i.image_url

        added = 0
        for row in ITEMS:
            data = dict(zip(FIELDS, row))
            if data["name"].strip().lower() in have:
                print(f"  = {data['name']} (already there, skipped)")
                continue
            item = ClothingItem(
                user_id=user_id,
                image_url=image_by_cat.get(data["category"]),
                target_gender="unisex",
                embellishments="[]",
                **data,
            )
            db.add(item)
            added += 1
            img = "img" if item.image_url else "no-img"
            print(f"  + {data['name']} ({data['category']}, {img})")

        db.commit()
        total = db.query(ClothingItem).filter(ClothingItem.user_id == user_id).count()
        print(f"\nAdded {added} items. {user.name} now has {total}.")
    finally:
        db.close()


if __name__ == "__main__":
    seed(int(sys.argv[1]) if len(sys.argv) > 1 else 1)
