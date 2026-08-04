"""Tests for the garment-detection gate in the tagging pipeline.

Verifies that non-clothing images are rejected with a structured 422 error
and that normal clothing photos still pass through and tag correctly.
"""

import json
from pathlib import Path

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def _fixture_path(name: str) -> str:
    return str(FIXTURES_DIR / name)


def test_garment_detection_rejects_black_image():
    from app.routers.tagging import _tag_item_fashion_clip
    from fastapi import HTTPException

    try:
        _tag_item_fashion_clip(_fixture_path("black-image.png"))
        assert False, "Expected HTTPException for black image"
    except HTTPException as exc:
        assert exc.status_code == 422
        detail = exc.detail if isinstance(exc.detail, dict) else json.loads(exc.detail)
        assert detail["error"] == "no_garment_detected"


def test_garment_detection_rejects_solid_color_image():
    from app.routers.tagging import _tag_item_fashion_clip
    from fastapi import HTTPException

    try:
        _tag_item_fashion_clip(_fixture_path("solid-color.png"))
        assert False, "Expected HTTPException for solid-color image"
    except HTTPException as exc:
        assert exc.status_code == 422
        detail = exc.detail if isinstance(exc.detail, dict) else json.loads(exc.detail)
        assert detail["error"] == "no_garment_detected"


def test_garment_detection_rejects_wall_image():
    from app.routers.tagging import _tag_item_fashion_clip
    from fastapi import HTTPException

    try:
        _tag_item_fashion_clip(_fixture_path("wall.jpg"))
        assert False, "Expected HTTPException for wall image"
    except HTTPException as exc:
        assert exc.status_code == 422
        detail = exc.detail if isinstance(exc.detail, dict) else json.loads(exc.detail)
        assert detail["error"] == "no_garment_detected"


def test_garment_detection_rejects_face_image():
    from app.routers.tagging import _tag_item_fashion_clip
    from fastapi import HTTPException

    try:
        _tag_item_fashion_clip(_fixture_path("face.jpg"))
        assert False, "Expected HTTPException for face image"
    except HTTPException as exc:
        assert exc.status_code == 422
        detail = exc.detail if isinstance(exc.detail, dict) else json.loads(exc.detail)
        assert detail["error"] == "no_garment_detected"


def test_clothing_image_passes_garment_detection():
    from app.routers.tagging import _tag_item_fashion_clip

    result = _tag_item_fashion_clip(_fixture_path("floral-dress.jpg"))
    assert result.get("category") is not None
    assert result.get("dominant_color") is not None
    assert "_confidence" in result
    assert "_needs_review" in result