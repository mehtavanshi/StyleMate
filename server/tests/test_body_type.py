import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app


@pytest.fixture()
def client():
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
        json={"name": "Test User", "email": "bodytype-test@example.com"},
    )
    assert res.status_code == 201
    return res.json()["id"]


class TestSetBodyType:
    def test_valid_value_sets_body_type(self, client, user_id):
        res = client.post(f"/users/{user_id}/body-type", json={"body_type": "pear"})
        assert res.status_code == 200
        body = res.json()
        assert body["body_type"] == "pear"

        get = client.get(f"/users/{user_id}")
        assert get.json()["body_type"] == "pear"

    def test_invalid_value_returns_422(self, client, user_id):
        res = client.post(f"/users/{user_id}/body-type", json={"body_type": "triangle"})
        assert res.status_code == 422

    def test_unknown_user_returns_404(self, client):
        res = client.post("/users/999999/body-type", json={"body_type": "apple"})
        assert res.status_code == 404
