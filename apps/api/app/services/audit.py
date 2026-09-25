"""Privacy-preserving audit persistence for material application actions."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.entities import AuditEvent


def record_audit(db: Session, action: str, entity_type: str, entity_id: UUID, metadata: dict[str, Any] | None = None) -> None:
    """Queue an audit event containing only opaque identifiers and operational metadata."""
    db.add(AuditEvent(action=action, entity_type=entity_type, entity_id=entity_id, metadata_=metadata or {}))
