"""Authenticated local backup encryption and non-destructive verification."""

from __future__ import annotations

import base64
import os
import shutil
import subprocess
import tarfile
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.exceptions import InvalidTag
from sqlalchemy.engine import make_url

_MAGIC = b"HDBK1"
_NONCE_BYTES = 12
_TAG_BYTES = 16
_AAD = b"healthdocs-backup-v1"
_CHUNK_BYTES = 1024 * 1024


class BackupError(RuntimeError):
    """Raised for invalid keys, corrupted archives, or unsafe backup content."""


def decode_backup_key(value: str) -> bytes:
    """Decode a URL-safe 256-bit key without accepting weak alternatives."""
    try:
        key = base64.urlsafe_b64decode(value.encode())
    except (ValueError, TypeError) as error:
        raise BackupError("Backup encryption key is invalid.") from error
    if len(key) != 32:
        raise BackupError("Backup encryption key must contain 32 bytes.")
    return key


def encrypted_backup_filename() -> str:
    """Return a stable UTC timestamped filename without sensitive data."""
    return f"healthdocs-{datetime.now(UTC):%Y%m%dT%H%M%SZ}.hdbak"


def create_database_dump(database_url: str, destination: Path) -> None:
    """Create a custom PostgreSQL dump without exposing the password in argv."""
    url = make_url(database_url)
    if not url.host or not url.database:
        raise BackupError("Backup database URL is incomplete.")
    environment = os.environ.copy()
    if url.password:
        environment["PGPASSWORD"] = url.password
    command = [
        "pg_dump",
        "--format=custom",
        "--no-owner",
        "--file",
        str(destination),
        "--host",
        url.host,
        "--username",
        url.username or "",
        "--dbname",
        url.database,
    ]
    if url.port:
        command.extend(["--port", str(url.port)])
    try:
        subprocess.run(command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, env=environment)
    except (OSError, subprocess.CalledProcessError) as error:
        raise BackupError("PostgreSQL dump failed.") from error


def create_encrypted_backup(sources: dict[str, Path], destination: Path, key: bytes) -> Path:
    """Archive local sources then encrypt them with streaming AES-256-GCM."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(suffix=".tar", delete=False) as temporary:
        archive_path = Path(temporary.name)
    try:
        with tarfile.open(archive_path, "w:gz") as archive:
            for name, source in sources.items():
                if not source.exists() or Path(name).is_absolute() or ".." in Path(name).parts:
                    raise BackupError("Backup sources are invalid.")
                archive.add(source, arcname=name, recursive=True)
        nonce = os.urandom(_NONCE_BYTES)
        encryptor = Cipher(algorithms.AES(key), modes.GCM(nonce)).encryptor()
        encryptor.authenticate_additional_data(_AAD)
        with archive_path.open("rb") as source, destination.open("wb") as output:
            output.write(_MAGIC + nonce)
            for chunk in iter(lambda: source.read(_CHUNK_BYTES), b""):
                output.write(encryptor.update(chunk))
            output.write(encryptor.finalize())
            output.write(encryptor.tag)
        os.chmod(destination, 0o600)
        return destination
    finally:
        archive_path.unlink(missing_ok=True)


def verify_encrypted_backup(path: Path, key: bytes) -> list[str]:
    """Authenticate, decrypt, and inspect an archive without restoring any data."""
    try:
        payload = path.read_bytes()
    except OSError as error:
        raise BackupError("Encrypted backup is unavailable.") from error
    if len(payload) <= len(_MAGIC) + _NONCE_BYTES + _TAG_BYTES or not payload.startswith(_MAGIC):
        raise BackupError("Encrypted backup format is invalid.")
    nonce_start = len(_MAGIC)
    nonce_end = nonce_start + _NONCE_BYTES
    ciphertext, tag = payload[nonce_end:-_TAG_BYTES], payload[-_TAG_BYTES:]
    decryptor = Cipher(algorithms.AES(key), modes.GCM(payload[nonce_start:nonce_end], tag)).decryptor()
    decryptor.authenticate_additional_data(_AAD)
    try:
        plaintext = decryptor.update(ciphertext) + decryptor.finalize()
    except (InvalidTag, ValueError) as error:
        raise BackupError("Encrypted backup authentication failed.") from error
    with tempfile.NamedTemporaryFile(suffix=".tar") as temporary:
        temporary.write(plaintext)
        temporary.flush()
        try:
            with tarfile.open(temporary.name, "r:gz") as archive:
                names = archive.getnames()
                database_member = archive.getmember("database.dump") if "database.dump" in names else None
                if database_member:
                    with tempfile.NamedTemporaryFile(suffix=".dump") as database_dump:
                        source = archive.extractfile(database_member)
                        if source is None:
                            raise BackupError("Encrypted backup database dump is invalid.")
                        with source:
                            shutil.copyfileobj(source, database_dump)
                        database_dump.flush()
                        subprocess.run(
                            ["pg_restore", "--list", database_dump.name],
                            check=True,
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.PIPE,
                        )
        except (OSError, subprocess.CalledProcessError, tarfile.TarError) as error:
            raise BackupError("Encrypted backup archive is invalid.") from error
    if not names or any(Path(name).is_absolute() or ".." in Path(name).parts for name in names):
        raise BackupError("Encrypted backup contains unsafe paths.")
    return names