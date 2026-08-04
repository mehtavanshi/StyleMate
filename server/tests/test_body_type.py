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
def auth_headers(client):
    res = client.post(
        "/auth/register",
        json={
            "name": "Test User",
            "email": "bodytype-test@example.com",
            "password": "Passw0rd",
        },
    )
    assert res.status_code == 201, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


class TestSetBodyType:
    def test_valid_value_sets_body_type(self, client, auth_headers):
        res = client.post(
            "/users/me/body-type", json={"body_type": "pear"}, headers=auth_headers
        )
        assert res.status_code == 200
        body = res.json()
        assert body["body_type"] == "pear"

        get = client.get("/users/me", headers=auth_headers)
        assert get.json()["body_type"] == "pear"

    def test_invalid_value_returns_422(self, client, auth_headers):
        res = client.post(
            "/users/me/body-type", json={"body_type": "triangle"}, headers=auth_headers
        )
        assert res.status_code == 422

    def test_unauthenticated_request_returns_401(self, client):
        res = client.post("/users/me/body-type", json={"body_type": "apple"})
        assert res.status_code == 401
