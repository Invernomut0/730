"""Persistence models. Clinical payloads stay out of application logs."""

from __future__ import annotations

import enum
import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import Date, DateTime, Enum, Float, ForeignKey, JSON, Numeric, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base for all ORM entities."""


class Timestamped:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class DocumentState(str, enum.Enum):
    DISCOVERED = "DISCOVERED"
    STORED = "STORED"
    EXTRACTING = "EXTRACTING"
    OCR = "OCR"
    CLASSIFYING = "CLASSIFYING"
    STRUCTURING = "STRUCTURING"
    NORMALIZING = "NORMALIZING"
    LINKING = "LINKING"
    EVENT_CLUSTERING = "EVENT_CLUSTERING"
    INSURANCE_EVALUATION = "INSURANCE_EVALUATION"
    COMPLETE = "COMPLETE"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    FAILED = "FAILED"


class DocumentType(str, enum.Enum):
    INVOICE = "INVOICE"
    PRESCRIPTION = "PRESCRIPTION"
    MEDICAL_REPORT = "MEDICAL_REPORT"
    PHARMACY_RECEIPT = "PHARMACY_RECEIPT"
    OTHER = "OTHER"
    UNKNOWN = "UNKNOWN"


class EventStatus(str, enum.Enum):
    PROPOSED = "PROPOSED"
    CONFIRMED = "CONFIRMED"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    ARCHIVED = "ARCHIVED"


class ReviewType(str, enum.Enum):
    PATIENT_CONFLICT = "PATIENT_CONFLICT"
    DOCUMENT_TYPE_UNCERTAIN = "DOCUMENT_TYPE_UNCERTAIN"
    LINK_AMBIGUOUS = "LINK_AMBIGUOUS"
    DIAGNOSIS_MISSING = "DIAGNOSIS_MISSING"
    INSURANCE_RULE_AMBIGUOUS = "INSURANCE_RULE_AMBIGUOUS"


class Household(Timestamped, Base):
    __tablename__ = "households"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(160))
    members: Mapped[list[HouseholdMember]] = relationship(back_populates="household")


class HouseholdMember(Timestamped, Base):
    __tablename__ = "household_members"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    household_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("households.id"), index=True)
    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
    fiscal_code: Mapped[str | None] = mapped_column(String(16), unique=True, nullable=True)
    birth_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    relationship_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    household: Mapped[Household] = relationship(back_populates="members")


class Document(Timestamped, Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    original_filename: Mapped[str] = mapped_column(String(255))
    mime_type: Mapped[str] = mapped_column(String(100))
    byte_size: Mapped[int]
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    storage_key: Mapped[str] = mapped_column(String(512), unique=True)
    state: Mapped[DocumentState] = mapped_column(Enum(DocumentState), default=DocumentState.STORED)
    document_type: Mapped[DocumentType] = mapped_column(Enum(DocumentType), default=DocumentType.UNKNOWN)
    patient_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("household_members.id"), nullable=True)
    document_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    duplicate_of_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("documents.id"), nullable=True)
    pages: Mapped[list[DocumentPage]] = relationship(back_populates="document", cascade="all, delete-orphan")


class DocumentPage(Timestamped, Base):
    __tablename__ = "document_pages"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id"), index=True)
    page_number: Mapped[int]
    text: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(32), default="native")
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    blocks: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    document: Mapped[Document] = relationship(back_populates="pages")


class Prescription(Timestamped, Base):
    __tablename__ = "prescriptions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id"), unique=True)
    patient_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("household_members.id"), nullable=True)
    prescription_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    provider: Mapped[str | None] = mapped_column(String(255), nullable=True)
    extraction: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class ExpenseDocument(Timestamped, Base):
    __tablename__ = "expense_documents"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id"), unique=True)
    patient_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("household_members.id"), nullable=True)
    invoice_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    provider_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    total_amount: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    extraction: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class MedicalEvent(Timestamped, Base):
    __tablename__ = "medical_events"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    household_member_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("household_members.id"), nullable=True)
    title: Mapped[str] = mapped_column(String(255))
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[EventStatus] = mapped_column(Enum(EventStatus), default=EventStatus.PROPOSED)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)


class DocumentLink(Timestamped, Base):
    __tablename__ = "document_links"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    source_document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id"), index=True)
    target_document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id"), index=True)
    medical_event_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("medical_events.id"), nullable=True)
    relation_type: Mapped[str] = mapped_column(String(64), default="RELATED_TO")
    score: Mapped[float] = mapped_column(Float)
    evidence: Mapped[list[str]] = mapped_column(JSON, default=list)
    conflicts: Mapped[list[str]] = mapped_column(JSON, default=list)


class ReviewTask(Timestamped, Base):
    __tablename__ = "review_tasks"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    type: Mapped[ReviewType] = mapped_column(Enum(ReviewType))
    entity_type: Mapped[str] = mapped_column(String(64))
    entity_id: Mapped[uuid.UUID] = mapped_column(index=True)
    status: Mapped[str] = mapped_column(String(32), default="OPEN")
    priority: Mapped[int] = mapped_column(default=50)
    context: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolution: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)


class AIExecution(Timestamped, Base):
    __tablename__ = "ai_executions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("documents.id"), nullable=True)
    provider: Mapped[str] = mapped_column(String(64))
    model: Mapped[str] = mapped_column(String(255))
    prompt_name: Mapped[str] = mapped_column(String(128))
    prompt_version: Mapped[str] = mapped_column(String(32))
    schema_version: Mapped[str] = mapped_column(String(32))
    input_hash: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32))
    duration_ms: Mapped[int | None] = mapped_column(nullable=True)


class AuditEvent(Timestamped, Base):
    __tablename__ = "audit_events"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    action: Mapped[str] = mapped_column(String(128))
    entity_type: Mapped[str] = mapped_column(String(64))
    entity_id: Mapped[uuid.UUID] = mapped_column(index=True)
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict)
