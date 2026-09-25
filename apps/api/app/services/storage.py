"""Immutable local storage adapter for uploaded originals."""

from __future__ import annotations

import hashlib
import re
import uuid
from dataclasses import dataclass
from pathlib import Path

from app.core.config import Settings

_SAFE_FILENAME = re.compile(r"[^A-Za-z0-9._-]+")


class UnsupportedDocument(ValueError):
    """Raised when an upload does not satisfy the supported-file policy."""


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
    raise UnsupportedDocument("Only PDF, PNG, and JPEG uploads are supported in this milestone.")


def sanitize_filename(filename: str | None) -> str:
    """Return a presentation-only filename with path components removed."""
    candidate = Path(filename or "document").name
    return _SAFE_FILENAME.sub("_", candidate).strip("._")[:200] or "document"


class ImmutableStorage:
    """Store each original once under a UUID/hash-derived path."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def store(self, content: bytes, filename: str | None) -> StoredFile:
        if len(content) > self._settings.max_upload_bytes:
            raise UnsupportedDocument("The uploaded file exceeds the configured size limit.")
        if not content:
            raise UnsupportedDocument("Empty uploads are not allowed.")
        mime_type = sniff_mime(content)
        digest = hashlib.sha256(content).hexdigest()
        suffix = {"application/pdf": ".pdf", "image/png": ".png", "image/jpeg": ".jpg"}[mime_type]
        storage_key = f"originals/{digest[:2]}/{uuid.uuid4()}{suffix}"
        destination = self._settings.storage_root / storage_key
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)
        return StoredFile(digest, len(content), mime_type, sanitize_filename(filename), storage_key)
