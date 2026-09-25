"""Versioned HTTP API for ingestion and the initial graph workspace."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from arq import create_pool
from arq.connections import RedisSettings
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.adapters.lmstudio import LMStudioProvider, LLMUnavailable
from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.models.entities import (
    Document,
    DocumentLink,
    ExpenseDocument,
    Household,
    HouseholdMember,
    MedicalEvent,
    Prescription,
    ReviewTask,
)
from app.schemas.api import (
    DocumentResponse,
    EventGraph,
    GraphEdge,
    GraphNode,
    HouseholdCreate,
    HouseholdMemberResponse,
    HouseholdResponse,
    InsuranceResponse,
    MedicalEventResponse,
    MemberCreate,
    ReviewResolution,
    ReviewResponse,
    UploadResponse,
)
from app.services.insurance import evaluate_specialist_and_diagnostics
from app.services.identity import normalize_fiscal_code
from app.services.storage import ImmutableStorage, UnsupportedDocument

router = APIRouter(prefix="/api/v1")


def document_response(document: Document, db: Session) -> DocumentResponse:
    patient = db.get(HouseholdMember, document.patient_id) if document.patient_id else None
    prescription = db.scalar(select(Prescription).where(Prescription.document_id == document.id))
    expense = db.scalar(select(ExpenseDocument).where(ExpenseDocument.document_id == document.id))
    return DocumentResponse(
        id=document.id,
        original_filename=document.original_filename,
        mime_type=document.mime_type,
        byte_size=document.byte_size,
        sha256=document.sha256,
        state=document.state.value,
        document_type=document.document_type.value,
        duplicate_of_id=document.duplicate_of_id,
        patient_name=f"{patient.first_name} {patient.last_name}" if patient else None,
        document_date=document.document_date,
        total_amount=str(expense.total_amount) if expense and expense.total_amount is not None else None,
        extraction=prescription.extraction if prescription else expense.extraction if expense else None,
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
    return UploadResponse(document=document_response(document, db), job_status="queued")


@router.get("/documents", response_model=list[DocumentResponse])
def list_documents(db: Session = Depends(get_db)) -> list[DocumentResponse]:
    return [document_response(item, db) for item in db.scalars(select(Document).order_by(Document.created_at.desc()))]


@router.post("/households", status_code=status.HTTP_201_CREATED)
def create_household(payload: HouseholdCreate, db: Session = Depends(get_db)) -> dict[str, str]:
    household = Household(name=payload.name)
    db.add(household)
    db.commit()
    return {"id": str(household.id), "name": household.name}


@router.get("/households", response_model=list[HouseholdResponse])
def list_households(db: Session = Depends(get_db)) -> list[HouseholdResponse]:
    return [
        HouseholdResponse(
            id=household.id,
            name=household.name,
            members=[
                HouseholdMemberResponse(
                    id=member.id,
                    first_name=member.first_name,
                    last_name=member.last_name,
                    fiscal_code=member.fiscal_code,
                    relationship_type=member.relationship_type,
                )
                for member in household.members
            ],
        )
        for household in db.scalars(select(Household).order_by(Household.name))
    ]


@router.post("/household-members", status_code=status.HTTP_201_CREATED)
def create_member(payload: MemberCreate, db: Session = Depends(get_db)) -> dict[str, str]:
    household = db.get(Household, payload.household_id)
    if household is None:
        raise HTTPException(status_code=404, detail="Household not found.")
    try:
        fiscal_code = normalize_fiscal_code(payload.fiscal_code) if payload.fiscal_code else None
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    member = HouseholdMember(**payload.model_dump(exclude={"fiscal_code"}), fiscal_code=fiscal_code)
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


@router.get("/medical-events", response_model=list[MedicalEventResponse])
def list_medical_events(db: Session = Depends(get_db)) -> list[MedicalEventResponse]:
    return [
        MedicalEventResponse(id=item.id, title=item.title, status=item.status.value, confidence=item.confidence)
        for item in db.scalars(select(MedicalEvent).order_by(MedicalEvent.created_at.desc()))
    ]


@router.get("/medical-events/{event_id}/insurance-evaluation", response_model=InsuranceResponse)
def insurance_evaluation(event_id: UUID, db: Session = Depends(get_db)) -> InsuranceResponse:
    if db.get(MedicalEvent, event_id) is None:
        raise HTTPException(status_code=404, detail="Medical event not found.")
    result = evaluate_specialist_and_diagnostics(db, event_id)
    return InsuranceResponse(
        category=result.category,
        status=result.status,
        documentation_complete=result.documentation_complete,
        estimated_eligible_amount=str(result.estimated_eligible_amount),
        rules=result.rules,
        evidence=[item for item in result.evidence if item],
        missing_documents=result.missing_documents,
        warnings=result.warnings,
    )


@router.get("/review-tasks", response_model=list[ReviewResponse])
def list_review_tasks(db: Session = Depends(get_db)) -> list[ReviewResponse]:
    return [
        ReviewResponse(id=item.id, type=item.type.value, entity_type=item.entity_type, entity_id=item.entity_id, status=item.status, priority=item.priority, context=item.context)
        for item in db.scalars(select(ReviewTask).where(ReviewTask.status == "OPEN").order_by(ReviewTask.priority.desc()))
    ]


@router.post("/review-tasks/{task_id}/resolve", response_model=ReviewResponse)
def resolve_review_task(task_id: UUID, payload: ReviewResolution, db: Session = Depends(get_db)) -> ReviewResponse:
    task = db.get(ReviewTask, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Review task not found.")
    task.status = "RESOLVED"
    task.resolution = payload.resolution
    task.resolved_at = datetime.now(UTC)
    db.commit()
    return ReviewResponse(id=task.id, type=task.type.value, entity_type=task.entity_type, entity_id=task.entity_id, status=task.status, priority=task.priority, context=task.context)
