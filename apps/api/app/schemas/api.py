"""Public API schemas for the first vertical slice."""

from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class LoginRequest(BaseModel):
    password: str = Field(min_length=1)


class DatabaseResetRequest(BaseModel):
    confirmation: Literal["RESET"]


class DatabaseResetResponse(BaseModel):
    status: Literal["database_reset"]


class DeletionResponse(BaseModel):
    status: Literal["deleted"]
    documents_deleted: int


class HouseholdCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)


class MemberCreate(BaseModel):
    household_id: UUID
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    fiscal_code: str | None = Field(default=None, max_length=16)
    birth_date: date | None = None
    relationship_type: str | None = Field(default=None, max_length=80)


class HouseholdMemberResponse(BaseModel):
    id: UUID
    first_name: str
    last_name: str
    fiscal_code: str | None
    relationship_type: str | None


class HouseholdResponse(BaseModel):
    id: UUID
    name: str
    members: list[HouseholdMemberResponse]


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    original_filename: str
    logical_name: str | None
    mime_type: str
    byte_size: int
    sha256: str
    state: str
    document_type: str
    duplicate_of_id: UUID | None
    patient_name: str | None
    document_date: date | None
    total_amount: str | None
    extraction: dict[str, object] | None
    created_at: datetime


class UploadResponse(BaseModel):
    document: DocumentResponse
    job_status: str


class GraphNode(BaseModel):
    id: str
    type: str
    label: str
    metadata: dict[str, str | float | None]
    status: str


class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    type: str
    confidence: float
    evidence: list[str]
    conflicts: list[str]


class EventGraph(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]


class MedicalEventResponse(BaseModel):
    id: UUID
    title: str
    status: str
    confidence: float


class ReviewResponse(BaseModel):
    id: UUID
    type: str
    entity_type: str
    entity_id: UUID
    status: str
    priority: int
    context: dict[str, object]


class ReviewResolution(BaseModel):
    resolution: dict[str, object]


class ManualDocumentCompletion(BaseModel):
    document_type: Literal["PRESCRIPTION", "INVOICE", "MEDICAL_REPORT"]
    document_date: date
    patient_name: str = Field(min_length=2, max_length=200)
    service_description: str = Field(min_length=2, max_length=500)
    total_amount: Decimal | None = Field(default=None, ge=0)
    provider_name: str | None = Field(default=None, max_length=255)


class AssociationDecision(BaseModel):
    action: Literal["approve", "reject"]
    reason: str | None = Field(default=None, max_length=1000)


class AssociationRebuildResponse(BaseModel):
    documents_queued: int
    events_removed: int


class InsuranceResponse(BaseModel):
    category: str
    status: str
    documentation_complete: bool
    documented_amount: str
    estimated_eligible_amount: str
    estimate_basis: str
    rules: list[str]
    evidence: list[str]
    missing_documents: list[str]
    warnings: list[str]


class PharmacyReceiptCreate(BaseModel):
    document_id: UUID
    payer_id: UUID | None = None
    receipt_date: date | None = None
    total_amount: Decimal | None = None


class ReceiptLineCreate(BaseModel):
    description: str = Field(min_length=1, max_length=255)
    amount: Decimal | None = None
    aic_text: str | None = Field(default=None, max_length=64)
    patient_id: UUID | None = None


class MixedAllocation(BaseModel):
    allocations: dict[UUID, UUID]


class ReimbursementCreate(BaseModel):
    document_id: UUID | None = None
    payer_id: UUID | None = None
    amount: Decimal = Field(gt=0)
    source: str = Field(default="manual", max_length=32)
    reference: str | None = Field(default=None, max_length=255)


class ReimbursementAllocationCreate(BaseModel):
    expense_document_id: UUID
    amount: Decimal = Field(gt=0)


class PaymentEvidenceCreate(BaseModel):
    method: str = Field(min_length=1, max_length=32)
    traceable: bool
    reference: str | None = Field(default=None, max_length=255)
