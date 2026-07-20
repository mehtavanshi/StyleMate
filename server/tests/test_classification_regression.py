"""Integration test: real classification must produce different results for different images.

Uses the real FashionCLIP model (already cached, ~500MB).  This catches
the "same default for everyone" bug class — if this test ever passes
with identical outputs for different images, something is broken again.
"""

from pathlib import Path

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def _fixture_path(name: str) -> str:
    return str(FIXTURES_DIR / name)


def test_classification_produces_different_results():
    from app.routers.tagging import _tag_item_fashion_clip

    result_a = _tag_item_fashion_clip(_fixture_path("floral-dress.jpg"))
    result_b = _tag_item_fashion_clip(_fixture_path("leather-jacket.jpg"))

    keys = ["category", "dominant_color", "target_gender"]
    differing = sum(1 for k in keys if result_a.get(k) != result_b.get(k))
    assert differing >= 2, (
        f"Results too similar ({differing}/3 fields differ):\n"
        f"  A={ {k: result_a.get(k) for k in keys} }\n"
        f"  B={ {k: result_b.get(k) for k in keys} }"
    )


def test_classification_returns_no_none_fields():
    from app.routers.tagging import _tag_item_fashion_clip

    result = _tag_item_fashion_clip(_fixture_path("floral-dress.jpg"))

    expected_fields = [
        "category", "dominant_color", "pattern", "occasion_tag",
        "season", "fabric_type", "fit_type", "sleeve_length",
        "target_gender", "formality_score", "style_tags",
    ]
    for field in expected_fields:
        assert result.get(field) is not None, (
            f"Field '{field}' is None — classifier returned no prediction"
        )
