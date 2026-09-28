"""Create medical-event proposals through the configured primary relation LLM."""

from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.adapters.lmstudio import LLMProvider
from app.models.entities import AssociationFeedback, Document, DocumentLink, EventStatus, ExpenseDocument, MedicalEvent, Prescription


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


def medical_event_title(prescription: Prescription, invoice: ExpenseDocument) -> str:
    """Create a concise, human-readable event title from extracted clinical services."""
    services = (
        _services(prescription.extraction, "requested_services")
        or _evidence_values(prescription.extraction, "requested_lab_tests")
        or _evidence_values(prescription.extraction, "prescribed_drugs")
        or _services(invoice.extraction, "services")
    )
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


async def cluster_document_with_relation_model(
    db: Session,
    document: Document,
    provider: LLMProvider,
) -> None:
    """Ask the primary local model to decide every prescription/invoice pair."""
    prescription = db.scalar(select(Prescription).where(Prescription.document_id == document.id))
    expense = db.scalar(select(ExpenseDocument).where(ExpenseDocument.document_id == document.id))
    if prescription:
        candidates = select(ExpenseDocument)
        if prescription.patient_id:
            candidates = candidates.where(ExpenseDocument.patient_id == prescription.patient_id)
        pairs = [(prescription, item) for item in db.scalars(candidates)]
    elif expense:
        candidates = select(Prescription)
        if expense.patient_id:
            candidates = candidates.where(Prescription.patient_id == expense.patient_id)
        pairs = [(item, expense) for item in db.scalars(candidates)]
    else:
        return

    schema = {
        "type": "object",
        "properties": {
            "decision": {"type": "string", "enum": ["RELATED", "NOT_RELATED", "UNCERTAIN"]},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "event_title": {"type": "string", "maxLength": 255},
            "reason": {"type": "string", "maxLength": 1000},
            "evidence": {"type": "array", "items": {"type": "string", "maxLength": 300}, "maxItems": 8},
        },
        "required": ["decision", "confidence", "event_title", "reason", "evidence"],
        "additionalProperties": False,
    }
    all_feedback = list(db.scalars(select(AssociationFeedback).order_by(AssociationFeedback.created_at.desc())))
    documents = {item.id: item for item in db.scalars(select(Document))}
    for source, target in pairs:
        if db.scalar(select(DocumentLink).where(DocumentLink.source_document_id == source.document_id, DocumentLink.target_document_id == target.document_id)):
            continue
        pair_feedback = next(
            (
                feedback for feedback in all_feedback
                if feedback.source_document_id == source.document_id and feedback.target_document_id == target.document_id
            ),
            None,
        )
        if pair_feedback and pair_feedback.decision == "REJECTED":
            continue
        if pair_feedback and pair_feedback.decision == "APPROVED":
            _create_event_and_link(
                db, source, target, "USER_CONFIRMED", EventStatus.CONFIRMED, 1.0,
                ["operator_confirmed_association"], [], medical_event_title(source, target),
            )
            continue
        feedback_examples = _feedback_examples(all_feedback, documents, source.patient_id)
        prompt = (
            "You are the primary clinical relationship arbiter for local health documents. Decide whether the "
            "prescription and invoice belong to the same concrete episode of care. Compare clinical intent, "
            "requested tests or drugs, billed services, provider, patient evidence, and chronology together. "
            "Dates, the same patient, generic wording, or a shared provider are never sufficient on their own. "
            "Do not relate a laboratory-test prescription to an infusion, medicine administration, or unrelated "
            "service unless document evidence explicitly connects them. Return RELATED only for a supported "
            "clinical relationship; use NOT_RELATED when evidence contradicts it and UNCERTAIN when it is incomplete.\n"
            f"Prescription: {json.dumps(_relation_context(source, 'prescription'), ensure_ascii=False)}\n"
            f"Invoice: {json.dumps(_relation_context(target, 'invoice'), ensure_ascii=False)}\n"
            f"Previous operator decisions for this patient: {json.dumps(feedback_examples, ensure_ascii=False)}"
        )
        decision = await provider.structured_completion(prompt, schema)
        relation_decision = decision.get("decision")
        confidence = decision.get("confidence")
        reason = decision.get("reason")
        title = decision.get("event_title")
        evidence = decision.get("evidence")
        if (
            relation_decision != "RELATED" or not isinstance(confidence, (int, float))
            or isinstance(confidence, bool) or not isinstance(reason, str) or not isinstance(title, str)
            or not title.strip() or not isinstance(evidence, list) or not all(isinstance(item, str) for item in evidence)
        ):
            continue
        _create_event_and_link(
            db, source, target, "LLM_PROPOSED", EventStatus.PROPOSED, min(1.0, max(0.0, float(confidence))),
            [*evidence[:8], f"model_reason: {reason[:1000]}"], [], title.strip()[:255],
        )


def _relation_context(document: Prescription | ExpenseDocument, kind: str) -> dict[str, object]:
    """Give the model complete extracted facts, not rule-derived scores or labels."""
    if kind == "prescription":
        return {
            "patient_id": str(document.patient_id) if document.patient_id else None,
            "date": str(document.prescription_date) if document.prescription_date else None,
            "provider": document.provider,
            "requested_services": _services(document.extraction, "requested_services"),
            "prescribed_drugs": _evidence_values(document.extraction, "prescribed_drugs"),
            "requested_lab_tests": _evidence_values(document.extraction, "requested_lab_tests"),
            "extraction": document.extraction,
        }
    return {
        "patient_id": str(document.patient_id) if document.patient_id else None,
        "date": str(document.invoice_date) if document.invoice_date else None,
        "provider": document.provider_name,
        "services": _services(document.extraction, "services"),
        "billed_drugs": _evidence_values(document.extraction, "billed_drugs"),
        "billed_lab_tests": _evidence_values(document.extraction, "billed_lab_tests"),
        "extraction": document.extraction,
    }


def _feedback_examples(
    feedback: list[AssociationFeedback], documents: dict[object, Document], patient_id: object | None
) -> list[dict[str, object]]:
    """Provide recent same-patient corrections as local few-shot guidance to the LLM."""
    examples: list[dict[str, object]] = []
    for item in feedback:
        source = documents.get(item.source_document_id)
        target = documents.get(item.target_document_id)
        if not source or not target or patient_id is None or source.patient_id != patient_id:
            continue
        examples.append({
            "decision": item.decision,
            "reason": item.reason,
            "prescription": source.logical_name or source.original_filename,
            "invoice": target.logical_name or target.original_filename,
        })
        if len(examples) == 12:
            break
    return examples


def _create_event_and_link(
    db: Session,
    source: Prescription,
    target: ExpenseDocument,
    relation_type: str,
    status: EventStatus,
    confidence: float,
    evidence: list[str],
    conflicts: list[str],
    title: str,
) -> None:
    event = MedicalEvent(
        household_member_id=source.patient_id or target.patient_id,
        title=title,
        start_date=source.prescription_date,
        end_date=target.invoice_date,
        status=status,
        confidence=confidence,
    )
    db.add(event)
    db.flush()
    db.add(DocumentLink(
        source_document_id=source.document_id,
        target_document_id=target.document_id,
        medical_event_id=event.id,
        relation_type=relation_type,
        score=confidence,
        evidence=evidence,
        conflicts=conflicts,
    ))
