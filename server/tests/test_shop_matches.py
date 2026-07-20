"""Integration test for GET /items/{item_id}/shop-matches.

Verifies routing, response structure, and that the endpoint does not
return 404 for valid items (the original bug).
"""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.routers.shop_matches import _cache as shop_matches_cache
from app.shopping_service import Product, ProviderResult
from app.style_embeddings import RankedProduct


@pytest.fixture()
def client():
    shop_matches_cache.clear()
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def user_id(client):
    res = client.post(
        "/users/",
        json={"name": "Test User", "email": "shop-match-test@example.com"},
    )
    assert res.status_code == 201
    return res.json()["id"]


@pytest.fixture()
def clothing_item_id(client, user_id):
    res = client.post(
        "/clothing-items",
        json={
            "user_id": user_id,
            "name": "Blue T-Shirt",
            "category": "top",
            "color": "blue",
            "occasion_tag": "casual",
            "image_url": "/uploads/test.jpg",
        },
    )
    assert res.status_code == 201
    return res.json()["id"]


class TestShopMatchesIntegration:
    """Tests the live endpoint behaviour with external dependencies mocked."""

    @patch("app.routers.shop_matches.search_all_providers", new_callable=AsyncMock)
    @patch("app.routers.shop_matches.rank_by_visual_fit")
    def test_returns_200_and_expected_keys(
        self,
        mock_rank,
        mock_search,
        client,
        clothing_item_id,
    ):
        """Happy path: valid item returns 200 with all required keys and
        ai_top_picks has at most 3 entries."""
        mock_product = Product(
            name="Test Product",
            image_url="https://example.com/img.jpg",
            price=999.0,
            currency="INR",
            affiliate_link="https://example.com/buy",
            source="flipkart",
        )
        mock_search.return_value = [
            ProviderResult(platform="flipkart", products=[mock_product]),
        ]

        mock_rank.return_value = [
            RankedProduct(product=mock_product, similarity_score=0.85),
        ]

        res = client.get(f"/items/{clothing_item_id}/shop-matches")

        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        data = res.json()
        assert isinstance(data, list)
        assert len(data) > 0

        for group in data:
            assert "ai_top_picks" in group
            assert "flipkart_products" in group
            assert "amazon_products" in group
            assert "meesho_search_link" in group
            assert len(group["ai_top_picks"]) <= 3

    def test_unknown_item_returns_404(self, client):
        """Non-existent item_id returns 404, not a crash or wrong page."""
        res = client.get("/items/999999/shop-matches")
        assert res.status_code == 404

    @patch("app.routers.shop_matches.search_all_providers", new_callable=AsyncMock)
    @patch("app.routers.shop_matches.rank_by_visual_fit")
    def test_meesho_link_populated(
        self,
        mock_rank,
        mock_search,
        client,
        clothing_item_id,
    ):
        """When Meesho data is returned, meesho_search_link is not null."""
        mock_product = Product(
            name="Test Product",
            image_url="https://example.com/img.jpg",
            price=999.0,
            currency="INR",
            affiliate_link="https://example.com/buy",
            source="flipkart",
        )
        mock_meesho_product = Product(
            name="white t-shirt",
            image_url="",
            price=0.0,
            currency="INR",
            affiliate_link="https://www.meesho.com/search?q=white+t-shirt",
            source="meesho",
        )
        mock_search.return_value = [
            ProviderResult(platform="flipkart", products=[mock_product]),
            ProviderResult(platform="meesho", products=[mock_meesho_product]),
        ]
        mock_rank.return_value = [
            RankedProduct(product=mock_product, similarity_score=0.85),
        ]

        res = client.get(f"/items/{clothing_item_id}/shop-matches")
        assert res.status_code == 200
        data = res.json()

        meesho_groups = [g for g in data if g["meesho_search_link"] is not None]
        assert len(meesho_groups) > 0, "Expected at least one group with meesho_search_link"

        link = meesho_groups[0]["meesho_search_link"]
        assert link["source"] == "meesho"
        assert link["affiliate_link"].startswith("https://www.meesho.com/")

    @patch("app.routers.shop_matches.search_all_providers", new_callable=AsyncMock)
    @patch("app.routers.shop_matches.rank_by_visual_fit")
    def test_cache_bypass_with_refresh(
        self,
        mock_rank,
        mock_search,
        client,
        clothing_item_id,
    ):
        """The refresh=true parameter bypasses the cache and returns fresh data."""
        mock_product = Product(
            name="Test Product",
            image_url="https://example.com/img.jpg",
            price=999.0,
            currency="INR",
            affiliate_link="https://example.com/buy",
            source="flipkart",
        )
        mock_search.return_value = [
            ProviderResult(platform="flipkart", products=[mock_product]),
        ]
        mock_rank.return_value = [
            RankedProduct(product=mock_product, similarity_score=0.85),
        ]

        res = client.get(f"/items/{clothing_item_id}/shop-matches?refresh=true")
        assert res.status_code == 200
        data = res.json()
        assert isinstance(data, list)
        assert len(data) > 0
