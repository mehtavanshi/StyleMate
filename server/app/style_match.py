"""Style Match Suggestions engine.

Given ONE selected wardrobe item, recommend everything that matches it
(bottoms, tops, footwear, accessories, layering), the best/avoid color
pairings, occasion outfit ideas, and shopping links.

This is distinct from "Complete the Look" / gap detection:
- gap detection analyses the WHOLE wardrobe and finds what's MISSING;
- style match works on a SINGLE item and finds what GOES WELL WITH it.

Recommendations are deterministic and fashion-aware (no AI call needed):
category pairing rules, color theory (complementary / analogous /
monochromatic / triadic / neutral), fabric/fit/season compatibility, and
the user's own wardrobe are all consulted. Every suggestion carries a
compatibility score (0–100) and a human-readable reason.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Literal
from urllib.parse import quote_plus

from sqlalchemy.orm import Session

from app.models import ClothingItem
from app.shopping_links import build_google_shopping_link, build_meesho_search_link
from app.pairing_engine import (
    HSL_MAP,
    KNOWN_NEUTRAL_NAMES,
    _FASHION_CLASHES,
    _color_to_hsl,
    _hue_diff,
    _is_neutral_hsl,
    _normalise,
)

logger = logging.getLogger(__name__)


def _primary_occasion(occasion_tag: str | None) -> str | None:
    if not occasion_tag:
        return None
    return occasion_tag.split(",")[0].strip()


# ── Category pairing rules ──
# For a selected item of a given category, which other categories "go with" it.
# Ordered by typical importance for the UI.

_MATCHING_CATEGORIES: dict[str, list[str]] = {
    "top": ["bottom", "footwear", "accessory", "outerwear"],
    "bottom": ["top", "accessory", "footwear", "outerwear"],
    "dress": ["footwear", "accessory", "outerwear"],
    "outerwear": ["top", "bottom", "footwear", "accessory"],
    "footwear": ["top", "bottom", "dress", "accessory"],
    "accessory": ["top", "bottom", "dress", "footwear"],
    "kurti": ["bottom", "accessory", "footwear", "outerwear"],
}

# Section label per target category (what to show the user).
_SECTION_LABELS: dict[str, str] = {
    "top": "matchingTops",
    "bottom": "matchingBottoms",
    "footwear": "matchingFootwear",
    "accessory": "matchingAccessories",
    "outerwear": "layeringSuggestions",
    "dress": "matchingFootwear",
}

_OCCASIONS = [
    "casual", "office", "formal", "party", "wedding",
    "college", "date", "travel", "traditional", "festive", "streetwear",
]

# Shopping deep-link builders (no scraping — only search URLs).
_SHOP_BUILDERS: dict[str, str] = {
    "meesho": "https://www.meesho.com/search?q=",
    "myntra": "https://www.myntra.com/",
    "ajio": "https://www.ajio.com/search/",
    "amazon": "https://www.amazon.in/s?k=",
    "flipkart": "https://www.flipkart.com/search?q=",
}


# ── Attribute-driven suggestion tables ──
# Keyed by (target_category) → dict of (occasion, formality_bucket) → suggestions.
# Each suggestion has a name, gender filter, and optional color override.
# gender: "men" | "women" | "unisex" controls filtering.
# formality_bucket: "low" | "medium" | "high" | "any" (any matches all).

_FOOTWEAR_TABLE: dict[tuple[str, str], list[dict]] = {
    ("formal", "high"): [
        {"name": "Black Oxford Shoes", "gender": "men"},
        {"name": "Brown Brogues", "gender": "men"},
        {"name": "Nude Pumps", "gender": "women"},
        {"name": "Black Stiletto Heels", "gender": "women"},
        {"name": "Black Patent Loafers", "gender": "unisex"},
    ],
    ("formal", "medium"): [
        {"name": "Tan Derby Shoes", "gender": "men"},
        {"name": "Block Heel Pumps", "gender": "women"},
        {"name": "Brown Monk Strap Shoes", "gender": "unisex"},
    ],
    ("office", "high"): [
        {"name": "Brown Oxford Shoes", "gender": "men"},
        {"name": "Black Monk Strap Shoes", "gender": "men"},
        {"name": "Nude Block Heels", "gender": "women"},
        {"name": "Black Kitten Heels", "gender": "women"},
        {"name": "Tan Loafers", "gender": "unisex"},
    ],
    ("office", "medium"): [
        {"name": "Black Loafers", "gender": "unisex"},
        {"name": "Brown Chelsea Boots", "gender": "men"},
        {"name": "Pointed-Toe Flats", "gender": "women"},
        {"name": "Suede Loafers", "gender": "unisex"},
    ],
    ("casual", "low"): [
        {"name": "White Canvas Sneakers", "gender": "unisex"},
        {"name": "Beige Slip-Ons", "gender": "unisex"},
        {"name": "Brown Espadrilles", "gender": "unisex"},
        {"name": "Canvas Loafers", "gender": "unisex"},
        {"name": "White Running Shoes", "gender": "unisex"},
    ],
    ("casual", "medium"): [
        {"name": "White Leather Sneakers", "gender": "unisex"},
        {"name": "Brown Desert Boots", "gender": "men"},
        {"name": "Tan Mules", "gender": "women"},
        {"name": "Suede Sneakers", "gender": "unisex"},
    ],
    ("party", "medium"): [
        {"name": "Metallic Statement Heels", "gender": "women"},
        {"name": "Black Platform Sneakers", "gender": "unisex"},
        {"name": "Patent Leather Loafers", "gender": "men"},
        {"name": "Embellished Flats", "gender": "women"},
        {"name": "Chunky White Sneakers", "gender": "unisex"},
    ],
    ("party", "high"): [
        {"name": "Red Stiletto Heels", "gender": "women"},
        {"name": "Black Patent Oxfords", "gender": "men"},
        {"name": "Sequin Platform Heels", "gender": "women"},
    ],
    ("traditional", "medium"): [
        {"name": "Brown Juttis", "gender": "men"},
        {"name": "Gold Kolhapuri Chappals", "gender": "women"},
        {"name": "Embroidered Mojaris", "gender": "unisex"},
        {"name": "Leather Kolhapuris", "gender": "women"},
        {"name": "Tan Juttis", "gender": "unisex"},
    ],
    ("traditional", "high"): [
        {"name": "Embroidered Juttis", "gender": "men"},
        {"name": "Gold Wedge Juttis", "gender": "women"},
        {"name": "Silk Mojaris", "gender": "unisex"},
    ],
    ("wedding", "high"): [
        {"name": "Gold Embroidered Juttis", "gender": "men"},
        {"name": "Gold Stiletto Heels", "gender": "women"},
        {"name": "Brocade Mojaris", "gender": "unisex"},
        {"name": "Kundan Work Juttis", "gender": "women"},
    ],
    ("wedding", "medium"): [
        {"name": "Velvet Juttis", "gender": "unisex"},
        {"name": "Block Heel Sandals", "gender": "women"},
        {"name": "Tan Oxford Shoes", "gender": "men"},
    ],
    ("festive", "medium"): [
        {"name": "Gold Kolhapuri Sandals", "gender": "women"},
        {"name": "Embroidered Mojaris", "gender": "men"},
        {"name": "Mirror-Work Juttis", "gender": "unisex"},
    ],
    ("streetwear", "low"): [
        {"name": "Chunky White Sneakers", "gender": "unisex"},
        {"name": "High-Top Canvas Shoes", "gender": "unisex"},
        {"name": "Platform Sneakers", "gender": "women"},
        {"name": "Retro Running Shoes", "gender": "unisex"},
        {"name": "Skate Shoes", "gender": "unisex"},
    ],
    ("college", "low"): [
        {"name": "White Sneakers", "gender": "unisex"},
        {"name": "Canvas High-Tops", "gender": "unisex"},
        {"name": "Slip-On Sneakers", "gender": "unisex"},
        {"name": "Colorful Running Shoes", "gender": "unisex"},
    ],
    ("date", "medium"): [
        {"name": "White Leather Sneakers", "gender": "unisex"},
        {"name": "Black Ankle Boots", "gender": "unisex"},
        {"name": "Nude Block Heels", "gender": "women"},
        {"name": "Suede Chelsea Boots", "gender": "men"},
    ],
    ("travel", "low"): [
        {"name": "Walking Sneakers", "gender": "unisex"},
        {"name": "Cushioned Running Shoes", "gender": "unisex"},
        {"name": "Slip-On Travel Shoes", "gender": "unisex"},
        {"name": "Lightweight Hiking Shoes", "gender": "unisex"},
    ],
}

_ACCESSORY_TABLE: dict[tuple[str, str], list[dict]] = {
    ("formal", "high"): [
        {"name": "Silver Chronograph Watch", "gender": "men"},
        {"name": "Pearl Stud Earrings", "gender": "women"},
        {"name": "Leather Briefcase", "gender": "unisex"},
        {"name": "Silk Pocket Square", "gender": "men"},
        {"name": "Crystal Pendant Necklace", "gender": "women"},
    ],
    ("formal", "medium"): [
        {"name": "Minimal Silver Watch", "gender": "unisex"},
        {"name": "Leather Belt", "gender": "unisex"},
        {"name": "Structured Tote Bag", "gender": "women"},
        {"name": "Cufflinks Set", "gender": "men"},
    ],
    ("office", "medium"): [
        {"name": "Minimal Analog Watch", "gender": "unisex"},
        {"name": "Leather Belt", "gender": "unisex"},
        {"name": "Structured Laptop Bag", "gender": "unisex"},
        {"name": "Simple Stud Earrings", "gender": "women"},
        {"name": "Woven Bracelet", "gender": "unisex"},
    ],
    ("office", "high"): [
        {"name": "Silver Watch", "gender": "men"},
        {"name": "Pearl Earrings", "gender": "women"},
        {"name": "Leather Portfolio Bag", "gender": "unisex"},
        {"name": "Silk Scarf", "gender": "unisex"},
    ],
    ("casual", "low"): [
        {"name": "Canvas Sling Bag", "gender": "unisex"},
        {"name": "Casual Digital Watch", "gender": "unisex"},
        {"name": "Baseball Cap", "gender": "unisex"},
        {"name": "Woven Bracelet", "gender": "unisex"},
        {"name": "Sunglasses", "gender": "unisex"},
    ],
    ("casual", "medium"): [
        {"name": "Leather Crossbody Bag", "gender": "unisex"},
        {"name": "Minimal Chain Necklace", "gender": "unisex"},
        {"name": "Canvas Tote", "gender": "unisex"},
        {"name": "Aviator Sunglasses", "gender": "unisex"},
    ],
    ("party", "medium"): [
        {"name": "Statement Chandelier Earrings", "gender": "women"},
        {"name": "Chain Link Bracelet", "gender": "unisex"},
        {"name": "Sequin Clutch", "gender": "women"},
        {"name": "Cocktail Ring", "gender": "women"},
        {"name": "Chunky Chain Necklace", "gender": "unisex"},
    ],
    ("party", "high"): [
        {"name": "Crystal Drop Earrings", "gender": "women"},
        {"name": "Diamond Stud Earrings", "gender": "unisex"},
        {"name": "Metallic Box Clutch", "gender": "women"},
    ],
    ("traditional", "medium"): [
        {"name": "Kundan Jhumka Earrings", "gender": "women"},
        {"name": "Embroidered Potli Bag", "gender": "women"},
        {"name": "Silver Kada Bracelet", "gender": "men"},
        {"name": "Statement Bangles Set", "gender": "women"},
        {"name": "Leather Mojaris Keychain", "gender": "unisex"},
    ],
    ("traditional", "high"): [
        {"name": "Gold Jhumka Earrings", "gender": "women"},
        {"name": "Pearl Polki Set", "gender": "women"},
        {"name": "Silk Potli Bag", "gender": "unisex"},
    ],
    ("wedding", "high"): [
        {"name": "Kundan Necklace Set", "gender": "women"},
        {"name": "Gold Chain with Pendant", "gender": "men"},
        {"name": "Embroidered Clutch", "gender": "women"},
        {"name": "Brooch Pin", "gender": "unisex"},
    ],
    ("wedding", "medium"): [
        {"name": "Statement Earrings", "gender": "women"},
        {"name": "Silk Dupatta", "gender": "unisex"},
        {"name": "Leather Belt", "gender": "men"},
    ],
    ("festive", "medium"): [
        {"name": "Kundan Jhumkas", "gender": "women"},
        {"name": "Mirror-Work Clutch", "gender": "women"},
        {"name": "Silver Cuff Bracelet", "gender": "unisex"},
        {"name": "Thread Bangle Set", "gender": "women"},
    ],
    ("streetwear", "low"): [
        {"name": "Baseball Cap", "gender": "unisex"},
        {"name": "Crossbody Bag", "gender": "unisex"},
        {"name": "Chunky Chain Necklace", "gender": "unisex"},
        {"name": "Bucket Hat", "gender": "unisex"},
        {"name": "Digital Watch", "gender": "unisex"},
    ],
    ("college", "low"): [
        {"name": "Backpack", "gender": "unisex"},
        {"name": "Casual Watch", "gender": "unisex"},
        {"name": "Phone Crossbody", "gender": "unisex"},
        {"name": "Woven Wristband", "gender": "unisex"},
    ],
    ("date", "medium"): [
        {"name": "Delicate Pendant Necklace", "gender": "women"},
        {"name": "Leather Wallet", "gender": "unisex"},
        {"name": "Minimal Watch", "gender": "unisex"},
        {"name": "Clutch Bag", "gender": "women"},
    ],
    ("travel", "low"): [
        {"name": "Anti-Theft Crossbody", "gender": "unisex"},
        {"name": "Wide-Brim Sun Hat", "gender": "unisex"},
        {"name": "Travel Wallet", "gender": "unisex"},
        {"name": "UV Sunglasses", "gender": "unisex"},
    ],
}

_OUTERWEAR_TABLE: dict[tuple[str, str], list[dict]] = {
    ("formal", "high"): [
        {"name": "Tailored Navy Blazer", "gender": "men"},
        {"name": "Wool Overcoat", "gender": "men"},
        {"name": "Structured Pencil Coat", "gender": "women"},
        {"name": "Cashmere Cardigan", "gender": "women"},
        {"name": "Charcoal Blazer", "gender": "unisex"},
    ],
    ("formal", "medium"): [
        {"name": "Slim-Fit Blazer", "gender": "unisex"},
        {"name": "Wool Blend Coat", "gender": "unisex"},
        {"name": "Structured Jacket", "gender": "unisex"},
    ],
    ("office", "medium"): [
        {"name": "Structured Blazer", "gender": "unisex"},
        {"name": "Trench Coat", "gender": "unisex"},
        {"name": "Wool Cardigan", "gender": "unisex"},
        {"name": "Tailored Vest", "gender": "unisex"},
    ],
    ("office", "high"): [
        {"name": "Navy Blazer", "gender": "men"},
        {"name": "Cropped Blazer", "gender": "women"},
        {"name": "Camel Overcoat", "gender": "unisex"},
    ],
    ("casual", "low"): [
        {"name": "Denim Jacket", "gender": "unisex"},
        {"name": "Bomber Jacket", "gender": "unisex"},
        {"name": "Knit Cardigan", "gender": "unisex"},
        {"name": "Overshirt", "gender": "unisex"},
        {"name": "Hoodie", "gender": "unisex"},
    ],
    ("casual", "medium"): [
        {"name": "Suede Jacket", "gender": "unisex"},
        {"name": "Quilted Vest", "gender": "unisex"},
        {"name": "Cotton Utility Jacket", "gender": "unisex"},
    ],
    ("party", "medium"): [
        {"name": "Velvet Blazer", "gender": "unisex"},
        {"name": "Leather Jacket", "gender": "unisex"},
        {"name": "Sequin Shrug", "gender": "women"},
        {"name": "Embroidered Jacket", "gender": "unisex"},
    ],
    ("traditional", "medium"): [
        {"name": "Nehru Jacket", "gender": "men"},
        {"name": "Embroidered Shawl", "gender": "unisex"},
        {"name": "Silk Stole", "gender": "women"},
        {"name": "Koti Vest", "gender": "unisex"},
    ],
    ("traditional", "high"): [
        {"name": "Brocade Nehru Jacket", "gender": "men"},
        {"name": "Embroidered Cape", "gender": "women"},
        {"name": "Woven Stole", "gender": "unisex"},
    ],
    ("wedding", "high"): [
        {"name": "Brocade Sherwani Jacket", "gender": "men"},
        {"name": "Embroidered Cape", "gender": "women"},
        {"name": "Silk Shawl", "gender": "unisex"},
    ],
    ("festive", "medium"): [
        {"name": "Embroidered Nehru Jacket", "gender": "men"},
        {"name": "Mirror-Work Shrug", "gender": "women"},
        {"name": "Woven Stole", "gender": "unisex"},
    ],
    ("streetwear", "low"): [
        {"name": "Oversized Puffer Jacket", "gender": "unisex"},
        {"name": "Windbreaker", "gender": "unisex"},
        {"name": "Cargo Vest", "gender": "unisex"},
        {"name": "Cropped Hoodie", "gender": "women"},
        {"name": "Bomber Jacket", "gender": "unisex"},
    ],
    ("college", "low"): [
        {"name": "Denim Jacket", "gender": "unisex"},
        {"name": "Hoodie", "gender": "unisex"},
        {"name": "Zip-Up Fleece", "gender": "unisex"},
    ],
    ("date", "medium"): [
        {"name": "Tailored Blazer", "gender": "unisex"},
        {"name": "Leather Jacket", "gender": "unisex"},
        {"name": "Wool Coat", "gender": "unisex"},
    ],
    ("travel", "low"): [
        {"name": "Packable Rain Jacket", "gender": "unisex"},
        {"name": "Fleece Zip-Up", "gender": "unisex"},
        {"name": "Lightweight Puffer", "gender": "unisex"},
    ],
}

_TOP_TABLE: dict[tuple[str, str], list[dict]] = {
    ("formal", "high"): [
        {"name": "White Dress Shirt", "gender": "men"},
        {"name": "Silk Blouse", "gender": "women"},
        {"name": "Pin-Stripe Shirt", "gender": "unisex"},
        {"name": "French Cuff Shirt", "gender": "men"},
    ],
    ("office", "medium"): [
        {"name": "White Button-Down Shirt", "gender": "unisex"},
        {"name": "Navy Polo Shirt", "gender": "unisex"},
        {"name": "Camel Knit Sweater", "gender": "unisex"},
        {"name": "Oxford Shirt", "gender": "unisex"},
    ],
    ("casual", "low"): [
        {"name": "White T-Shirt", "gender": "unisex"},
        {"name": "Grey Henley", "gender": "unisex"},
        {"name": "Striped Breton Top", "gender": "unisex"},
        {"name": "Linen Camp-Collar Shirt", "gender": "unisex"},
        {"name": "Graphic Tee", "gender": "unisex"},
    ],
    ("party", "medium"): [
        {"name": "Sequin Top", "gender": "women"},
        {"name": "Silk Shirt", "gender": "unisex"},
        {"name": "Velvet Blazer Top", "gender": "unisex"},
        {"name": "Embellished Blouse", "gender": "women"},
    ],
    ("traditional", "medium"): [
        {"name": "Embroidered Kurta", "gender": "men"},
        {"name": "Anarkali Kurti", "gender": "women"},
        {"name": "Chikankari Shirt", "gender": "unisex"},
        {"name": "Block-Print Kurti", "gender": "women"},
    ],
    ("traditional", "high"): [
        {"name": "Silk Kurta", "gender": "men"},
        {"name": "Zardozi Work Kurti", "gender": "women"},
        {"name": "Brocade Shirt", "gender": "unisex"},
    ],
    ("wedding", "high"): [
        {"name": "Embroidered Sherwani Shirt", "gender": "men"},
        {"name": "Lehenga Blouse", "gender": "women"},
        {"name": "Brocade Kurta", "gender": "unisex"},
    ],
    ("streetwear", "low"): [
        {"name": "Oversized Graphic Tee", "gender": "unisex"},
        {"name": "Cropped Hoodie", "gender": "women"},
        {"name": "Logo Sweatshirt", "gender": "unisex"},
        {"name": "Tie-Dye Tee", "gender": "unisex"},
    ],
    ("college", "low"): [
        {"name": "Graphic T-Shirt", "gender": "unisex"},
        {"name": "Plaid Shirt", "gender": "unisex"},
        {"name": "Oversized Sweatshirt", "gender": "unisex"},
    ],
    ("date", "medium"): [
        {"name": "Fitted Polo Shirt", "gender": "men"},
        {"name": "Off-Shoulder Top", "gender": "women"},
        {"name": "Linen Shirt", "gender": "unisex"},
    ],
    ("travel", "low"): [
        {"name": "Moisture-Wicking Polo", "gender": "unisex"},
        {"name": "Packable Fleece", "gender": "unisex"},
        {"name": "Quick-Dry T-Shirt", "gender": "unisex"},
    ],
}

_BOTTOM_TABLE: dict[tuple[str, str], list[dict]] = {
    ("formal", "high"): [
        {"name": "Black Tailored Trousers", "gender": "men"},
        {"name": "Navy Pleated Trousers", "gender": "men"},
        {"name": "High-Waist Wide Leg Trousers", "gender": "women"},
        {"name": "Pencil Skirt", "gender": "women"},
    ],
    ("office", "medium"): [
        {"name": "Navy Chinos", "gender": "unisex"},
        {"name": "Black Straight-Leg Trousers", "gender": "unisex"},
        {"name": "Grey Wool Trousers", "gender": "unisex"},
        {"name": "Tailored Cigarette Pants", "gender": "women"},
    ],
    ("casual", "low"): [
        {"name": "Blue Straight Jeans", "gender": "unisex"},
        {"name": "Black Slim Jeans", "gender": "unisex"},
        {"name": "Khaki Chinos", "gender": "unisex"},
        {"name": "Denim Shorts", "gender": "unisex"},
        {"name": "Linen Trousers", "gender": "unisex"},
    ],
    ("party", "medium"): [
        {"name": "Black Leather Pants", "gender": "unisex"},
        {"name": "Sequin Mini Skirt", "gender": "women"},
        {"name": "Velvet Trousers", "gender": "unisex"},
        {"name": "Metallic Wide Leg Pants", "gender": "women"},
    ],
    ("traditional", "medium"): [
        {"name": "White Churidar Pants", "gender": "men"},
        {"name": "Embroidered Palazzo Pants", "gender": "women"},
        {"name": "Cotton Dhoti Pants", "gender": "unisex"},
        {"name": "Sharara Pants", "gender": "women"},
    ],
    ("traditional", "high"): [
        {"name": "Silk Dhoti Pants", "gender": "men"},
        {"name": "Brocade Lehenga Skirt", "gender": "women"},
    ],
    ("wedding", "high"): [
        {"name": "Embroidered Churidar", "gender": "men"},
        {"name": "Lehenga Skirt", "gender": "women"},
        {"name": "Silk Dhoti", "gender": "men"},
    ],
    ("streetwear", "low"): [
        {"name": "Wide Leg Cargo Pants", "gender": "unisex"},
        {"name": "Distressed Jeans", "gender": "unisex"},
        {"name": "Track Pants", "gender": "unisex"},
        {"name": "Baggy Jeans", "gender": "unisex"},
    ],
    ("college", "low"): [
        {"name": "Blue Jeans", "gender": "unisex"},
        {"name": "Cargo Pants", "gender": "unisex"},
        {"name": "Jogger Pants", "gender": "unisex"},
    ],
    ("date", "medium"): [
        {"name": "Slim-Fit Chinos", "gender": "men"},
        {"name": "High-Waist Trousers", "gender": "women"},
        {"name": "Tailored Jeans", "gender": "unisex"},
    ],
    ("travel", "low"): [
        {"name": "Stretch Joggers", "gender": "unisex"},
        {"name": "Quick-Dry Cargo Pants", "gender": "unisex"},
        {"name": "Comfort-Fit Chinos", "gender": "unisex"},
    ],
}

_SUGGESTION_TABLES: dict[str, dict[tuple[str, str], list[dict]]] = {
    "footwear": _FOOTWEAR_TABLE,
    "accessory": _ACCESSORY_TABLE,
    "outerwear": _OUTERWEAR_TABLE,
    "top": _TOP_TABLE,
    "bottom": _BOTTOM_TABLE,
}

# Fallback when no occasion/formality match is found.
_DEFAULT_SUGGESTIONS: dict[str, list[dict]] = {
    "footwear": [
        {"name": "White Sneakers", "gender": "unisex"},
        {"name": "Black Loafers", "gender": "unisex"},
        {"name": "Brown Chelsea Boots", "gender": "unisex"},
    ],
    "accessory": [
        {"name": "Minimal Watch", "gender": "unisex"},
        {"name": "Leather Belt", "gender": "unisex"},
        {"name": "Sunglasses", "gender": "unisex"},
    ],
    "outerwear": [
        {"name": "Denim Jacket", "gender": "unisex"},
        {"name": "Structured Blazer", "gender": "unisex"},
        {"name": "Knit Cardigan", "gender": "unisex"},
    ],
    "top": [
        {"name": "White Shirt", "gender": "unisex"},
        {"name": "Black T-Shirt", "gender": "unisex"},
        {"name": "Grey Sweater", "gender": "unisex"},
    ],
    "bottom": [
        {"name": "Blue Jeans", "gender": "unisex"},
        {"name": "Black Trousers", "gender": "unisex"},
        {"name": "Khaki Chinos", "gender": "unisex"},
    ],
}

# Season inference from item names.
_NAME_SEASON_HINTS: list[tuple[str, str]] = [
    ("boot", "winter"), ("boots", "winter"), ("ankle boot", "winter"),
    ("snow", "winter"), ("wool", "winter"), ("parka", "winter"),
    ("puffer", "winter"), ("fleece", "winter"),
    ("sandal", "summer"), ("flip flop", "summer"), ("espadrille", "summer"),
    ("slide", "summer"), ("kolhapuri", "summer"), ("chappal", "summer"),
    ("sneaker", "all-season"), ("sneakers", "all-season"),
    ("loafer", "all-season"), ("loafers", "all-season"),
    ("oxford", "all-season"), ("oxfords", "all-season"),
    ("heel", "all-season"), ("heels", "all-season"),
    ("jutti", "all-season"), ("juttis", "all-season"),
    ("mojari", "all-season"), ("mojaris", "all-season"),
]

# Occasion inference from item names.
_NAME_OCCASION_HINTS: list[tuple[str, str]] = [
    ("oxford", "formal"), ("brogue", "formal"), ("brogues", "formal"),
    ("stiletto", "party"), ("pump", "formal"), ("pumps", "formal"),
    ("sneaker", "casual"), ("sneakers", "casual"),
    ("sandal", "casual"), ("chappal", "traditional"),
    ("kolhapuri", "traditional"), ("jutti", "traditional"),
    ("juttis", "traditional"), ("mojari", "traditional"),
    ("mojaris", "traditional"), ("slip-on", "casual"),
    ("espadrille", "casual"), ("boot", "casual"), ("boots", "casual"),
    ("blazer", "formal"), ("coat", "formal"),
    ("nehru", "traditional"), ("shawl", "traditional"),
    ("puffer", "casual"), ("bomber", "casual"), ("denim jacket", "casual"),
    ("hoodie", "casual"), ("cardigan", "casual"),
    ("watch", "any"), ("belt", "any"), ("sunglasses", "casual"),
    ("cap", "casual"), ("hat", "casual"),
    ("jhumka", "traditional"), ("jhumkas", "traditional"),
    ("kundan", "traditional"), ("potli", "traditional"),
    ("clutch", "party"), ("brooch", "formal"),
]

# Formality inference from item names.
_NAME_FORMALITY_HINTS: list[tuple[str, str]] = [
    ("oxford", "formal"), ("brogue", "formal"), ("stiletto", "formal"),
    ("patent", "formal"), ("derby", "formal"),
    ("loafer", "smart"), ("monk strap", "smart"),
    ("heel", "smart"), ("heels", "smart"),
    ("sneaker", "casual"), ("sneakers", "casual"),
    ("sandal", "casual"), ("slip-on", "casual"),
    ("espadrille", "casual"), ("canvas", "casual"),
    ("boot", "smart"), ("boots", "smart"),
    ("blazer", "formal"), ("coat", "formal"),
    ("hoodie", "casual"), ("cardigan", "smart"),
    ("puffer", "casual"), ("bomber", "casual"),
    ("nehru", "smart"), ("kurta", "smart"),
]

# Color extraction from item names.
_NAME_COLOR_HINTS: list[tuple[str, str]] = [
    ("black", "black"), ("white", "white"), ("brown", "brown"),
    ("tan", "tan"), ("beige", "beige"), ("navy", "navy"),
    ("grey", "grey"), ("gray", "grey"), ("red", "red"),
    ("blue", "blue"), ("green", "green"), ("olive", "olive"),
    ("cream", "cream"), ("gold", "gold"), ("silver", "silver"),
    ("burgundy", "burgundy"), ("maroon", "maroon"),
    ("pink", "pink"), ("ivory", "ivory"),
]


def _formality_bucket(formality_str: str | None, formality_score: int | None) -> str:
    """Map formality to 'low' / 'medium' / 'high' bucket."""
    if formality_score is not None:
        if formality_score <= 2:
            return "low"
        if formality_score <= 3:
            return "medium"
        return "high"
    low_words = {"casual", "streetwear", "loungewear", "athleisure"}
    high_words = {"formal", "black tie", "business", "cocktail"}
    if formality_str:
        fl = formality_str.lower().strip()
        if fl in low_words:
            return "low"
        if fl in high_words:
            return "high"
    return "medium"


def _infer_season_from_name(name: str) -> str | None:
    """Infer a plausible season for a suggestion from its name."""
    nl = name.lower()
    for hint, season in _NAME_SEASON_HINTS:
        if hint in nl:
            return season
    return "all-season"


def _infer_occasion_from_name(name: str, target_category: str) -> str | None:
    """Infer a plausible occasion for a suggestion from its name."""
    nl = name.lower()
    for hint, occasion in _NAME_OCCASION_HINTS:
        if hint in nl:
            return occasion
    return "casual"


def _infer_formality_from_name(name: str) -> str | None:
    """Infer a plausible formality level for a suggestion from its name."""
    nl = name.lower()
    for hint, formality in _NAME_FORMALITY_HINTS:
        if hint in nl:
            return formality
    return "casual"


def _formality_compat_score(a: str | None, b: str | None) -> float:
    """Score formality compatibility between selected and candidate."""
    if not a or not b:
        return 0.5
    al = a.lower().strip()
    bl = b.lower().strip()
    _FORM_MAP = {"casual": 0, "smart": 1, "formal": 2}
    _FORM_RANGE = {"casual": 0, "streetwear": 0, "loungewear": 0,
                   "smart": 1, "business": 1, "cocktail": 1,
                   "formal": 2, "black tie": 2}
    a_val = _FORM_RANGE.get(al, _FORM_MAP.get(al, 1))
    b_val = _FORM_RANGE.get(bl, _FORM_MAP.get(bl, 1))
    diff = abs(a_val - b_val)
    if diff == 0:
        return 0.9
    if diff == 1:
        return 0.65
    return 0.35


def _color_for_suggestion(name: str, fallback_color: str | None) -> str | None:
    """Extract or infer a color from a suggestion name."""
    nl = name.lower()
    for hint, color in _NAME_COLOR_HINTS:
        if hint in nl:
            return color
    return fallback_color


@dataclass
class StyleMatchItem:
    name: str
    match_percentage: int
    reason: str
    owned: bool = False
    item_id: int | None = None
    category: str | None = None
    color: str | None = None
    image_url: str | None = None


@dataclass
class ShoppingLink:
    store: str
    url: str


@dataclass
class StyleMatchResult:
    selected_item: dict
    matching_bottoms: list[StyleMatchItem] = field(default_factory=list)
    matching_tops: list[StyleMatchItem] = field(default_factory=list)
    matching_footwear: list[StyleMatchItem] = field(default_factory=list)
    matching_accessories: list[StyleMatchItem] = field(default_factory=list)
    layering_suggestions: list[StyleMatchItem] = field(default_factory=list)
    recommended_colors: list[str] = field(default_factory=list)
    avoid_colors: list[str] = field(default_factory=list)
    occasion_outfits: list[dict] = field(default_factory=list)
    shopping_suggestions: list[dict] = field(default_factory=list)
    already_owned: list[StyleMatchItem] = field(default_factory=list)
    wardrobe_matches: list[StyleMatchItem] = field(default_factory=list)


# ── Color theory helpers ──

def _complementary(h: float) -> float:
    return (h + 180) % 360


def _analogous(h: float) -> list[float]:
    return [((h - 30) % 360), ((h + 30) % 360)]


def _triadic(h: float) -> list[float]:
    return [((h + 120) % 360), ((h + 240) % 360)]


def _nearest_named_color(hsl: tuple[float, float, float]) -> str | None:
    h, s, l = hsl
    best: str | None = None
    best_d = float("inf")
    for name, (hh, ss, ll) in HSL_MAP.items():
        dh = _hue_diff(h, hh) / 180.0
        ds = abs(s - ss) / 100.0
        dl = abs(l - ll) / 100.0
        d = dh * 0.5 + ds * 0.25 + dl * 0.25
        if d < best_d:
            best_d = d
            best = name
    return best


def _hsl_for_color(color: str | None):
    return _color_to_hsl(color)


def _color_compat_score(color_a: str | None, color_b: str | None) -> tuple[float, str]:
    """Return (score 0-1, reason) for pairing two colors."""
    ha = _hsl_for_color(color_a)
    hb = _hsl_for_color(color_b)
    if ha is None or hb is None:
        return 0.5, "Color compatibility unknown — neutral base."

    na = _normalise(color_a)
    nb = _normalise(color_b)
    # Same/very close color → monochromatic.
    if na == nb or _hue_diff(ha[0], hb[0]) <= 15:
        return 0.92, f"Monochromatic {na} palette — clean and cohesive."

    # One (or both) neutral → safe anchor.
    if _is_neutral_hsl(ha, color_a) or _is_neutral_hsl(hb, color_b):
        return 0.88, f"{na or 'neutral'} anchors {nb or 'neutral'} effortlessly."

    diff = _hue_diff(ha[0], hb[0])
    # Fashion-specific clash overrides theory.
    if frozenset({na, nb}) in _FASHION_CLASHES:
        return 0.25, f"{na} and {nb} clash in practice — avoid this combo."

    if 150 <= diff <= 210:
        return 0.85, f"Complementary colors ({na} + {nb}) create contrast."
    if diff <= 40:
        return 0.80, f"Analogous colors ({na} + {nb}) sit well together."
    if 100 <= diff <= 140:
        return 0.78, f"Triadic colors ({na} + {nb}) add playful balance."
    return 0.55, f"{na} and {nb} are wearable but not a standout pairing."


# ── Attribute compatibility ──

def _season_score(season_a: str | None, season_b: str | None) -> float:
    sa = _normalise(season_a)
    sb = _normalise(season_b)
    if not sa or not sb:
        return 0.5
    if sa == sb:
        return 0.9
    if "all-season" in (sa, sb):
        return 0.85
    return 0.3


def _occasion_score(oa: str | None, ob: str | None) -> float:
    if not oa or not ob:
        return 0.5
    a_tags = [t.strip() for t in oa.split(",")]
    b_tags = [t.strip() for t in ob.split(",")]
    if any(t in b_tags for t in a_tags):
        return 0.9
    return 0.45


def _fit_score(fa: str | None, fb: str | None) -> float:
    a = _normalise(fa)
    b = _normalise(fb)
    if not a or not b:
        return 0.5
    if a == b:
        return 0.7
    if {a, b} == {"slim", "oversized"} or {a, b} == {"loose", "slim"}:
        return 0.9
    if {a, b} == {"oversized", "loose"}:
        return 0.3
    return 0.6


def _gender_ok(a: str | None, b: str | None) -> bool:
    g1 = _normalise(a) or "unisex"
    g2 = _normalise(b) or "unisex"
    return g1 == "unisex" or g2 == "unisex" or g1 == g2


# ── Core item-to-item compatibility ──

def _compatibility(selected: ClothingItem, other: ClothingItem) -> tuple[int, str]:
    """Return (score 0-100, reason) for pairing two wardrobe items."""
    parts: list[str] = []
    scores: list[float] = []

    col_s, col_r = _color_compat_score(selected.color, other.color)
    scores.append(col_s)
    parts.append(col_r)

    sc_s = _season_score(selected.season, other.season)
    scores.append(sc_s * 0.8 + 0.2 * 0.5)
    if sc_s >= 0.85:
        parts.append("same season")

    oc_s = _occasion_score(selected.occasion_tag, other.occasion_tag)
    scores.append(oc_s)
    if oc_s >= 0.9:
        parts.append(f"both {_primary_occasion(selected.occasion_tag) or 'casual'} wear")

    ft_s = _fit_score(selected.fit_type, other.fit_type)
    scores.append(ft_s)
    if ft_s >= 0.85:
        parts.append("balanced fit")

    if not _gender_ok(selected.target_gender, other.target_gender):
        return 20, "Different target gender — likely a mismatch."

    base = sum(scores) / len(scores)
    # Slight boost when the other item is a natural category partner.
    partner_cats = _MATCHING_CATEGORIES.get(_normalise(selected.category), [])
    if _normalise(other.category) in partner_cats:
        base = min(1.0, base + 0.05)

    score = int(round(base * 100))
    reason = "; ".join(parts[:3]) if parts else "Versatile pairing."
    return score, reason


# ── Generated (non-owned) suggestions ──

def _generated_suggestions(
    selected: ClothingItem, target_category: str, owned_ids: set[int], count: int = 5
) -> list[StyleMatchItem]:
    """Build concrete, named suggestions for a category with reasons + scores.

    Uses the selected item's attributes (color, occasion, season, formality,
    gender) to generate plausible, fashion-correct items. Each suggestion is
    scored individually against the selected item's attributes. These are NOT
    wardrobe items — they are purchase suggestions, so owned=False.
    """
    sel_hsl = _hsl_for_color(selected.color)
    sel_occ = _primary_occasion(selected.occasion_tag) or "casual"
    sel_season = selected.season
    sel_formality = selected.formality
    sel_formality_score = selected.formality_score

    # Pick a complementary/neutral color to recommend for the new item.
    if sel_hsl is not None and not _is_neutral_hsl(sel_hsl, selected.color):
        rec_color = _nearest_named_color((_complementary(sel_hsl[0]), 45.0, 55.0))
    else:
        rec_color = "navy" if _normalise(selected.color) in ("white", "beige", "cream", "ivory") else "beige"

    # Get suggestion names from the attribute-driven tables.
    names = _suggested_names(selected, target_category, rec_color)
    items: list[StyleMatchItem] = []
    for name in names[:count]:
        # Extract color from the suggestion name (e.g. "Black Loafers" → "black").
        cand_color = _color_for_suggestion(name, rec_color)

        # Score color compatibility between selected item and this specific suggestion.
        col_s, col_r = _color_compat_score(selected.color, cand_color)

        # Fix: compare selected season against the CANDIDATE's inferred season (not itself).
        cand_season = _infer_season_from_name(name)
        season_s = _season_score(sel_season, cand_season)

        # Fix: compare selected occasion against the CANDIDATE's inferred occasion.
        cand_occ = _infer_occasion_from_name(name, target_category)
        occ_s = _occasion_score(sel_occ, cand_occ)

        # New: formality compatibility.
        cand_formality = _infer_formality_from_name(name)
        form_s = _formality_compat_score(sel_formality, cand_formality)

        # Weighted blend: color (40%), occasion (20%), season (15%), formality (15%), base (10%).
        score = int(round((
            col_s * 0.40 +
            occ_s * 0.20 +
            season_s * 0.15 +
            form_s * 0.15 +
            0.10  # base for being a curated suggestion
        ) * 100))

        reason = f"{col_r} Pairs with your {selected.name or selected.category}."
        items.append(
            StyleMatchItem(
                name=name,
                match_percentage=max(55, min(96, score)),
                reason=reason,
                owned=False,
                category=target_category,
                color=cand_color,
            )
        )
    return items


def _suggested_names(selected: ClothingItem, target: str, rec_color: str) -> list[str]:
    """Return suggestion names driven by the selected item's attributes.

    Uses occasion, formality, season, and target_gender to pick from the
    suggestion tables, falling back to defaults when no match is found.
    """
    occ = _primary_occasion(selected.occasion_tag) or "casual"
    fb = _formality_bucket(selected.formality, selected.formality_score)
    gender = (selected.target_gender or "unisex").lower()

    table = _SUGGESTION_TABLES.get(target, {})
    candidates = table.get((occ, fb)) or table.get((occ, "any")) or _DEFAULT_SUGGESTIONS.get(target, [])

    # Filter by gender compatibility.
    filtered = [
        c for c in candidates
        if c["gender"] in ("unisex", gender) or gender == "unisex"
    ]

    # If gender filter removed everything, fall back to unisex-only.
    if not filtered:
        filtered = [c for c in candidates if c["gender"] == "unisex"]
    if not filtered:
        filtered = candidates

    return [c["name"] for c in filtered]


# ── Color recommendations / avoid ──

def _recommend_avoid_colors(selected: ClothingItem) -> tuple[list[str], list[str]]:
    hsl = _hsl_for_color(selected.color)
    if hsl is None:
        return ["beige", "navy blue", "black", "olive green", "grey"], ["neon green", "bright orange"]

    rec: list[str] = []
    if _is_neutral_hsl(hsl, selected.color):
        # Neutrals pair with everything — recommend timeless neutrals.
        rec = ["navy blue", "black", "beige", "olive green", "grey", "brown"]
    else:
        comp = _nearest_named_color((_complementary(hsl[0]), 45, 55))
        analog = [_nearest_named_color((h, 45, 55)) for h in _analogous(hsl[0])]
        tri = [_nearest_named_color((h, 45, 55)) for h in _triadic(hsl[0])]
        for c in [comp] + analog + tri:
            if c and c not in rec:
                rec.append(c)
        for n in ["beige", "navy blue", "black", "grey", "olive green"]:
            if n not in rec:
                rec.append(n)
        rec = rec[:6]

    # Avoid: clashing fashion pairs + own hue's weak neighbors.
    clashes: list[str] = []
    na = _normalise(selected.color)
    for pair in _FASHION_CLASHES:
        if na in pair:
            other = (pair - {na}).pop()
            clashes.append(other)
    avoid = clashes + ["neon green", "bright orange"]
    # de-dup preserving order
    seen = set()
    avoid = [c for c in avoid if not (c in seen or seen.add(c))]
    return rec, avoid[:5]


def _occasion_ideas(selected: ClothingItem) -> list[dict]:
    sel_occ = _primary_occasion(selected.occasion_tag) or "casual"
    mapping = {
        "casual": ["Office Casual", "Streetwear", "Weekend Casual"],
        "office": ["Office Casual", "Business Formal", "Travel"],
        "formal": ["Business Formal", "Wedding Guest", "Date Night"],
        "party": ["Date Night", "Festive", "Party Glam"],
        "wedding": ["Wedding Guest", "Festive", "Date Night"],
        "college": ["College Day", "Streetwear", "Casual Hangout"],
        "date": ["Date Night", "Dinner Out", "Smart Casual"],
        "travel": ["Travel", "Weekend Casual", "Airport Look"],
        "traditional": ["Traditional", "Festive", "Wedding Guest"],
        "festive": ["Festive", "Party", "Traditional"],
        "streetwear": ["Streetwear", "College Day", "Weekend Casual"],
    }
    ideas = mapping.get(sel_occ, ["Casual", "Office Casual", "Weekend Casual"])
    return [
        {"name": idea, "based_on": selected.name or selected.category}
        for idea in ideas
    ]


def _build_shop_links(query: str) -> list[dict]:
    q = quote_plus(_normalise(query) or query)
    dash = _normalise(query).replace(" ", "-")
    links = [
        {"store": "meesho", "url": f"{_SHOP_BUILDERS['meesho']}{q}"},
        {"store": "myntra", "url": f"{_SHOP_BUILDERS['myntra']}{dash}"},
        {"store": "ajio", "url": f"{_SHOP_BUILDERS['ajio']}{dash}"},
        {"store": "amazon", "url": f"{_SHOP_BUILDERS['amazon']}{q}"},
        {"store": "flipkart", "url": f"{_SHOP_BUILDERS['flipkart']}{q}"},
    ]
    return links


# ── Main entry ──

def generate_style_match(item_id: int, db: Session) -> StyleMatchResult:
    selected = db.query(ClothingItem).filter(ClothingItem.id == item_id).first()
    if not selected:
        raise ValueError(f"Item {item_id} not found")

    user_id = selected.user_id
    all_items = (
        db.query(ClothingItem).filter(ClothingItem.user_id == user_id).all()
    )
    owned_ids = {it.id for it in all_items}

    partner_cats = _MATCHING_CATEGORIES.get(_normalise(selected.category), [])

    section_map: dict[str, list[StyleMatchItem]] = {
        "top": [], "bottom": [], "footwear": [], "accessory": [], "outerwear": [],
    }

    # 1) Wardrobe matches (owned items in partner categories), scored.
    wardrobe_matches: list[StyleMatchItem] = []
    for it in all_items:
        if it.id == selected.id:
            continue
        if _normalise(it.category) not in partner_cats:
            continue
        score, reason = _compatibility(selected, it)
        wardrobe_matches.append(
            StyleMatchItem(
                name=it.name or f"{it.category}",
                match_percentage=score,
                reason=reason,
                owned=True,
                item_id=it.id,
                category=it.category,
                color=it.color,
                image_url=it.image_url,
            )
        )
    wardrobe_matches.sort(key=lambda x: x.match_percentage, reverse=True)

    # 2) Generated suggestions per partner category (not owned).
    for cat in partner_cats:
        generated = _generated_suggestions(selected, cat, owned_ids)
        section_map[cat].extend(generated)

    # 3) Split into the response buckets.
    result = StyleMatchResult(
        selected_item={
            "id": selected.id,
            "name": selected.name,
            "category": selected.category,
            "color": selected.color,
            "pattern": selected.pattern,
            "fabric_type": selected.fabric_type,
            "sleeve_length": selected.sleeve_length,
            "occasion_tag": selected.occasion_tag,
            "season": selected.season,
            "target_gender": selected.target_gender,
            "image_url": selected.image_url,
        },
        matching_bottoms=section_map.get("bottom", []),
        matching_tops=section_map.get("top", []),
        matching_footwear=section_map.get("footwear", []),
        matching_accessories=section_map.get("accessory", []),
        layering_suggestions=section_map.get("outerwear", []),
        already_owned=wardrobe_matches,
        wardrobe_matches=wardrobe_matches,
    )

    rec, avoid = _recommend_avoid_colors(selected)
    result.recommended_colors = rec
    result.avoid_colors = avoid
    result.occasion_outfits = _occasion_ideas(selected)

    # 4) Shopping suggestions: one group per partner category's top pick.
    for cat in partner_cats:
        picks = section_map.get(cat, [])
        if not picks:
            continue
        top = picks[0]
        links = _build_shop_links(top.name)
        links.append({"store": "Google Shopping", "url": build_google_shopping_link(top.name)})
        links.append({"store": "Meesho", "url": build_meesho_search_link(top.name)})
        result.shopping_suggestions.append(
            {
                "category": cat,
                "item_name": top.name,
                "match_percentage": top.match_percentage,
                "reason": top.reason,
                "owned": False,
                "shopping_links": links,
            }
        )

    return result


def style_match_to_dict(result: StyleMatchResult) -> dict:
    """Serialise to the structured JSON contract."""

    def _item(d: StyleMatchItem) -> dict:
        return {
            "name": d.name,
            "match_percentage": d.match_percentage,
            "reason": d.reason,
            "owned": d.owned,
            "item_id": d.item_id,
            "category": d.category,
            "color": d.color,
            "image_url": d.image_url,
        }

    return {
        "selectedItem": result.selected_item,
        "matchingBottoms": [_item(d) for d in result.matching_bottoms],
        "matchingTops": [_item(d) for d in result.matching_tops],
        "matchingFootwear": [_item(d) for d in result.matching_footwear],
        "matchingAccessories": [_item(d) for d in result.matching_accessories],
        "layeringSuggestions": [_item(d) for d in result.layering_suggestions],
        "recommendedColors": result.recommended_colors,
        "avoidColors": result.avoid_colors,
        "occasionOutfits": result.occasion_outfits,
        "shoppingSuggestions": result.shopping_suggestions,
        "alreadyOwned": [_item(d) for d in result.already_owned],
    }


def build_item_match_queries(item_id: int, db: Session) -> list[dict]:
    """Build search queries for each category that matches the given item.

    Returns ``[{label: "bottom", query: "Black Trousers"}, ...]``.
    """
    selected = db.query(ClothingItem).filter(ClothingItem.id == item_id).first()
    if not selected:
        return []

    partner_cats = _MATCHING_CATEGORIES.get(_normalise(selected.category), [])
    queries: list[dict] = []

    for cat in partner_cats:
        names = _generated_suggestions(selected, cat, set())
        query = names[0].name if names else cat.capitalize()
        queries.append({"label": cat, "query": query})

    return queries
