#!/usr/bin/env python3
"""Seed real fashion products from the Myntra product dataset.

Source: two openly-hosted HuggingFace mirrors of the Kaggle
"fashion-product-images" dataset (originally Myntra catalogue data).

  ashraq/fashion-product-images-small  rich metadata, 60x80 thumbnails
  ceyda/fashion-products-small         384x512 images, thin metadata

Neither has everything, so they are joined on the Myntra product id: metadata
from ashraq, image from ceyda. Images are re-uploaded through the app's own
storage provider rather than hotlinked, because the dataset-server image URLs
are signed and expire.

    python scripts/seed_from_dataset.py --gender women --user-id 1
    python scripts/seed_from_dataset.py --dry-run          # no writes
    python scripts/seed_from_dataset.py --undo             # remove seeded rows

Expects the four parquet files in DATA_DIR (see download command in --help).
"""

from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys
from collections import Counter

KIDS_RE = re.compile(r"\b(kid|kids|kidswear|girl|girl's|girls|boy|boy's|boys|infant|toddler|baby)\b", re.I)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DATA_DIR = os.environ.get("FASHION_DATA_DIR", "/media/rajveer/New Volume/.fashion-data")

# Marks rows this script created, so --undo can find them without guessing.
SEED_TAG = "myntra-dataset"

# Myntra taxonomy -> StyleMate category. Checked most-specific first.
# articleType wins over subCategory because Myntra files jackets and blazers
# under "Topwear", but the capsule builder treats outerwear as its own layer.
OUTERWEAR_TYPES = {
    "Jackets", "Blazers", "Waistcoat", "Rain Jacket", "Nehru Jackets",
    "Sweaters", "Sweatshirts", "Shrug",
}
ACCESSORY_TYPES = {
    "Belts", "Watches", "Handbags", "Backpacks", "Clutches", "Wallets",
    "Sunglasses", "Scarves", "Stoles", "Caps", "Hats", "Earrings",
    "Necklace and Chains", "Bracelet", "Ring", "Jewellery Set", "Bangle",
    "Pendant", "Duffel Bag", "Laptop Bag", "Messenger Bag", "Mobile Pouch",
    # Myntra files dupattas under Topwear, but they drape like a scarf.
    "Dupatta",
}
# articleTypes to drop regardless of where Myntra filed them. "Swimwear" is the
# load-bearing one: the dataset files swimming goggles as Apparel/Bottomwear,
# so the Bottomwear fallback would otherwise seed goggles as a pair of trousers.
SKIP_TYPES = {"Swimwear", "Booties", "Nightdress", "Baby Dolls", "Rompers"}
# One-piece garments; a saree/lehenga behaves like a dress for pairing purposes
# (pairs with footwear and accessories, not with a bottom).
DRESS_TYPES = {"Dresses", "Jumpsuit", "Sarees", "Lehenga Choli", "Salwar", "Churidar"}
TOP_TYPES = {
    "Shirts", "Tshirts", "Tops", "Tunics", "Kurtas", "Kurtis", "Kurta Sets",
    "Camisoles", "Blouse", "Sweatshirt",
}
# Excluded outright: nothing here belongs in an outfit-pairing wardrobe.
SKIP_SUBCATS = {
    "Innerwear", "Fragrance", "Skin Care", "Skin", "Hair", "Makeup", "Nails",
    "Beauty Accessories", "Bath and Body", "Eyes", "Lips", "Free Gifts",
    "Sports Accessories", "Home Furnishing", "Perfumes", "Socks", "Loungewear and Nightwear",
    "Apparel Set", "Water Bottle", "Sports Equipment", "Vouchers", "Umbrellas",
    "Wristbands", "Cufflinks", "Ties", "Accessories", "Shoe Accessories", "Stoles",
    "Mufflers", "Gloves", "Headwear", "Bags",
}

# usage -> (occasion_tag, formality). Myntra's "usage" is the closest thing the
# dataset has to an occasion.
USAGE_MAP = {
    "Casual": ("casual", "casual"),
    "Formal": ("office", "business"),
    "Sports": ("sports", "casual"),
    "Ethnic": ("festive", "smart casual"),
    "Party": ("party", "smart casual"),
    "Smart Casual": ("office", "smart casual"),
    "Travel": ("casual", "casual"),
}

# How many of each category to seed. Best-effort: a shortfall is reported, not
# silently accepted, because a capsule with no footwear scores badly.
QUOTAS = {
    "top": 16, "bottom": 14, "footwear": 8,
    "dress": 5, "outerwear": 5, "accessory": 6,
}


