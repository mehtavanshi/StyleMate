"""Debug script: run tagging on diverse test images and show all debug logs."""

import logging
import sys

# Enable DEBUG logging for our modules
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s:%(lineno)d %(message)s",
    stream=sys.stdout,
)

# Avoid HTTP request debug noise
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("PIL").setLevel(logging.WARNING)

import traceback

from app.routers.tagging import _tag_item_fashion_clip, _tag_item, CANDIDATE_LABELS

TEST_IMAGES = [
    ("floral-dress.jpg",  "women's dress with floral pattern"),
    ("oxford-shirt.jpg",  "men's formal oxford shirt"),
    ("leather-jacket.jpg","black leather jacket"),
    ("denim-jeans.jpg",   "blue denim jeans"),
    ("black-tshirt.jpg",  "black t-shirt"),
]

print("=" * 90)
print("DEBUG TAGGING: Running classification on 5 diverse test images")
print("=" * 90)

for filename, description in TEST_IMAGES:
    image_url = f"/uploads/{filename}"
    print(f"\n{'─' * 90}")
    print(f"IMAGE: {filename}  —  {description}")
    print(f"{'─' * 90}")

    try:
        result = _tag_item_fashion_clip(image_url)

        print(f"\n  ▶ RESULTS for {filename}:")
        for key in ["category", "dominant_color", "pattern", "target_gender", "occasion_tag", "season", "fabric_type", "fit_type", "sleeve_length", "formality_score", "style_tags"]:
            val = result.get(key)
            if val is not None:
                print(f"    {key:20s} = {val}")
        if result.get("_warnings"):
            print(f"    {'WARNINGS':20s} = {result['_warnings']}")

        conf = result.get("_confidence", {})
        print(f"    {'Confidences:':20s} { {k: round(v, 4) for k, v in conf.items()} }")

    except Exception:
        print(f"  ▶ FAILED for {filename}:")
        traceback.print_exc()

print(f"\n{'=' * 90}")
print("DEBUG TAGGING COMPLETE")
print(f"{'=' * 90}")
