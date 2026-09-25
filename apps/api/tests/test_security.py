from app.core.security import password_hash, verify_password
from fastapi.testclient import TestClient

from app.main import app


def test_argon2_password_verification_accepts_correct_password() -> None:
    encoded = password_hash.hash("synthetic-test-password")
    assert verify_password("synthetic-test-password", encoded)


def test_argon2_password_verification_rejects_wrong_password() -> None:
    encoded = password_hash.hash("synthetic-test-password")
    assert not verify_password("wrong-password", encoded)


def test_local_web_origin_can_preflight_household_creation() -> None:
    with TestClient(app) as client:
        response = client.options(
            "/api/v1/households",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert "POST" in response.headers["access-control-allow-methods"]
