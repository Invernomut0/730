"""Public API schemas for the first vertical slice."""

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class HouseholdCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)


class MemberCreate(BaseModel):
    household_id: UUID
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    fiscal_code: str | None = Field(default=None, max_length=16)
    birth_date: date | None = None
    relationship_type: str | None = Field(default=None, max_length=80)


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    original_filename: str
    mime_type: str
    byte_size: int
    sha256: str
    state: str
    document_type: str
    duplicate_of_id: UUID | None
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
