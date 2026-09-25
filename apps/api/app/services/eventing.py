"""Create proposed medical events from safe prescription/invoice links."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import Document, DocumentLink, ExpenseDocument, MedicalEvent, Prescription, ReviewTask, ReviewType
from app.services.linking import score_prescription_invoice


def _services(extraction: dict[str, object], key: str) -> list[str]:
    values = extraction.get(key, [])
    if not isinstance(values, list):
        return []
    result: list[str] = []
    for value in values:
        if isinstance(value, dict):
            candidate = value.get("value") or (value.get("description", {}) if isinstance(value.get("description"), dict) else {}).get("value")
            if isinstance(candidate, str):
                result.append(candidate)
    return result


def cluster_document(db: Session, document: Document, auto_confirm_threshold: float, suggest_threshold: float) -> None:
    """Link one newly structured document to compatible opposite-type documents exactly once."""
    prescription = db.scalar(select(Prescription).where(Prescription.document_id == document.id))
    expense = db.scalar(select(ExpenseDocument).where(ExpenseDocument.document_id == document.id))
    if prescription:
        pairs = [(prescription, item) for item in db.scalars(select(ExpenseDocument))]
    elif expense:
        pairs = [(item, expense) for item in db.scalars(select(Prescription))]
    else:
        return
    for source, target in pairs:
        if source.document_id == target.document_id:
            continue
        exists = db.scalar(select(DocumentLink).where(DocumentLink.source_document_id == source.document_id, DocumentLink.target_document_id == target.document_id))
        if exists:
            continue
        candidate = score_prescription_invoice(source.patient_id, target.patient_id, source.prescription_date, target.invoice_date, _services(source.extraction, "requested_services"), _services(target.extraction, "services"))
        if candidate.score >= auto_confirm_threshold and not candidate.conflicts:
            event = MedicalEvent(household_member_id=source.patient_id, title="Linked medical care", start_date=source.prescription_date, end_date=target.invoice_date, confidence=candidate.score)
            db.add(event)
            db.flush()
            db.add(DocumentLink(source_document_id=source.document_id, target_document_id=target.document_id, medical_event_id=event.id, relation_type="RELATED_TO", score=candidate.score, evidence=candidate.evidence, conflicts=candidate.conflicts))
        elif candidate.score >= suggest_threshold or candidate.conflicts:
            db.add(ReviewTask(type=ReviewType.LINK_AMBIGUOUS, entity_type="Document", entity_id=document.id, context={"candidate_document_id": str(target.document_id if prescription else source.document_id), "score": candidate.score, "evidence": candidate.evidence, "conflicts": candidate.conflicts}))
