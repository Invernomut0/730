"""Versioned HTTP API for ingestion and the initial graph workspace."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from arq import create_pool
from arq.connections import RedisSettings
from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.adapters.lmstudio import LMStudioProvider, LLMUnavailable
from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.models.entities import (
    Document,
    DocumentLink,
    DocumentPage,
    ExpenseDocument,
    Household,
    HouseholdMember,
    MedicalEvent,
    PharmacyReceipt,
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
    LoginRequest,
    MedicalEventResponse,
    MemberCreate,
    ReviewResolution,
    ReviewResponse,
    UploadResponse,
    PharmacyReceiptCreate,
    ReceiptLineCreate,
    MixedAllocation,
)
from app.services.insurance import evaluate_specialist_and_diagnostics
from app.services.identity import normalize_fiscal_code
from app.services.audit import record_audit
from app.core.security import verify_password
from app.services.storage import ImmutableStorage, UnsupportedDocument
from app.services.thumbnails import thumbnail_path
from app.services.pharmacy import add_receipt_line, allocate_receipt, import_aifa_csv, match_receipt_lines

router = APIRouter(prefix="/api/v1")


def document_response(document: Document, db: Session) -> DocumentResponse:
    patient = db.get(HouseholdMember, document.patient_id) if document.patient_id else None
    prescription = db.scalar(select(Prescription).where(Prescription.document_id == document.id))
    expense = db.scalar(select(ExpenseDocument).where(ExpenseDocument.document_id == document.id))
    return DocumentResponse(
        id=document.id,
        original_filename=document.original_filename,
        logical_name=document.logical_name,
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


@router.post("/auth/login")
def login(payload: LoginRequest, request: Request, settings: Settings = Depends(get_settings)) -> dict[str, str]:
    """Create a local authenticated session when LAN authentication is enabled."""
    if not settings.auth_enabled:
        raise HTTPException(status_code=409, detail="Authentication is disabled in this environment.")
    if not settings.auth_password_hash or not settings.session_secret:
        raise HTTPException(status_code=503, detail="Authentication is not securely configured.")
    if not verify_password(payload.password, settings.auth_password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials.")
    request.session["authenticated"] = True
    return {"status": "authenticated"}


@router.post("/auth/logout")
def logout(request: Request) -> dict[str, str]:
    """Clear the browser's local authenticated session."""
    request.session.clear()
    return {"status": "signed_out"}


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
    db.flush()
    record_audit(db, "document.uploaded", "Document", document.id, {"mime_type": document.mime_type})
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


@router.get("/documents/{document_id}/thumbnail")
def document_thumbnail(
    document_id: UUID,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> FileResponse:
    """Serve the generated preview only for an existing local document."""
    document = db.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    preview = thumbnail_path(settings.storage_root, document.sha256)
    if not preview.is_file():
        raise HTTPException(status_code=404, detail="Thumbnail is not available yet.")
    return FileResponse(preview, media_type="image/png")


@router.get("/documents/{document_id}/pages")
def document_pages(document_id: UUID, db: Session = Depends(get_db)) -> list[dict[str, object]]:
    """Return local OCR text and bounding boxes for the document viewer."""
    if db.get(Document, document_id) is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    return [
        {"page_number": page.page_number, "text": page.text or "", "source": page.source, "confidence": page.confidence, "blocks": page.blocks}
        for page in db.scalars(select(DocumentPage).where(DocumentPage.document_id == document_id).order_by(DocumentPage.page_number))
    ]


@router.post("/pharmacy/catalog/import")
def import_pharmacy_catalog(db: Session = Depends(get_db), settings: Settings = Depends(get_settings)) -> dict[str, int]:
    """Import the operator-provided local AIFA-compatible catalog CSV."""
    if not settings.aifa_catalog_path.is_file():
        raise HTTPException(status_code=404, detail="Local AIFA catalog CSV is not available.")
    count = import_aifa_csv(db, settings.aifa_catalog_path, datetime.now(UTC).date().isoformat())
    return {"imported": count}


@router.post("/pharmacy/receipts", status_code=status.HTTP_201_CREATED)
def create_pharmacy_receipt(payload: PharmacyReceiptCreate, db: Session = Depends(get_db)) -> dict[str, str]:
    """Create a pharmacy receipt linked to an immutable document."""
    if db.get(Document, payload.document_id) is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    receipt = PharmacyReceipt(**payload.model_dump())
    db.add(receipt)
    db.flush()
    record_audit(db, "pharmacy_receipt.created", "PharmacyReceipt", receipt.id)
    db.commit()
    return {"id": str(receipt.id)}


@router.post("/pharmacy/receipts/{receipt_id}/lines", status_code=status.HTTP_201_CREATED)
def create_receipt_line(receipt_id: UUID, payload: ReceiptLineCreate, db: Session = Depends(get_db)) -> dict[str, object]:
    receipt = db.get(PharmacyReceipt, receipt_id)
    if receipt is None:
        raise HTTPException(status_code=404, detail="Pharmacy receipt not found.")
    line = add_receipt_line(db, receipt, payload.description, payload.amount, payload.aic_text, payload.patient_id)
    db.flush()
    record_audit(db, "receipt_line.created", "ReceiptLine", line.id, {"aic_validated": line.aic_validated})
    db.commit()
    return {"id": str(line.id), "aic": line.aic, "aic_validated": line.aic_validated}


@router.post("/pharmacy/receipts/{receipt_id}/match")
def match_pharmacy_receipt(receipt_id: UUID, db: Session = Depends(get_db)) -> dict[str, int]:
    if db.get(PharmacyReceipt, receipt_id) is None:
        raise HTTPException(status_code=404, detail="Pharmacy receipt not found.")
    return {"matched": match_receipt_lines(db, receipt_id)}


@router.post("/pharmacy/receipts/{receipt_id}/allocate")
def allocate_pharmacy_receipt(receipt_id: UUID, payload: MixedAllocation, db: Session = Depends(get_db)) -> dict[str, object]:
    try:
        result = allocate_receipt(db, receipt_id, payload.allocations)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return {"allocated_amount": str(result.allocated_amount), "review_required": result.review_required}


@router.post("/households", status_code=status.HTTP_201_CREATED)
def create_household(payload: HouseholdCreate, db: Session = Depends(get_db)) -> dict[str, str]:
    household = Household(name=payload.name)
    db.add(household)
    db.flush()
    record_audit(db, "household.created", "Household", household.id)
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
    db.flush()
    record_audit(db, "household_member.created", "HouseholdMember", member.id)
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
    record_audit(db, "review.resolved", "ReviewTask", task.id)
    db.commit()
    return ReviewResponse(id=task.id, type=task.type.value, entity_type=task.entity_type, entity_id=task.entity_id, status=task.status, priority=task.priority, context=task.context)
