"""Tests for style_embeddings module.

The FashionCLIP model is mocked in all tests to avoid downloading
the ~500MB model during CI/test runs.
"""

import json
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from app.style_embeddings import (
    _embedding_cache,
    cosine_similarity,
    get_embedding,
)


class TestCosineSimilarity:
    def test_identical_vectors(self):
        v = [1.0, 0.0, 0.0]
        assert cosine_similarity(v, v) == pytest.approx(1.0)

    def test_orthogonal_vectors(self):
        a = [1.0, 0.0, 0.0]
        b = [0.0, 1.0, 0.0]
        assert cosine_similarity(a, b) == pytest.approx(0.0)

    def test_opposite_vectors(self):
        a = [1.0, 0.0, 0.0]
        b = [-1.0, 0.0, 0.0]
        assert cosine_similarity(a, b) == pytest.approx(-1.0)

    def test_zero_vector_returns_zero(self):
        a = [0.0, 0.0, 0.0]
        b = [1.0, 0.0, 0.0]
        assert cosine_similarity(a, b) == 0.0

    def test_realistic_embedding(self):
        np.random.seed(42)
        a = np.random.randn(512).tolist()
        b = a.copy()
        b[0] += 0.01
        score = cosine_similarity(a, b)
        assert 0.99 < score <= 1.0


class TestGetEmbedding:
    def _mock_model_output(self):
        mock_output = MagicMock()
        mock_output.cpu.return_value.numpy.return_value.tolist.return_value = [0.1] * 512
        return mock_output

    @patch("app.style_embeddings._get_model")
    def test_get_embedding_returns_list(self, mock_get_model):
        import torch

        mock_model = MagicMock()
        mock_model.device = "cpu"
        mock_model.get_image_features.return_value = torch.randn(1, 512)

        mock_processor = MagicMock()
        mock_processor.return_value = {
            "pixel_values": torch.randn(1, 3, 224, 224)
        }

        mock_get_model.return_value = (mock_model, mock_processor)

        with patch("app.style_embeddings._resolve_image") as mock_resolve:
            mock_resolve.return_value = MagicMock()
            result = get_embedding("/uploads/test.jpg")

        assert isinstance(result, list)
        assert len(result) == 512

    @patch("app.style_embeddings._get_model")
    def test_get_embedding_normalizes_output(self, mock_get_model):
        import torch

        raw_vec = torch.tensor([[3.0, 4.0, 0.0]])
        mock_model = MagicMock()
        mock_model.device = "cpu"
        mock_model.get_image_features.return_value = raw_vec

        mock_processor = MagicMock()
        mock_processor.return_value = {"pixel_values": torch.randn(1, 3, 224, 224)}

        mock_get_model.return_value = (mock_model, mock_processor)

        with patch("app.style_embeddings._resolve_image") as mock_resolve:
            mock_resolve.return_value = MagicMock()
            result = get_embedding("/uploads/test.jpg")

        norm = sum(x**2 for x in result) ** 0.5
        assert norm == pytest.approx(1.0, abs=1e-5)


class TestResolveImage:
    def test_local_path_resolves(self):
        from pathlib import Path

        from app.style_embeddings import _resolve_image

        uploads = Path(__file__).resolve().parents[2] / "uploads"
        existing = next(uploads.glob("*"), None)
        if existing:
            url = f"/uploads/{existing.name}"
            img = _resolve_image(url)
            assert img.size[0] > 0


class TestEmbeddingCache:
    def setup_method(self):
        _embedding_cache.clear()

    def test_cache_prevents_recomputation(self):
        _embedding_cache[999] = [0.1, 0.2, 0.3]

        mock_db = MagicMock()
        item = MagicMock()
        item.id = 999
        item.image_url = "/uploads/test.jpg"
        item.embedding_json = None
        mock_db.query.return_value.filter.return_value.first.return_value = item

        from app.style_embeddings import compute_and_store_embedding

        compute_and_store_embedding(999, mock_db)

        mock_db.commit.assert_not_called()

    def test_stored_json_is_loadable(self):
        original = [0.1, -0.2, 0.3, 0.0]
        serialized = json.dumps(original)
        loaded = json.loads(serialized)
        assert loaded == original
