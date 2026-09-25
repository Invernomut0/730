"""Immutable local storage adapter for uploaded originals."""

from __future__ import annotations

import hashlib
import os
import re
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path

from app.core.config import Settings

_SAFE_FILENAME = re.compile(r"[^A-Za-z0-9._-]+")


class UnsupportedDocument(ValueError):
    """Raised when an upload does not satisfy the supported-file policy."""


class UploadTooLarge(UnsupportedDocument):
    """Raised when an upload exceeds a configured request or file limit."""


@dataclass(frozen=True)
class StoredFile:
    sha256: str
    byte_size: int
    mime_type: str
    original_filename: str
    storage_key: str


def sniff_mime(content: bytes) -> str:
    """Recognize the supported binary formats without trusting HTTP headers."""
    if content.startswith(b"%PDF-"):
        return "application/pdf"
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if content.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if content.startswith((b"II*\x00", b"MM\x00*")):
        return "image/tiff"
    if content[4:8] == b"ftyp" and content[8:12] in {b"heic", b"heix", b"hevc", b"hevx", b"mif1"}:
        return "image/heic"
    raise UnsupportedDocument("Only PDF, PNG, JPEG, TIFF, and HEIC uploads are supported.")


def sanitize_filename(filename: str | None) -> str:
    """Return a presentation-only filename with path components removed."""
    candidate = Path(filename or "document").name
    return _SAFE_FILENAME.sub("_", candidate).strip("._")[:200] or "document"


def validate_declared_request_size(
    content_length: str | None, max_upload_bytes: int, request_overhead_bytes: int
) -> None:
    """Reject clearly oversized multipart requests before buffering their body."""
    if content_length is None:
        return
    try:
        declared_size = int(content_length)
    except ValueError as error:
        raise UnsupportedDocument("The upload size header is invalid.") from error
    if declared_size < 0:
        raise UnsupportedDocument("The upload size header is invalid.")
    if declared_size > max_upload_bytes + request_overhead_bytes:
        raise UploadTooLarge("The upload request exceeds the configured size limit.")


class ImmutableStorage:
    """Store each original once under a UUID/hash-derived path."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def store(self, content: bytes, filename: str | None) -> StoredFile:
        if len(content) > self._settings.max_upload_bytes:
            raise UploadTooLarge("The uploaded file exceeds the configured size limit.")
        if not content:
            raise UnsupportedDocument("Empty uploads are not allowed.")
        mime_type = sniff_mime(content)
        digest = hashlib.sha256(content).hexdigest()
        suffix = {
            "application/pdf": ".pdf",
            "image/png": ".png",
            "image/jpeg": ".jpg",
            "image/tiff": ".tiff",
            "image/heic": ".heic",
        }[mime_type]
        storage_key = f"originals/{digest[:2]}/{uuid.uuid4()}{suffix}"
        destination = self._settings.storage_root / storage_key
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(dir=destination.parent, delete=False) as temporary:
                temporary_path = Path(temporary.name)
                os.chmod(temporary_path, 0o600)
                temporary.write(content)
                temporary.flush()
                os.fsync(temporary.fileno())
            os.replace(temporary_path, destination)
        except OSError as error:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)
            raise UnsupportedDocument("The upload could not be stored safely.") from error
        return StoredFile(digest, len(content), mime_type, sanitize_filename(filename), storage_key)
