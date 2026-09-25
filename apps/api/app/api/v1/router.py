"""Versioned HTTP API for ingestion and the initial graph workspace."""

from __future__ import annotations

from uuid import UUID

from arq import create_pool
from arq.connections import RedisSettings
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.adapters.lmstudio import LMStudioProvider, LLMUnavailable
from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.models.entities import Document, DocumentLink, Household, HouseholdMember, MedicalEvent
from app.schemas.api import DocumentResponse, EventGraph, GraphEdge, GraphNode, HouseholdCreate, MemberCreate, UploadResponse
from app.services.storage import ImmutableStorage, UnsupportedDocument

router = APIRouter(prefix="/api/v1")


def document_response(document: Document) -> DocumentResponse:
    return DocumentResponse(
        id=document.id,
        original_filename=document.original_filename,
        mime_type=document.mime_type,
        byte_size=document.byte_size,
        sha256=document.sha256,
        state=document.state.value,
        document_type=document.document_type.value,
        duplicate_of_id=document.duplicate_of_id,
        created_at=document.created_at,
    )


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/ai")
async def ai_health(settings: Settings = Depends(get_settings)) -> dict[str, object]:
    provider = LMStudioProvider(settings)
    try:
        models = await provider.models()
        configured = settings.lmstudio_main_model
        return {"lmstudio": {"connected": True, "model": configured, "configured_model_available": configured in models}}
    except LLMUnavailable:
        return {"lmstudio": {"connected": False, "model": settings.lmstudio_main_model}}


@router.get("/settings/models")
async def available_models(settings: Settings = Depends(get_settings)) -> dict[str, list[str]]:
    try:
        return {"models": await LMStudioProvider(settings).models()}
    except LLMUnavailable as error:
        raise HTTPException(status_code=503, detail="LM Studio is unavailable.") from error


@router.post("/documents", response_model=UploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> UploadResponse:
    content = await file.read(settings.max_upload_bytes + 1)
    try:
        stored = ImmutableStorage(settings).store(content, file.filename)
    except UnsupportedDocument as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

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
    db.commit()
    db.refresh(document)
    try:
        redis = await create_pool(RedisSettings.from_dsn(settings.redis_url))
        await redis.enqueue_job("process_document", str(document.id))
        await redis.close()
    except OSError as error:
        raise HTTPException(status_code=503, detail="Document stored, but the processing queue is unavailable.") from error
    return UploadResponse(document=document_response(document), job_status="queued")


@router.get("/documents", response_model=list[DocumentResponse])
def list_documents(db: Session = Depends(get_db)) -> list[DocumentResponse]:
    return [document_response(item) for item in db.scalars(select(Document).order_by(Document.created_at.desc()))]


@router.post("/households", status_code=status.HTTP_201_CREATED)
def create_household(payload: HouseholdCreate, db: Session = Depends(get_db)) -> dict[str, str]:
    household = Household(name=payload.name)
    db.add(household)
    db.commit()
    return {"id": str(household.id), "name": household.name}


@router.post("/household-members", status_code=status.HTTP_201_CREATED)
def create_member(payload: MemberCreate, db: Session = Depends(get_db)) -> dict[str, str]:
    household = db.get(Household, payload.household_id)
    if household is None:
        raise HTTPException(status_code=404, detail="Household not found.")
    member = HouseholdMember(**payload.model_dump(), fiscal_code=payload.fiscal_code.upper() if payload.fiscal_code else None)
    db.add(member)
    db.commit()
    return {"id": str(member.id), "name": f"{member.first_name} {member.last_name}"}


@router.get("/medical-events/{event_id}/graph", response_model=EventGraph)
def medical_event_graph(event_id: UUID, db: Session = Depends(get_db)) -> EventGraph:
    event = db.get(MedicalEvent, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Medical event not found.")
    nodes = [GraphNode(id=str(event.id), type="medical_event", label=event.title, metadata={"confidence": event.confidence}, status=event.status.value)]
    edges: list[GraphEdge] = []
    for link in db.scalars(select(DocumentLink).where(DocumentLink.medical_event_id == event.id)):
        for document_id in (link.source_document_id, link.target_document_id):
            document = db.get(Document, document_id)
            if document and not any(node.id == str(document.id) for node in nodes):
                nodes.append(GraphNode(id=str(document.id), type="document", label=document.original_filename, metadata={"document_type": document.document_type.value}, status=document.state.value))
        edges.append(GraphEdge(id=str(link.id), source=str(link.source_document_id), target=str(link.target_document_id), type=link.relation_type, confidence=link.score, evidence=link.evidence, conflicts=link.conflicts))
    return EventGraph(nodes=nodes, edges=edges)