def classify(sub_category: str, article_type: str) -> str | None:
    if sub_category in SKIP_SUBCATS or article_type in SKIP_TYPES:
        return None
    if article_type in ACCESSORY_TYPES:
        return "accessory"
    if article_type in OUTERWEAR_TYPES:
        return "outerwear"
    if article_type in DRESS_TYPES:
        return "dress"
    if article_type in TOP_TYPES or sub_category == "Topwear":
        return "top"
    if sub_category == "Bottomwear":
        return "bottom"
    if sub_category in ("Shoes", "Flip Flops", "Sandal", "Sandals"):
        return "footwear"
    if sub_category == "Dress":
        return "dress"
    return None


def selfcheck() -> None:
    """Assert the taxonomy mapping, including the upstream mislabels it works around."""
    cases = [
        # (subCategory, articleType, expected)
        ("Topwear", "Shirts", "top"),
        ("Topwear", "Kurtas", "top"),
        ("Bottomwear", "Jeans", "bottom"),
        ("Shoes", "Heels", "footwear"),
        ("Flip Flops", "Flip Flops", "footwear"),
        ("Dress", "Dresses", "dress"),
        ("Saree", "Sarees", "dress"),
        # Myntra files these under Topwear; they are not tops.
        ("Topwear", "Jackets", "outerwear"),
        ("Topwear", "Blazers", "outerwear"),
        ("Topwear", "Dupatta", "accessory"),
        ("Watches", "Watches", "accessory"),
        # Swimming goggles really are filed as Apparel/Bottomwear/Swimwear.
        ("Bottomwear", "Swimwear", None),
        ("Innerwear", "Bra", None),
        ("Fragrance", "Perfume", None),
    ]
    for sub, art, expected in cases:
        got = classify(sub, art)
        assert got == expected, f"classify({sub!r},{art!r}) -> {got!r}, want {expected!r}"

    for name in ("Crocs Kids Navy Blue Clogs", "Gini and Jony Girl's Vanya Kidswear",
                 "Nike Boys Blue Tshirt"):
        assert KIDS_RE.search(name), f"kids filter missed {name!r}"
    for name in ("Jealous 21 Women Black Jeans", "Fossil Women Copper Watch"):
        assert not KIDS_RE.search(name), f"kids filter false-positive on {name!r}"

    assert USAGE_MAP["Formal"] == ("office", "business")
    print("selfcheck: all assertions passed")


def load_metadata(gender_keep: set[str]) -> dict[str, dict]:
    """id -> metadata, from the ashraq mirror. Images in this one are ignored."""
    import pyarrow.parquet as pq

    cols = [
        "id", "gender", "masterCategory", "subCategory", "articleType",
        "baseColour", "season", "usage", "productDisplayName",
    ]
    out: dict[str, dict] = {}
    for shard in ("ashraq-0.parquet", "ashraq-1.parquet"):
        table = pq.read_table(os.path.join(DATA_DIR, shard), columns=cols)
        for batch in table.to_batches(1024):
            for row in batch.to_pylist():
                if row["gender"] not in gender_keep:
                    continue
                # The gender column is unreliable for children's items — the
                # dataset tags "Gini and Jony Girl's ... Kidswear" as Women and
                # "Crocs Kids ... Clogs" as Unisex. The name is the only signal.
                if KIDS_RE.search(row["productDisplayName"] or ""):
                    continue
                cat = classify(row["subCategory"] or "", row["articleType"] or "")
                if not cat:
                    continue
                row["_category"] = cat
                out[str(row["id"])] = row
    return out


def pick_images(wanted: dict[str, dict], quotas: dict[str, int]) -> list[tuple[dict, bytes]]:
    """Stream the ceyda shards, keeping the first image for each wanted id.

    Streamed row-group at a time: the shards are ~300 MB each and holding the
    decoded image column for 42k rows at once would be gigabytes.
    """
    import pyarrow.parquet as pq

    remaining = dict(quotas)
    picked: list[tuple[dict, bytes]] = []
    for shard in ("ceyda-0.parquet", "ceyda-1.parquet"):
        pf = pq.ParquetFile(os.path.join(DATA_DIR, shard))
        for batch in pf.iter_batches(batch_size=256, columns=["id", "image"]):
            for row in batch.to_pylist():
                pid = str(row["id"])
                meta = wanted.get(pid)
                if not meta:
                    continue
                cat = meta["_category"]
                if remaining.get(cat, 0) <= 0:
                    continue
                img = row["image"]
                data = img.get("bytes") if isinstance(img, dict) else img
                if not data:
                    continue
                remaining[cat] -= 1
                picked.append((meta, data))
                del wanted[pid]
            if all(v <= 0 for v in remaining.values()):
                return picked
    return picked


