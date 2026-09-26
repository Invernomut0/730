"""Create proposed medical events from safe prescription/invoice links."""

from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.adapters.lmstudio import LLMProvider
from app.models.entities import Document, DocumentLink, EventStatus, ExpenseDocument, MedicalEvent, Prescription, ReviewTask, ReviewType
from app.services.linking import is_patient_date_review_candidate, score_prescription_invoice


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


def _evidence_values(extraction: dict[str, object], key: str) -> list[str]:
    """Read scalar extracted prescription/invoice item evidence without mutation."""
    values = extraction.get(key, [])
    if not isinstance(values, list):
        return []
    return [value["value"] for value in values if isinstance(value, dict) and isinstance(value.get("value"), str)]


def _link_candidate(source: Prescription, target: ExpenseDocument):
    """Build one safety-first candidate from services and itemized clinical evidence."""
    return score_prescription_invoice(
        source.patient_id,
        target.patient_id,
        source.prescription_date,
        target.invoice_date,
        _services(source.extraction, "requested_services"),
        _services(target.extraction, "services"),
        _evidence_values(source.extraction, "prescribed_drugs"),
        _evidence_values(source.extraction, "requested_lab_tests"),
        _evidence_values(target.extraction, "billed_drugs"),
        _evidence_values(target.extraction, "billed_lab_tests"),
    )


def medical_event_title(prescription: Prescription, invoice: ExpenseDocument) -> str:
    """Create a concise, human-readable event title from extracted clinical services."""
    services = _services(prescription.extraction, "requested_services") or _services(invoice.extraction, "services")
    return services[0][:220] if services else "Prestazione sanitaria collegata"


def refresh_legacy_event_title(db: Session, event: MedicalEvent) -> str:
    """Replace historic generic event titles with a service-derived title when possible."""
    if event.title not in {"Linked medical care", "Manually confirmed medical care"}:
        return event.title
    link = db.scalar(select(DocumentLink).where(DocumentLink.medical_event_id == event.id))
    if link is None:
        return event.title
    prescription = db.scalar(select(Prescription).where(Prescription.document_id == link.source_document_id))
    expense = db.scalar(select(ExpenseDocument).where(ExpenseDocument.document_id == link.target_document_id))
    if prescription is None or expense is None:
        return event.title
    event.title = medical_event_title(prescription, expense)
    return event.title


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
        candidate = _link_candidate(source, target)
        if candidate.conflicts:
            continue
        if candidate.score >= auto_confirm_threshold:
            event = MedicalEvent(household_member_id=source.patient_id, title=medical_event_title(source, target), start_date=source.prescription_date, end_date=target.invoice_date, confidence=candidate.score)
            db.add(event)
            db.flush()
            db.add(DocumentLink(source_document_id=source.document_id, target_document_id=target.document_id, medical_event_id=event.id, relation_type="RELATED_TO", score=candidate.score, evidence=candidate.evidence, conflicts=candidate.conflicts))
        elif candidate.score >= suggest_threshold:
            db.add(ReviewTask(type=ReviewType.LINK_AMBIGUOUS, entity_type="Document", entity_id=document.id, context={"candidate_document_id": str(target.document_id if prescription else source.document_id), "score": candidate.score, "evidence": candidate.evidence, "conflicts": candidate.conflicts}))
        elif is_patient_date_review_candidate(candidate):
            event = MedicalEvent(
                household_member_id=source.patient_id,
                title=medical_event_title(source, target),
                start_date=source.prescription_date,
                end_date=target.invoice_date,
                status=EventStatus.PROPOSED,
                confidence=candidate.score,
            )
            db.add(event)
            db.flush()
            db.add(DocumentLink(
                source_document_id=source.document_id,
                target_document_id=target.document_id,
                medical_event_id=event.id,
                relation_type="PATIENT_DATE_REVIEW",
                score=candidate.score,
                evidence=[*candidate.evidence, "patient_date_match_requires_review"],
                conflicts=["invoice_service_not_matched"],
            ))


async def cluster_document_with_relation_model(
    db: Session,
    document: Document,
    provider: LLMProvider,
    suggest_threshold: float,
) -> None:
    """Ask the designated large local model only about candidate pairs that pass hard safety gates."""
    prescription = db.scalar(select(Prescription).where(Prescription.document_id == document.id))
    expense = db.scalar(select(ExpenseDocument).where(ExpenseDocument.document_id == document.id))
    if prescription:
        pairs = [(prescription, item) for item in db.scalars(select(ExpenseDocument))]
    elif expense:
        pairs = [(item, expense) for item in db.scalars(select(Prescription))]
    else:
        return

    schema = {
        "type": "object",
        "properties": {
            "related": {"type": "boolean"},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "reason": {"type": "string", "maxLength": 500},
        },
        "required": ["related", "confidence", "reason"],
        "additionalProperties": False,
    }
    for source, target in pairs:
        if db.scalar(select(DocumentLink).where(DocumentLink.source_document_id == source.document_id, DocumentLink.target_document_id == target.document_id)):
            continue
        candidate = _link_candidate(source, target)
        if candidate.conflicts or not candidate.evidence:
            continue
        prompt = (
            "Decide whether a prescription and an invoice describe the same health service. "
            "The patient and chronology have already passed deterministic safety checks. "
            "Return related=false when the services are not the same or evidence is insufficient.\n"
            f"Prescription date: {source.prescription_date}; requested services: {json.dumps(_services(source.extraction, 'requested_services'), ensure_ascii=False)}; prescribed drugs: {json.dumps(_evidence_values(source.extraction, 'prescribed_drugs'), ensure_ascii=False)}; requested lab tests: {json.dumps(_evidence_values(source.extraction, 'requested_lab_tests'), ensure_ascii=False)}\n"
            f"Invoice date: {target.invoice_date}; billed services: {json.dumps(_services(target.extraction, 'services'), ensure_ascii=False)}; billed drugs: {json.dumps(_evidence_values(target.extraction, 'billed_drugs'), ensure_ascii=False)}; billed lab tests: {json.dumps(_evidence_values(target.extraction, 'billed_lab_tests'), ensure_ascii=False)}"
        )
        decision = await provider.structured_completion(prompt, schema)
        related = decision.get("related") is True
        confidence = decision.get("confidence")
        reason = decision.get("reason")
        if not related or not isinstance(confidence, (int, float)) or isinstance(confidence, bool) or not isinstance(reason, str):
            continue
        score = min(1.0, candidate.score + 0.5 * float(confidence))
        if score < suggest_threshold:
            continue
        event = MedicalEvent(
            household_member_id=source.patient_id,
            title=medical_event_title(source, target),
            start_date=source.prescription_date,
            end_date=target.invoice_date,
            confidence=score,
        )
        db.add(event)
        db.flush()
        db.add(DocumentLink(
            source_document_id=source.document_id,
            target_document_id=target.document_id,
            medical_event_id=event.id,
            relation_type="LLM_RELATED_TO",
            score=score,
            evidence=[*candidate.evidence, "large_model_relation_match", f"large_model_reason: {reason[:500]}"],
            conflicts=candidate.conflicts,
        ))
