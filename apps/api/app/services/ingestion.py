"""Application service for immutable local-file ingestion."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models.entities import Document
from app.services.audit import record_audit
from app.services.storage import ImmutableStorage, StoredFile


def ingest_content(db: Session, settings: Settings, content: bytes, filename: str | None) -> Document:
    """Persist an immutable original and document record in one transaction."""
    stored: StoredFile = ImmutableStorage(settings).store(content, filename)
    existing = db.scalar(select(Document).where(Document.sha256 == stored.sha256).order_by(Document.created_at))
    document = Document(
        original_filename=stored.original_filename,
        mime_type=stored.mime_type,
        byte_size=stored.byte_size,
        sha256=stored.sha256,
        storage_key=stored.storage_key,
        duplicate_of_id=existing.id if existing else None,
    )
    db.add(document)
    db.flush()
    record_audit(db, "document.ingested", "Document", document.id, {"mime_type": document.mime_type})
    db.commit()
    db.refresh(document)
    return document


def archive_inbox_file(path: Path, destination_root: Path) -> Path:
    """Move a consumed inbox source without using it as an immutable storage key."""
    destination_root.mkdir(parents=True, exist_ok=True)
    destination = destination_root / path.name
    if destination.exists():
        destination = destination_root / f"{path.stem}-{path.stat().st_mtime_ns}{path.suffix}"
    return path.replace(destination)
