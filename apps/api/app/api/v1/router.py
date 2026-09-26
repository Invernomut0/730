"""Versioned HTTP API for ingestion and the initial graph workspace."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from arq import create_pool
from arq.connections import RedisSettings
from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.adapters.lmstudio import LMStudioProvider, LLMUnavailable
from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.models.entities import (
    Document,
    DocumentLink,
    DocumentPage,
    DocumentState,
    ExpenseDocument,
    Household,
    HouseholdMember,
    MedicalReport,
    MedicalEvent,
    EventStatus,
    DocumentType,
    PharmacyReceipt,
    Prescription,
    ReviewTask,
    ReviewType,
    Reimbursement,
    PaymentEvidence,
    Precompiled730Row,
)
from app.schemas.api import (
    DatabaseResetRequest,
    DatabaseResetResponse,
    DeletionResponse,
    DocumentResponse,
    EventGraph,
    GraphEdge,
    GraphNode,
    HouseholdCreate,
    HouseholdMemberResponse,
    HouseholdResponse,
    InsuranceResponse,
    LoginRequest,
    AssociationDecision,
    ManualDocumentCompletion,
    MedicalEventResponse,
    MemberCreate,
    ReviewResolution,
    ReviewResponse,
    UploadResponse,
    PharmacyReceiptCreate,
    ReceiptLineCreate,
    MixedAllocation,
    ReimbursementCreate,
    ReimbursementAllocationCreate,
    PaymentEvidenceCreate,
)
from app.services.insurance import evaluate_specialist_and_diagnostics, export_package
from app.services.identity import normalize_fiscal_code, resolve_patient
from app.services.audit import record_audit
from app.core.security import verify_password
from app.services.auth_rate_limit import LoginRateLimitUnavailable, clear_login_attempts, consume_login_attempt
from app.services.storage import ImmutableStorage, UnsupportedDocument, UploadTooLarge, validate_declared_request_size
from app.services.thumbnails import thumbnail_path
from app.services.reimbursements import allocate_reimbursement, out_of_pocket
from app.services.tax import evaluate_expense
from app.services.precompiled_730 import import_csv, reconcile
from app.services.pharmacy import add_receipt_line, allocate_receipt, import_aifa_csv, match_receipt_lines
from app.services.database_reset import reset_application_database
from app.services.deletion import delete_document_group, delete_household
from app.services.eventing import cluster_document, medical_event_title, refresh_legacy_event_title

router = APIRouter(prefix="/api/v1")


def document_response(document: Document, db: Session) -> DocumentResponse:
    patient = db.get(HouseholdMember, document.patient_id) if document.patient_id else None
    prescription = db.scalar(select(Prescription).where(Prescription.document_id == document.id))
    expense = db.scalar(select(ExpenseDocument).where(ExpenseDocument.document_id == document.id))
    report = db.scalar(select(MedicalReport).where(MedicalReport.document_id == document.id))
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
        extraction=prescription.extraction if prescription else expense.extraction if expense else report.extraction if report else None,
        created_at=document.created_at,
    )


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/admin/reset-database", response_model=DatabaseResetResponse)
def reset_database(payload: DatabaseResetRequest, db: Session = Depends(get_db)) -> DatabaseResetResponse:
    """Permanently clear all application tables after explicit operator confirmation."""
    reset_application_database(db)
    return DatabaseResetResponse(status="database_reset")


@router.post("/auth/login")
async def login(payload: LoginRequest, request: Request, settings: Settings = Depends(get_settings)) -> dict[str, str]:
    """Create a local authenticated session when LAN authentication is enabled."""
    if not settings.auth_enabled:
        raise HTTPException(status_code=409, detail="Authentication is disabled in this environment.")
    if not settings.auth_password_hash or not settings.session_secret:
        raise HTTPException(status_code=503, detail="Authentication is not securely configured.")
    client_host = request.client.host if request.client else "unknown"
    try:
        permitted = await consume_login_attempt(
            settings.redis_url, client_host, settings.login_rate_limit_attempts, settings.login_rate_limit_window_seconds
        )
    except LoginRateLimitUnavailable as error:
        raise HTTPException(status_code=503, detail="Login protection is unavailable.") from error
    if not permitted:
        raise HTTPException(status_code=429, detail="Too many login attempts. Try again later.")
    if not verify_password(payload.password, settings.auth_password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials.")
    try:
        await clear_login_attempts(settings.redis_url, client_host)
    except LoginRateLimitUnavailable as error:
        raise HTTPException(status_code=503, detail="Login protection is unavailable.") from error
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
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> UploadResponse:
    try:
        validate_declared_request_size(
            request.headers.get("content-length"),
            settings.max_upload_bytes,
            settings.max_upload_request_overhead_bytes,
        )
    except UploadTooLarge as error:
        raise HTTPException(status_code=413, detail=str(error)) from error
    except UnsupportedDocument as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    content = await file.read(settings.max_upload_bytes + 1)
    try:
        stored = ImmutableStorage(settings).store(content, file.filename)
    except UploadTooLarge as error:
        raise HTTPException(status_code=413, detail=str(error)) from error
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


@router.delete("/documents/{document_id}", response_model=DeletionResponse)
def delete_document(document_id: UUID, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)) -> DeletionResponse:
    """Remove a document group and all dependent records and local artifacts."""
    try:
        count = delete_document_group(db, settings.storage_root, document_id)
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return DeletionResponse(status="deleted", documents_deleted=count)


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


@router.post("/reimbursements", status_code=status.HTTP_201_CREATED)
def create_reimbursement(payload: ReimbursementCreate, db: Session = Depends(get_db)) -> dict[str, str]:
    reimbursement = Reimbursement(**payload.model_dump())
    db.add(reimbursement); db.flush(); record_audit(db, "reimbursement.created", "Reimbursement", reimbursement.id); db.commit()
    return {"id": str(reimbursement.id)}


@router.post("/reimbursements/{reimbursement_id}/allocate")
def allocate_reimbursement_endpoint(reimbursement_id: UUID, payload: ReimbursementAllocationCreate, db: Session = Depends(get_db)) -> dict[str, str]:
    try:
        allocation = allocate_reimbursement(db, reimbursement_id, payload.expense_document_id, payload.amount)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return {"id": str(allocation.id), "out_of_pocket": str(out_of_pocket(db, payload.expense_document_id))}


@router.post("/expenses/{expense_id}/payment-evidence", status_code=status.HTTP_201_CREATED)
def create_payment_evidence(expense_id: UUID, payload: PaymentEvidenceCreate, db: Session = Depends(get_db)) -> dict[str, str]:
    if db.get(ExpenseDocument, expense_id) is None:
        raise HTTPException(status_code=404, detail="Expense document not found.")
    evidence = PaymentEvidence(expense_document_id=expense_id, **payload.model_dump())
    db.add(evidence); db.flush(); record_audit(db, "payment_evidence.created", "PaymentEvidence", evidence.id); db.commit()
    return {"id": str(evidence.id)}


@router.post("/tax/{tax_year}/expenses/{expense_id}/evaluate")
def evaluate_tax_expense(tax_year: int, expense_id: UUID, taxpayer_id: UUID, db: Session = Depends(get_db)) -> dict[str, str]:
    try:
        allocation = evaluate_expense(db, tax_year, expense_id, taxpayer_id)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return {"id": str(allocation.id), "eligible_amount": str(allocation.eligible_amount), "status": allocation.status}


@router.post("/tax/{tax_year}/precompiled/import", status_code=status.HTTP_201_CREATED)
async def import_precompiled_730(tax_year: int, file: UploadFile = File(...), db: Session = Depends(get_db)) -> dict[str, str]:
    """Import a local UTF-8 pre-filled 730 CSV; no authenticated scraping is used."""
    imported = import_csv(db, tax_year, file.filename or "precompiled.csv", await file.read())
    return {"id": str(imported.id)}


@router.post("/tax/{tax_year}/precompiled/reconcile")
def reconcile_precompiled_730(tax_year: int, db: Session = Depends(get_db)) -> dict[str, int]:
    return {"matched": reconcile(db, tax_year)}


@router.get("/tax/{tax_year}/reconciliation")
def precompiled_discrepancies(tax_year: int, db: Session = Depends(get_db)) -> list[dict[str, object]]:
    """Return only rows requiring a user discrepancy decision."""
    return [{"id": str(row.id), "amount": str(row.amount), "description": row.normalized_description, "status": row.status} for row in db.scalars(select(Precompiled730Row).where(Precompiled730Row.tax_year == tax_year, Precompiled730Row.status != "MATCHED"))]


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


@router.delete("/households/{household_id}", response_model=DeletionResponse)
def delete_household_endpoint(household_id: UUID, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)) -> DeletionResponse:
    """Remove one household, its members, and data associated with those members."""
    try:
        count = delete_household(db, settings.storage_root, household_id)
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return DeletionResponse(status="deleted", documents_deleted=count)


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
    event_title = refresh_legacy_event_title(db, event)
    db.commit()
    nodes = [GraphNode(id=str(event.id), type="medical_event", label=event_title, metadata={"confidence": event.confidence}, status=event.status.value)]
    edges: list[GraphEdge] = []
    for link in db.scalars(select(DocumentLink).where(DocumentLink.medical_event_id == event.id)):
        for document_id in (link.source_document_id, link.target_document_id):
            document = db.get(Document, document_id)
            if document and not any(node.id == str(document.id) for node in nodes):
                nodes.append(GraphNode(id=str(document.id), type="document", label=document.logical_name or document.original_filename, metadata={"document_type": document.document_type.value}, status=document.state.value))
        edges.append(GraphEdge(id=str(link.id), source=str(link.source_document_id), target=str(link.target_document_id), type=link.relation_type, confidence=link.score, evidence=link.evidence, conflicts=link.conflicts))
    return EventGraph(nodes=nodes, edges=edges)


@router.get("/medical-events", response_model=list[MedicalEventResponse])
def list_medical_events(db: Session = Depends(get_db)) -> list[MedicalEventResponse]:
    events = list(db.scalars(select(MedicalEvent).where(MedicalEvent.status != EventStatus.ARCHIVED).order_by(MedicalEvent.created_at.desc())))
    titles = {item.id: refresh_legacy_event_title(db, item) for item in events}
    db.commit()
    return [MedicalEventResponse(id=item.id, title=titles[item.id], status=item.status.value, confidence=item.confidence) for item in events]


@router.post("/medical-events/{event_id}/association", response_model=MedicalEventResponse)
def decide_medical_event_association(event_id: UUID, payload: AssociationDecision, db: Session = Depends(get_db)) -> MedicalEventResponse:
    """Record an operator decision on a proposed association and retain rejected pairs as feedback."""
    event = db.get(MedicalEvent, event_id)
    if event is None or event.status == EventStatus.ARCHIVED:
        raise HTTPException(status_code=404, detail="Active medical event not found.")
    if payload.action == "approve":
        event.status = EventStatus.CONFIRMED
        record_audit(db, "association.approved", "MedicalEvent", event.id)
    else:
        reason = (payload.reason or "").strip()
        if not reason:
            raise HTTPException(status_code=422, detail="A rejection reason is required.")
        for link in db.scalars(select(DocumentLink).where(DocumentLink.medical_event_id == event.id)):
            link.relation_type = "REJECTED_BY_OPERATOR"
            link.conflicts = [*link.conflicts, "operator_rejected"]
            link.evidence = [*link.evidence, f"operator_rejection_reason: {reason}"]
        event.status = EventStatus.ARCHIVED
        record_audit(db, "association.rejected", "MedicalEvent", event.id, {"reason": reason})
    db.commit()
    return MedicalEventResponse(id=event.id, title=event.title, status=event.status.value, confidence=event.confidence)


@router.post("/medical-events/rebuild-associations")
def rebuild_proposed_associations(db: Session = Depends(get_db), settings: Settings = Depends(get_settings)) -> dict[str, int]:
    """Discard only unreviewed proposals, then recompute links while preserving decisions and feedback."""
    proposed_ids = list(db.scalars(select(MedicalEvent.id).where(MedicalEvent.status == EventStatus.PROPOSED)))
    if proposed_ids:
        db.execute(delete(DocumentLink).where(DocumentLink.medical_event_id.in_(proposed_ids)))
        db.execute(delete(MedicalEvent).where(MedicalEvent.id.in_(proposed_ids)))
        db.flush()
    structured_documents = list(db.scalars(select(Document).where(Document.document_type.in_([DocumentType.PRESCRIPTION, DocumentType.INVOICE]))))
    for document in structured_documents:
        cluster_document(db, document, settings.auto_confirm_threshold, settings.suggest_threshold)
    record_audit(db, "association.rebuilt", "MedicalEvent", UUID(int=0), {"proposals_removed": len(proposed_ids)})
    db.commit()
    return {"proposals_removed": len(proposed_ids)}


@router.get("/medical-events/{event_id}/insurance-evaluation", response_model=InsuranceResponse)
def insurance_evaluation(event_id: UUID, db: Session = Depends(get_db)) -> InsuranceResponse:
    if db.get(MedicalEvent, event_id) is None:
        raise HTTPException(status_code=404, detail="Medical event not found.")
    result = evaluate_specialist_and_diagnostics(db, event_id)
    return InsuranceResponse(
        category=result.category,
        status=result.status,
        documentation_complete=result.documentation_complete,
        documented_amount=str(result.documented_amount),
        estimated_eligible_amount=str(result.estimated_eligible_amount),
        estimate_basis=result.estimate_basis,
        rules=result.rules,
        evidence=[item for item in result.evidence if item],
        missing_documents=result.missing_documents,
        warnings=result.warnings,
    )


@router.get("/medical-events/{event_id}/insurance-package")
def insurance_package(event_id: UUID, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)) -> FileResponse:
    """Export a local PDF candidate summary for mandatory human policy review."""
    if db.get(MedicalEvent, event_id) is None:
        raise HTTPException(status_code=404, detail="Medical event not found.")
    package = export_package(settings.storage_root / "exports", event_id, evaluate_specialist_and_diagnostics(db, event_id))
    return FileResponse(package, media_type="application/pdf", filename=package.name)


@router.get("/review-tasks", response_model=list[ReviewResponse])
def list_review_tasks(db: Session = Depends(get_db)) -> list[ReviewResponse]:
    """Return open reviews after resolving obsolete or temporally impossible links."""
    document_ids = {str(document_id) for document_id in db.scalars(select(Document.id))}
    obsolete_reviews: list[tuple[ReviewTask, str]] = []
    for task in db.scalars(select(ReviewTask).where(ReviewTask.status == "OPEN", ReviewTask.entity_type == "Document")):
        candidate_id = task.context.get("candidate_document_id")
        deleted_source = str(task.entity_id) not in document_ids
        deleted_candidate = task.type == ReviewType.LINK_AMBIGUOUS and (
            not isinstance(candidate_id, str) or candidate_id not in document_ids
        )
        if deleted_source or deleted_candidate:
            obsolete_reviews.append((task, "documents_removed"))
            continue
        if task.type != ReviewType.LINK_AMBIGUOUS or not isinstance(candidate_id, str):
            continue
        source_document = db.get(Document, task.entity_id)
        candidate_document = db.get(Document, UUID(candidate_id))
        prescription_document, invoice_document = (
            (source_document, candidate_document)
            if source_document and source_document.document_type == DocumentType.PRESCRIPTION
            else (candidate_document, source_document)
        )
        if not prescription_document or not invoice_document:
            continue
        prescription = db.scalar(select(Prescription).where(Prescription.document_id == prescription_document.id))
        expense = db.scalar(select(ExpenseDocument).where(ExpenseDocument.document_id == invoice_document.id))
        if prescription and expense and prescription.prescription_date and expense.invoice_date:
            days = (expense.invoice_date - prescription.prescription_date).days
            if days < 0:
                obsolete_reviews.append((task, "invoice_before_prescription"))
            elif days > 30:
                obsolete_reviews.append((task, "invoice_outside_link_window"))
    for task, reason in obsolete_reviews:
        task.status = "RESOLVED"
        task.resolution = {"action": reason}
        task.resolved_at = datetime.now(UTC)
        record_audit(db, "review.resolved", "ReviewTask", task.id, {"reason": reason})
    if obsolete_reviews:
        db.commit()
    return [
        ReviewResponse(id=item.id, type=item.type.value, entity_type=item.entity_type, entity_id=item.entity_id, status=item.status, priority=item.priority, context=item.context)
        for item in db.scalars(select(ReviewTask).where(ReviewTask.status == "OPEN").order_by(ReviewTask.priority.desc()))
    ]


@router.post("/review-tasks/{task_id}/resolve", response_model=ReviewResponse)
def resolve_review_task(task_id: UUID, payload: ReviewResolution, db: Session = Depends(get_db)) -> ReviewResponse:
    task = db.get(ReviewTask, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Review task not found.")
    if payload.resolution.get("action") == "confirmed_related" and task.type == ReviewType.LINK_AMBIGUOUS:
        candidate_id = task.context.get("candidate_document_id")
        if not isinstance(candidate_id, str):
            raise HTTPException(status_code=422, detail="Link review has no candidate document.")
        source_document = db.get(Document, task.entity_id)
        candidate_document = db.get(Document, UUID(candidate_id))
        if source_document is None or candidate_document is None:
            raise HTTPException(status_code=422, detail="A reviewed document is no longer available.")
        prescription_document, invoice_document = (
            (source_document, candidate_document)
            if source_document.document_type == DocumentType.PRESCRIPTION
            else (candidate_document, source_document)
        )
        if prescription_document.document_type != DocumentType.PRESCRIPTION or invoice_document.document_type != DocumentType.INVOICE:
            raise HTTPException(status_code=422, detail="A link review must pair a prescription with an invoice.")
        prescription = db.scalar(select(Prescription).where(Prescription.document_id == prescription_document.id))
        expense = db.scalar(select(ExpenseDocument).where(ExpenseDocument.document_id == invoice_document.id))
        if prescription and expense and prescription.prescription_date and expense.invoice_date:
            days = (expense.invoice_date - prescription.prescription_date).days
            if days < 0:
                raise HTTPException(status_code=422, detail="An invoice dated before its prescription cannot be linked.")
            if days > 30:
                raise HTTPException(status_code=422, detail="An invoice outside the 30-day prescription window cannot be linked.")
        if db.scalar(select(DocumentLink).where(DocumentLink.source_document_id == prescription_document.id, DocumentLink.target_document_id == invoice_document.id)) is None:
            evidence = task.context.get("evidence")
            conflicts = task.context.get("conflicts")
            score = task.context.get("score")
            evidence_values = [item for item in evidence if isinstance(item, str)] if isinstance(evidence, list) else []
            conflict_values = [item for item in conflicts if isinstance(item, str)] if isinstance(conflicts, list) else []
            confidence = float(score) if isinstance(score, int | float) else 0.0
            event = MedicalEvent(
                household_member_id=(prescription.patient_id if prescription else None) or (expense.patient_id if expense else None),
                title=medical_event_title(prescription, expense) if prescription and expense else "Prestazione sanitaria confermata",
                status=EventStatus.CONFIRMED,
                confidence=confidence,
            )
            db.add(event)
            db.flush()
            db.add(DocumentLink(
                source_document_id=prescription_document.id,
                target_document_id=invoice_document.id,
                medical_event_id=event.id,
                relation_type="MANUALLY_CONFIRMED",
                score=confidence,
                evidence=[*evidence_values, "manual_review_confirmed"],
                conflicts=conflict_values,
            ))
    task.status = "RESOLVED"
    task.resolution = payload.resolution
    task.resolved_at = datetime.now(UTC)
    record_audit(db, "review.resolved", "ReviewTask", task.id)
    db.commit()
    return ReviewResponse(id=task.id, type=task.type.value, entity_type=task.entity_type, entity_id=task.entity_id, status=task.status, priority=task.priority, context=task.context)


@router.post("/review-tasks/{task_id}/retry", response_model=ReviewResponse)
async def retry_document_review_task(task_id: UUID, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)) -> ReviewResponse:
    """Requeue a document whose local extraction or classification needs another attempt."""
    task = db.get(ReviewTask, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Review task not found.")
    if task.type != ReviewType.DOCUMENT_TYPE_UNCERTAIN or task.entity_type != "Document":
        raise HTTPException(status_code=422, detail="Only document-classification reviews can be retried.")
    document = db.get(Document, task.entity_id)
    if document is None:
        raise HTTPException(status_code=404, detail="The reviewed document is no longer available.")
    try:
        redis = await create_pool(RedisSettings.from_dsn(settings.redis_url))
    except OSError as error:
        raise HTTPException(status_code=503, detail="The processing queue is unavailable.") from error
    try:
        db.execute(delete(DocumentPage).where(DocumentPage.document_id == document.id))
        for open_task in db.scalars(
            select(ReviewTask).where(
                ReviewTask.status == "OPEN",
                ReviewTask.type == ReviewType.DOCUMENT_TYPE_UNCERTAIN,
                ReviewTask.entity_type == "Document",
                ReviewTask.entity_id == document.id,
            )
        ):
            open_task.status = "RESOLVED"
            open_task.resolution = {"action": "retry_requested"}
            open_task.resolved_at = datetime.now(UTC)
            record_audit(db, "review.resolved", "ReviewTask", open_task.id, {"action": "retry_requested"})
        document.state = DocumentState.STORED
        db.commit()
        await redis.enqueue_job("process_document", str(document.id))
    except OSError as error:
        db.rollback()
        raise HTTPException(status_code=503, detail="The processing queue is unavailable.") from error
    finally:
        await redis.aclose()
    return ReviewResponse(id=task.id, type=task.type.value, entity_type=task.entity_type, entity_id=task.entity_id, status=task.status, priority=task.priority, context=task.context)


@router.post("/review-tasks/{task_id}/complete-manually", response_model=ReviewResponse)
def complete_document_review_manually(task_id: UUID, payload: ManualDocumentCompletion, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)) -> ReviewResponse:
    """Persist operator-supplied structured data for a document that local extraction could not classify."""
    task = db.get(ReviewTask, task_id)
    if task is None or task.status != "OPEN":
        raise HTTPException(status_code=404, detail="Open review task not found.")
    if task.type != ReviewType.DOCUMENT_TYPE_UNCERTAIN or task.entity_type != "Document":
        raise HTTPException(status_code=422, detail="Only document-classification reviews can be completed manually.")
    if payload.document_type == "INVOICE" and payload.total_amount is None:
        raise HTTPException(status_code=422, detail="A total amount is required for a manually completed invoice.")
    document = db.get(Document, task.entity_id)
    if document is None:
        raise HTTPException(status_code=404, detail="The reviewed document is no longer available.")

    patient = resolve_patient(db, None, payload.patient_name)
    evidence = {"value": payload.patient_name, "source_text": "manual operator entry", "confidence": 1.0}
    service = {"value": payload.service_description, "source_text": "manual operator entry", "confidence": 1.0}
    document.document_type = DocumentType(payload.document_type)
    document.document_date = payload.document_date
    document.patient_id = patient.member_id
    document.state = DocumentState.COMPLETE
    extension = Path(document.original_filename).suffix.lower() or ".bin"
    document.logical_name = f"{payload.document_date.isoformat()}_{payload.document_type.lower()}_{document.sha256[:8]}{extension}"

    if document.document_type == DocumentType.PRESCRIPTION:
        extraction = {"document_date": payload.document_date.isoformat(), "patient": evidence, "requested_services": [service], "diagnosis_evidence": []}
        db.add(Prescription(document_id=document.id, patient_id=patient.member_id, prescription_date=payload.document_date, provider=payload.provider_name, extraction=extraction))
    elif document.document_type == DocumentType.INVOICE:
        extraction = {"invoice_date": payload.document_date.isoformat(), "patient_name": evidence, "provider_name": {"value": payload.provider_name, "source_text": "manual operator entry", "confidence": 1.0} if payload.provider_name else None, "services": [{"description": service, "amount": str(payload.total_amount)}], "total_amount": str(payload.total_amount)}
        db.add(ExpenseDocument(document_id=document.id, patient_id=patient.member_id, invoice_date=payload.document_date, provider_name=payload.provider_name, total_amount=payload.total_amount, extraction=extraction))
    else:
        extraction = {"report_date": payload.document_date.isoformat(), "patient": evidence, "requested_visits": [{"kind": "OTHER", "evidence": service, "scheduled_date": payload.document_date.isoformat()}]}
        db.add(MedicalReport(document_id=document.id, patient_id=patient.member_id, report_date=payload.document_date, provider=payload.provider_name, extraction=extraction))

    db.flush()
    if patient.conflict:
        db.add(ReviewTask(type=ReviewType.PATIENT_CONFLICT, entity_type="Document", entity_id=document.id, context={"resolution_evidence": patient.evidence, "source": "manual_completion"}))
    cluster_document(db, document, settings.auto_confirm_threshold, settings.suggest_threshold)
    task.status = "RESOLVED"
    task.resolution = {"action": "completed_manually", "document_type": payload.document_type}
    task.resolved_at = datetime.now(UTC)
    record_audit(db, "review.completed_manually", "ReviewTask", task.id, {"document_type": payload.document_type})
    db.commit()
    return ReviewResponse(id=task.id, type=task.type.value, entity_type=task.entity_type, entity_id=task.entity_id, status=task.status, priority=task.priority, context=task.context)
