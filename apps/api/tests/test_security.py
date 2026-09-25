import pytest

from app.core.security import password_hash, verify_password
from app.db.session import SessionLocal
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.main import app
from app.models.entities import Document


def test_argon2_password_verification_accepts_correct_password() -> None:
    encoded = password_hash.hash("synthetic-test-password")
    assert verify_password("synthetic-test-password", encoded)


def test_argon2_password_verification_rejects_wrong_password() -> None:
    encoded = password_hash.hash("synthetic-test-password")
    assert not verify_password("wrong-password", encoded)


@pytest.mark.parametrize("origin", ["http://localhost:3000", "http://127.0.0.1:3000"])
def test_local_web_origins_can_preflight_household_creation(origin: str) -> None:
    with TestClient(app) as client:
        response = client.options(
            "/api/v1/households",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin
    assert "POST" in response.headers["access-control-allow-methods"]


def test_database_reset_requires_exact_operator_confirmation() -> None:
    database = SessionLocal()
    try:
        before_count = database.scalar(select(func.count()).select_from(Document))
        with TestClient(app) as client:
            response = client.post("/api/v1/admin/reset-database", json={"confirmation": "reset"})
        assert response.status_code == 422
        assert database.scalar(select(func.count()).select_from(Document)) == before_count
    finally:
        database.close()
