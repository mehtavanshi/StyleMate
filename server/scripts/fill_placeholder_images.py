#!/usr/bin/env python3
"""Give items with no photo a color-accurate placeholder swatch.

Colors come from pairing_engine.HSL_MAP — the same table the pairing scorer
uses — so a swatch actually looks like the color the recommender thinks the
garment is. Only touches rows where image_url is NULL; real uploads are left
alone.

    python scripts/fill_placeholder_images.py [user_id] [--undo]
"""

import colorsys
import os
import sys
from urllib.parse import quote

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal
from app.models import ClothingItem
from app.pairing_engine import _color_to_hsl

PLACEHOLDER_HOST = "https://placehold.co"


def swatch_url(name: str | None, color: str | None) -> str:
    hsl = _color_to_hsl(color) or (0, 0, 75)  # unknown color -> light grey
    h, s, l = hsl
    r, g, b = colorsys.hls_to_rgb(h / 360, l / 100, s / 100)
    bg = f"{round(r * 255):02x}{round(g * 255):02x}{round(b * 255):02x}"
    # Perceptual luminance, not HSL lightness: yellow at L=50 is far brighter
    # than navy at L=50, and picking on L alone puts white text on gold.
    fg = "000000" if (0.299 * r + 0.587 * g + 0.114 * b) > 0.55 else "ffffff"
    label = quote((name or "item").replace(" ", "+"), safe="+")
    return f"{PLACEHOLDER_HOST}/400x500/{bg}/{fg}.png?text={label}"


def main(user_id: int, undo: bool) -> None:
    db = SessionLocal()
    try:
        if undo:
            rows = (
                db.query(ClothingItem)
                .filter(
                    ClothingItem.user_id == user_id,
                    ClothingItem.image_url.like(f"{PLACEHOLDER_HOST}%"),
                )
                .all()
            )
            for item in rows:
                item.image_url = None
            db.commit()
            print(f"Cleared {len(rows)} placeholder images.")
            return

        rows = (
            db.query(ClothingItem)
            .filter(ClothingItem.user_id == user_id, ClothingItem.image_url.is_(None))
            .all()
        )
        for item in rows:
            item.image_url = swatch_url(item.name, item.color)
            print(f"  + {item.name} ({item.color})")
        db.commit()
        print(f"\nFilled {len(rows)} placeholders. Re-run with --undo to remove.")
    finally:
        db.close()


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--undo"]
    main(int(args[0]) if args else 1, "--undo" in sys.argv)
