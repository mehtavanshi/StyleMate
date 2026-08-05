"""The image embedding is cached per URL — tagging one item asks ~20 questions
about the same photo and must not re-run the CLIP image encoder each time."""

from unittest.mock import MagicMock, patch

import numpy as np

from app.style_embeddings import _cached_embedding, get_embedding


def _fake_model():
    model = MagicMock()
    model.device = "cpu"
    import torch

    model.get_image_features.return_value = torch.tensor([[3.0, 4.0]])
    processor = MagicMock(return_value={"pixel_values": torch.zeros(1, 3, 2, 2)})
    return model, processor


def test_same_url_encodes_once():
    _cached_embedding.cache_clear()
    with patch("app.style_embeddings._resolve_image") as resolve, patch(
        "app.style_embeddings._get_model", side_effect=lambda: _fake_model()
    ) as get_model:
        resolve.return_value = MagicMock()

        first = get_embedding("/uploads/a.jpg")
        second = get_embedding("/uploads/a.jpg")
        get_embedding("/uploads/b.jpg")

        assert first == second
        assert isinstance(first, list)
        assert np.isclose(np.linalg.norm(first), 1.0)
        # a.jpg encoded once (second call cached), b.jpg once more.
        assert get_model.call_count == 2


def test_returned_list_is_not_shared_state():
    _cached_embedding.cache_clear()
    with patch("app.style_embeddings._resolve_image") as resolve, patch(
        "app.style_embeddings._get_model", side_effect=lambda: _fake_model()
    ):
        resolve.return_value = MagicMock()

        first = get_embedding("/uploads/a.jpg")
        first[0] = 99.0
        assert get_embedding("/uploads/a.jpg")[0] != 99.0
