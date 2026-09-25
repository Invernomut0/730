from app.core.security import password_hash, verify_password


def test_argon2_password_verification_accepts_correct_password() -> None:
    encoded = password_hash.hash("synthetic-test-password")
    assert verify_password("synthetic-test-password", encoded)


def test_argon2_password_verification_rejects_wrong_password() -> None:
    encoded = password_hash.hash("synthetic-test-password")
    assert not verify_password("wrong-password", encoded)