def to_item_fields(meta: dict, gender_label: str) -> dict:
    occasion, formality = USAGE_MAP.get(meta.get("usage") or "", ("casual", "casual"))
    season = (meta.get("season") or "").lower() or "all-season"
    return {
        "name": meta.get("productDisplayName") or f"Myntra {meta['id']}",
        "category": meta["_category"],
        "subcategory": (meta.get("articleType") or "").lower().replace(" ", "_") or None,
        # baseColour like "Navy Blue" resolves through pairing_engine.HSL_MAP's
        # substring match, so it scores as a real color rather than the 0.5 default.
        "color": (meta.get("baseColour") or "").lower() or None,
        # The dataset has no pattern column. Leave it NULL rather than assert
        # "solid" — several of these are visibly printed or embroidered, and
        # _hard_rule_score would be reasoning from a fact we made up.
        "pattern": None,
        "occasion_tag": occasion,
        "season": season,
        "formality": formality,
        # Deliberately not the dataset's per-item gender: _gender_compatible is a
        # hard 0.0 filter, so a mixed-gender wardrobe cannot pair across itself.
        "target_gender": gender_label,
        "brand": None,  # dataset has no brand column; it's embedded in the name
        "embellishments": "[]",
        "tags": json.dumps({"source": SEED_TAG, "myntra_id": str(meta["id"])}),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--user-id", type=int, default=1)
    ap.add_argument("--gender", default="women", choices=["women", "men"])
    ap.add_argument("--dry-run", action="store_true", help="classify and count, upload nothing")
    ap.add_argument("--undo", action="store_true", help="delete rows this script created")
    ap.add_argument("--selfcheck", action="store_true", help="assert the taxonomy mapping and exit")
    args = ap.parse_args()

    if args.selfcheck:
        selfcheck()
        return

    from app.database import SessionLocal
    from app.models import ClothingItem, User

    db = SessionLocal()
    try:
        if args.undo:
            rows = (
                db.query(ClothingItem)
                .filter(
                    ClothingItem.user_id == args.user_id,
                    ClothingItem.tags.like(f'%"{SEED_TAG}"%'),
                )
                .all()
            )
            for r in rows:
                db.delete(r)
            db.commit()
            print(f"Deleted {len(rows)} dataset-seeded items (uploaded images left in the bucket).")
            return

        if not db.query(User).filter(User.id == args.user_id).first():
            sys.exit(f"No user with id={args.user_id}.")

        keep = {"Women", "Unisex"} if args.gender == "women" else {"Men", "Unisex"}
        print(f"Reading metadata ({args.gender} + unisex)...")
        wanted = load_metadata(keep)
        print(f"  {len(wanted)} candidate products")
        print(dict(Counter(m["_category"] for m in wanted.values())))

        print("\nMatching against high-resolution images...")
        picked = pick_images(wanted, QUOTAS)
        got = Counter(m["_category"] for m, _ in picked)
        print(f"  matched {len(picked)} items: {dict(got)}")
        for cat, want in QUOTAS.items():
            if got[cat] < want:
                print(f"  ! short on {cat}: {got[cat]}/{want}")

        if args.dry_run:
            print("\n--dry-run, nothing written. Sample:")
            for meta, data in picked[:8]:
                f = to_item_fields(meta, args.gender)
                print(f"  {f['category']:9} {f['color']:14} {f['name'][:48]:48} {len(data)/1024:.0f} KB")
            return

        from app.storage import get_storage_provider
        from PIL import Image

        storage = get_storage_provider()
        print(f"\nUploading via {type(storage).__name__}...")
        added = 0
        for meta, data in picked:
            fields = to_item_fields(meta, args.gender)
            try:
                # Re-encode to JPEG: the parquet payload is PNG for some rows and
                # the bucket is served straight to the client.
                buf = io.BytesIO()
                Image.open(io.BytesIO(data)).convert("RGB").save(buf, "JPEG", quality=88)
                path = storage.save_file(buf.getvalue(), f"{meta['id']}.jpg", "image/jpeg")
                url = storage.get_file_url(path)
            except Exception as exc:
                print(f"  ! upload failed for {meta['id']}: {type(exc).__name__} {exc}")
                continue
            db.add(ClothingItem(user_id=args.user_id, image_url=url, **fields))
            added += 1
            print(f"  + {fields['category']:9} {fields['name'][:52]}")

        db.commit()
        total = db.query(ClothingItem).filter(ClothingItem.user_id == args.user_id).count()
        print(f"\nAdded {added} real products. Wardrobe is now {total} items.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
