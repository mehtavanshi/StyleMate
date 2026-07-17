#!/usr/bin/env python3
"""Sanity-check script for the pairing engine.

Runs a set of known-good and known-bad outfit pairs through score_pair(),
verifies the engine ranks good pairs above bad ones, and reports any
inversions that might indicate weight tuning is needed.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.pairing_engine import score_pair, COLOR_WEIGHT, EMBEDDING_WEIGHT, HARD_RULE_WEIGHT


class Item:
    """Lightweight stand-in for ClothingItem (no DB needed)."""

    def __init__(
        self,
        name,
        category,
        color,
        pattern="solid",
        occasion_tag=None,
        formality=None,
        target_gender="unisex",
        embedding_json=None,
    ):
        self.id = 0
        self.category = category
        self.color = color
        self.pattern = pattern
        self.name = name
        self.image_url = None
        self.occasion_tag = occasion_tag
        self.formality = formality
        self.target_gender = target_gender
        self.embedding_json = embedding_json


# ── Known-good pairs (should score well) ──

GOOD_PAIRS = [
    ("White Oxford + Navy Trousers",
     Item("White Oxford Shirt", "top", "white", occasion_tag="formal", formality="business"),
     Item("Navy Chinos", "bottom", "navy", occasion_tag="formal", formality="business")),

    ("Black Tee + Blue Jeans",
     Item("Black Tee", "top", "black", occasion_tag="casual"),
     Item("Blue Jeans", "bottom", "blue", occasion_tag="casual")),

    ("Burgundy Dress + Beige Shoes",
     Item("Burgundy Dress", "dress", "burgundy", occasion_tag="party"),
     Item("Beige Heels", "footwear", "beige", occasion_tag="party")),

    ("Grey Hoodie + Black Joggers",
     Item("Grey Hoodie", "top", "grey", occasion_tag="casual"),
     Item("Black Joggers", "bottom", "black", occasion_tag="casual")),

    ("Navy Blazer + White Shirt",
     Item("Navy Blazer", "outerwear", "navy", occasion_tag="formal", formality="business"),
     Item("White Shirt", "top", "white", occasion_tag="formal", formality="business")),

    ("Cream Sweater + Olive Trousers",
     Item("Cream Sweater", "top", "cream", occasion_tag="casual"),
     Item("Olive Trousers", "bottom", "olive", occasion_tag="casual")),

    ("Teal Top + Khaki Pants",
     Item("Teal Top", "top", "teal", occasion_tag="casual"),
     Item("Khaki Pants", "bottom", "khaki", occasion_tag="casual")),

    ("Pink Blouse + Navy Skirt",
     Item("Pink Blouse", "top", "pink", occasion_tag="office"),
     Item("Navy Skirt", "bottom", "navy", occasion_tag="office")),

    ("Brown Boots + Tan Jacket",
     Item("Tan Jacket", "outerwear", "tan", occasion_tag="casual"),
     Item("Brown Boots", "footwear", "brown", occasion_tag="casual")),

    ("Black Dress + Red Heels",
     Item("Black Dress", "dress", "black", occasion_tag="party"),
     Item("Red Heels", "footwear", "red", occasion_tag="party")),
]

# ── Known-bad pairs (should score poorly) ──

BAD_PAIRS = [
    ("Orange Top + Red-Pink Bottom",
     Item("Orange Top", "top", "orange", occasion_tag="casual"),
     Item("Hot Pink Bottom", "bottom", "hot pink", occasion_tag="casual")),

    ("Lime Shirt + Purple Trousers",
     Item("Lime Shirt", "top", "lime", occasion_tag="casual"),
     Item("Purple Trousers", "bottom", "purple", occasion_tag="casual")),

    ("Yellow Blazer + Violet Pants",
     Item("Yellow Blazer", "outerwear", "yellow", occasion_tag="office"),
     Item("Violet Pants", "bottom", "violet", occasion_tag="office")),

    ("Red Top + Green Bottom",
     Item("Red Top", "top", "red", occasion_tag="casual"),
     Item("Green Bottom", "bottom", "green", occasion_tag="casual")),

    ("Coral Shirt + Brown Trousers",
     Item("Coral Shirt", "top", "coral", occasion_tag="casual"),
     Item("Brown Trousers", "bottom", "brown", occasion_tag="casual")),

    ("Fuchsia Dress + Rust Shoes",
     Item("Fuchsia Dress", "dress", "fuchsia", occasion_tag="party"),
     Item("Rust Shoes", "footwear", "rust", occasion_tag="party")),

    ("Maroon Top + Teal Bottom",
     Item("Maroon Top", "top", "maroon", occasion_tag="casual"),
     Item("Teal Bottom", "bottom", "teal", occasion_tag="casual")),

    ("Lavender Shirt + Mustard Pants",
     Item("Lavender Shirt", "top", "lavender", occasion_tag="casual"),
     Item("Mustard Pants", "bottom", "mustard", occasion_tag="casual")),

    ("Formal Shirt + Casual Shorts (mismatch)",
     Item("Formal Shirt", "top", "white", occasion_tag="formal", formality="business"),
     Item("Casual Shorts", "bottom", "khaki", occasion_tag="casual", formality="casual")),

    ("Men's Blazer + Women's Skirt (gender clash)",
     Item("Men's Blazer", "outerwear", "navy", target_gender="men"),
     Item("Women's Skirt", "bottom", "pink", target_gender="women")),
]


def run_eval():
    print("=" * 65)
    print("PAIRING ENGINE SANITY CHECK")
    print("=" * 65)
    print(f"Weights: COLOR={COLOR_WEIGHT}  EMBEDDING={EMBEDDING_WEIGHT}  HARD_RULE={HARD_RULE_WEIGHT}")
    print()

    good_scores = []
    bad_scores = []

    print("--- KNOWN-GOOD PAIRS ---")
    for label, a, b in GOOD_PAIRS:
        score, reason = score_pair(a, b)
        good_scores.append((label, score))
        status = "OK" if score >= 0.45 else "LOW"
        print(f"  [{status}] {score:.3f}  {label}")
        if reason != "mixed compatibility":
            print(f"         reason: {reason}")

    print()
    print("--- KNOWN-BAD PAIRS ---")
    for label, a, b in BAD_PAIRS:
        score, reason = score_pair(a, b)
        bad_scores.append((label, score))
        status = "OK" if score <= 0.55 else "HIGH"
        print(f"  [{status}] {score:.3f}  {label}")
        if reason != "mixed compatibility":
            print(f"         reason: {reason}")

    # Summary
    avg_good = sum(s for _, s in good_scores) / len(good_scores) if good_scores else 0
    avg_bad = sum(s for _, s in bad_scores) / len(bad_scores) if bad_scores else 0
    min_good = min(s for _, s in good_scores) if good_scores else 0
    max_bad = max(s for _, s in bad_scores) if bad_scores else 0

    print()
    print("=" * 65)
    print("SUMMARY")
    print("=" * 65)
    print(f"  Good pairs:  avg={avg_good:.3f}  min={min_good:.3f}  (n={len(good_scores)})")
    print(f"  Bad pairs:   avg={avg_bad:.3f}  max={max_bad:.3f}  (n={len(bad_scores)})")
    print()

    inversions = []
    for g_label, g_score in good_scores:
        for b_label, b_score in bad_scores:
            if g_score < b_score:
                inversions.append((g_label, g_score, b_label, b_score))

    if inversions:
        print(f"  INVERSIONS: {len(inversions)} good pair(s) scored below a bad pair:")
        for g_label, g_score, b_label, b_score in inversions:
            print(f"    {g_label} ({g_score:.3f}) < {b_label} ({b_score:.3f})")
    else:
        print("  No inversions — all good pairs scored above all bad pairs.")

    print()
    if min_good > max_bad:
        print("  PASS: scoring correctly separates good from bad.")
    elif avg_good > avg_bad:
        print("  PARTIAL: average ranking is correct, but some overlap exists.")
        print("  Consider tweaking weights to increase separation.")
    else:
        print("  FAIL: good pairs are not consistently ranked above bad pairs.")
        print("  Review weights and color/embedding scoring logic.")

    print()
    return 0 if min_good > max_bad else 1


if __name__ == "__main__":
    sys.exit(run_eval())
