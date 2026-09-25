"""Local password authentication and session protection."""

from pwdlib import PasswordHash

password_hash = PasswordHash.recommended()


def verify_password(password: str, encoded_password: str) -> bool:
    """Verify an Argon2 password hash without persisting raw credentials."""
    try:
        return password_hash.verify(password, encoded_password)
    except ValueError:
        return False
