"""Create medical-event proposals through the configured primary relation LLM."""

from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.adapters.lmstudio import LLMProvider
from app.models.entities import AssociationFeedback, Document, DocumentLink, EventStatus, ExpenseDocument, MedicalEvent, Prescription

LEGACY_RULE_REJECTION_REASON = "Proposta legacy basata su regole fisse: relazione dichiarata errata dall'operatore."


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
    screening_provider: LLMProvider | None = None,
) -> None:
    """Use a small semantic selector, then ask the primary model only about uncertainty."""
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
            "decisions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "candidate_index": {"type": "integer", "minimum": 0},
                        "decision": {"type": "string", "enum": ["RELATED", "NOT_RELATED", "UNCERTAIN"]},
                        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                        "event_title": {"type": "string", "maxLength": 255},
                        "reason": {"type": "string", "maxLength": 1000},
                        "evidence": {"type": "array", "items": {"type": "string", "maxLength": 300}, "maxItems": 8},
                    },
                    "required": ["candidate_index", "decision", "confidence", "event_title", "reason", "evidence"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["decisions"],
        "additionalProperties": False,
    }
    all_feedback = list(db.scalars(select(AssociationFeedback).order_by(AssociationFeedback.created_at.desc())))
    documents = {item.id: item for item in db.scalars(select(Document))}
    model_candidates: list[tuple[Prescription, ExpenseDocument, AssociationFeedback | None]] = []
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
        if pair_feedback and pair_feedback.decision == "REJECTED" and not _is_legacy_rule_rejection(pair_feedback):
            continue
        if pair_feedback and pair_feedback.decision == "APPROVED":
            _create_event_and_link(
                db, source, target, "USER_CONFIRMED", EventStatus.CONFIRMED, 1.0,
                ["operator_confirmed_association"], [], medical_event_title(source, target),
            )
            continue
        model_candidates.append((source, target, pair_feedback))
    if not model_candidates:
        return

    patient_id = model_candidates[0][0].patient_id or model_candidates[0][1].patient_id
    feedback_examples = _feedback_examples(all_feedback, documents, patient_id)
    candidate_context = [
        {
            "candidate_index": index,
            "prescription": _relation_context(source, "prescription", include_extraction=True),
            "invoice": _relation_context(target, "invoice", include_extraction=True),
            "legacy_rule_rejection": bool(feedback and _is_legacy_rule_rejection(feedback)),
        }
        for index, (source, target, feedback) in enumerate(model_candidates)
    ]
    large_candidates = model_candidates
    if screening_provider is not None:
        screening_prompt = (
            "You are a fast clinical association selector. Review every candidate prescription/invoice pair "
            "independently from the complete structured extraction. Return RELATED only when the clinical episode "
            "is clearly supported, NOT_RELATED when it is clearly unrelated, and UNCERTAIN when a senior clinical "
            "model must evaluate the nuance. Never use date, patient, generic service wording, or provider alone "
            "as sufficient evidence. Legacy rule rejections are context, not a veto.\n"
            f"Candidate pairs: {json.dumps(candidate_context, ensure_ascii=False)}\n"
            f"Previous operator decisions for this patient: {json.dumps(feedback_examples, ensure_ascii=False)}"
        )
        screening_response = await screening_provider.structured_completion(screening_prompt, schema)
        screening_decisions = screening_response.get("decisions")
        if isinstance(screening_decisions, list):
            large_candidates = []
            screened_indexes: set[int] = set()
            for decision in screening_decisions:
                parsed = _parse_relation_decision(decision, len(model_candidates), screened_indexes)
                if parsed is None:
                    continue
                candidate_index, relation_decision, confidence, reason, title, evidence = parsed
                screened_indexes.add(candidate_index)
                source, target, _feedback = model_candidates[candidate_index]
                if relation_decision == "RELATED":
                    _create_event_and_link(
                        db, source, target, "SMALL_LLM_PROPOSED", EventStatus.PROPOSED,
                        confidence, [*evidence, f"small_model_reason: {reason}"], [], title,
                    )
                elif relation_decision == "UNCERTAIN":
                    large_candidates.append((source, target, _feedback))
            large_candidates.extend(
                candidate for index, candidate in enumerate(model_candidates) if index not in screened_indexes
            )
    if not large_candidates:
        return

    large_context = [
        {
            "candidate_index": index,
            "prescription": _relation_context(source, "prescription"),
            "invoice": _relation_context(target, "invoice"),
        }
        for index, (source, target, _feedback) in enumerate(large_candidates)
    ]
    prompt = (
        "You are the primary clinical relationship arbiter for local health documents. Decide every listed "
        "prescription/invoice pair independently and return one decision for every candidate_index. Compare "
        "clinical intent, requested tests or drugs, billed services, provider, patient evidence, and chronology "
        "together. Dates, the same patient, generic wording, or a shared provider are never sufficient on their own. "
        "Do not relate a laboratory-test prescription to an infusion, medicine administration, or unrelated service "
        "unless document evidence explicitly connects them. Return RELATED only for a supported clinical relationship; "
        "use NOT_RELATED when evidence contradicts it and UNCERTAIN when it is incomplete. A legacy rule rejection "
        "is weak historical context, not a veto: reassess it from the clinical facts.\n"
        f"Candidate pairs: {json.dumps(large_context, ensure_ascii=False)}\n"
        f"Previous operator decisions for this patient: {json.dumps(feedback_examples, ensure_ascii=False)}"
    )
    response = await provider.structured_completion(prompt, schema)
    decisions = response.get("decisions")
    if not isinstance(decisions, list):
        return
    decided_indexes: set[int] = set()
    for decision in decisions:
        parsed = _parse_relation_decision(decision, len(large_candidates), decided_indexes)
        if parsed is None:
            continue
        candidate_index, relation_decision, confidence, reason, title, evidence = parsed
        decided_indexes.add(candidate_index)
        if relation_decision != "RELATED":
            continue
        source, target, _feedback = large_candidates[candidate_index]
        _create_event_and_link(
            db, source, target, "LLM_PROPOSED", EventStatus.PROPOSED,
            confidence, [*evidence, f"model_reason: {reason}"], [], title,
        )


async def rebuild_relationships_with_model_routing(
    db: Session,
    primary_provider: LLMProvider,
    screening_provider: LLMProvider | None,
) -> None:
    """Screen each patient's full document inventory once, escalating only uncertainty."""
    prescriptions = list(db.scalars(select(Prescription)))
    invoices = list(db.scalars(select(ExpenseDocument)))
    feedback = list(db.scalars(select(AssociationFeedback).order_by(AssociationFeedback.created_at.desc())))
    documents = {item.id: item for item in db.scalars(select(Document))}
    by_patient: dict[object, tuple[list[Prescription], list[ExpenseDocument]]] = {}
    for prescription in prescriptions:
        if prescription.patient_id is not None:
            by_patient.setdefault(prescription.patient_id, ([], []))[0].append(prescription)
    for invoice in invoices:
        if invoice.patient_id is not None:
            by_patient.setdefault(invoice.patient_id, ([], []))[1].append(invoice)

    for patient_id, (patient_prescriptions, patient_invoices) in by_patient.items():
        if not patient_prescriptions or not patient_invoices:
            continue
        eligible: dict[tuple[str, str], tuple[Prescription, ExpenseDocument]] = {}
        for source in patient_prescriptions:
            for target in patient_invoices:
                pair_feedback = next((
                    item for item in feedback
                    if item.source_document_id == source.document_id and item.target_document_id == target.document_id
                ), None)
                if pair_feedback and pair_feedback.decision == "REJECTED" and not _is_legacy_rule_rejection(pair_feedback):
                    continue
                if pair_feedback and pair_feedback.decision == "APPROVED":
                    _create_event_and_link(
                        db, source, target, "USER_CONFIRMED", EventStatus.CONFIRMED, 1.0,
                        ["operator_confirmed_association"], [], medical_event_title(source, target),
                    )
                    continue
                eligible[(str(source.document_id), str(target.document_id))] = (source, target)
        if not eligible:
            continue

        selector = screening_provider or primary_provider
        selector_schema = _inventory_schema()
        inventory_prompt = (
            "You are a fast clinical association selector. Consider each possible prescription/invoice pair for one "
            "patient from the complete structured document inventories. Return only pairs that are RELATED or "
            "UNCERTAIN; omit clearly unrelated pairs. Never infer a relation from dates, patient, generic wording, "
            "or provider alone. Legacy rule rejections are not vetoes.\n"
            f"Prescriptions: {json.dumps([{'document_id': str(item.document_id), 'data': _relation_context(item, 'prescription', include_extraction=True)} for item in patient_prescriptions], ensure_ascii=False)}\n"
            f"Invoices: {json.dumps([{'document_id': str(item.document_id), 'data': _relation_context(item, 'invoice', include_extraction=True)} for item in patient_invoices], ensure_ascii=False)}\n"
            f"Previous operator decisions: {json.dumps(_feedback_examples(feedback, documents, patient_id), ensure_ascii=False)}"
        )
        selection = await selector.structured_completion(inventory_prompt, selector_schema)
        matches = selection.get("matches")
        if not isinstance(matches, list):
            continue
        uncertain: list[tuple[Prescription, ExpenseDocument]] = []
        selected_keys: set[tuple[str, str]] = set()
        for match in matches:
            parsed = _parse_inventory_match(match, eligible, selected_keys)
            if parsed is None:
                continue
            source, target, decision, confidence, reason, title, evidence = parsed
            selected_keys.add((str(source.document_id), str(target.document_id)))
            if decision == "RELATED":
                _create_event_and_link(
                    db, source, target, "SMALL_LLM_PROPOSED", EventStatus.PROPOSED,
                    confidence, [*evidence, f"small_model_reason: {reason}"], [], title,
                )
            else:
                uncertain.append((source, target))
        if uncertain and screening_provider is not None:
            await _resolve_uncertain_pairs_with_primary(db, uncertain, feedback, documents, patient_id, primary_provider)


async def _resolve_uncertain_pairs_with_primary(
    db: Session,
    pairs: list[tuple[Prescription, ExpenseDocument]],
    feedback: list[AssociationFeedback],
    documents: dict[object, Document],
    patient_id: object,
    provider: LLMProvider,
) -> None:
    """Ask the large model to decide only the compact, already-semantic uncertain pairs."""
    prompt = (
        "You are the senior clinical relationship arbiter. Decide each compact candidate pair independently. "
        "Return RELATED only for a supported clinical episode; otherwise return NOT_RELATED or UNCERTAIN.\n"
        f"Candidate pairs: {json.dumps([{'candidate_index': index, 'prescription': _relation_context(source, 'prescription'), 'invoice': _relation_context(target, 'invoice')} for index, (source, target) in enumerate(pairs)], ensure_ascii=False)}\n"
        f"Previous operator decisions: {json.dumps(_feedback_examples(feedback, documents, patient_id), ensure_ascii=False)}"
    )
    response = await provider.structured_completion(prompt, _pair_decision_schema())
    decisions = response.get("decisions")
    if not isinstance(decisions, list):
        return
    decided_indexes: set[int] = set()
    for decision in decisions:
        parsed = _parse_relation_decision(decision, len(pairs), decided_indexes)
        if parsed is None:
            continue
        candidate_index, relation_decision, confidence, reason, title, evidence = parsed
        decided_indexes.add(candidate_index)
        if relation_decision == "RELATED":
            source, target = pairs[candidate_index]
            _create_event_and_link(
                db, source, target, "LLM_PROPOSED", EventStatus.PROPOSED,
                confidence, [*evidence, f"model_reason: {reason}"], [], title,
            )


def _inventory_schema() -> dict[str, object]:
    return {
        "type": "object",
        "properties": {
            "matches": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "prescription_document_id": {"type": "string"},
                        "invoice_document_id": {"type": "string"},
                        "decision": {"type": "string", "enum": ["RELATED", "UNCERTAIN"]},
                        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                        "event_title": {"type": "string", "maxLength": 255},
                        "reason": {"type": "string", "maxLength": 1000},
                        "evidence": {"type": "array", "items": {"type": "string", "maxLength": 300}, "maxItems": 8},
                    },
                    "required": ["prescription_document_id", "invoice_document_id", "decision", "confidence", "event_title", "reason", "evidence"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["matches"],
        "additionalProperties": False,
    }


def _pair_decision_schema() -> dict[str, object]:
    return {
        "type": "object",
        "properties": {
            "decisions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "candidate_index": {"type": "integer", "minimum": 0},
                        "decision": {"type": "string", "enum": ["RELATED", "NOT_RELATED", "UNCERTAIN"]},
                        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                        "event_title": {"type": "string", "maxLength": 255},
                        "reason": {"type": "string", "maxLength": 1000},
                        "evidence": {"type": "array", "items": {"type": "string", "maxLength": 300}, "maxItems": 8},
                    },
                    "required": ["candidate_index", "decision", "confidence", "event_title", "reason", "evidence"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["decisions"],
        "additionalProperties": False,
    }


def _parse_inventory_match(
    match: object,
    eligible: dict[tuple[str, str], tuple[Prescription, ExpenseDocument]],
    selected_keys: set[tuple[str, str]],
) -> tuple[Prescription, ExpenseDocument, str, float, str, str, list[str]] | None:
    if not isinstance(match, dict):
        return None
    prescription_id = match.get("prescription_document_id")
    invoice_id = match.get("invoice_document_id")
    decision = match.get("decision")
    confidence = match.get("confidence")
    reason = match.get("reason")
    title = match.get("event_title")
    evidence = match.get("evidence")
    key = (prescription_id, invoice_id)
    if (
        not isinstance(prescription_id, str) or not isinstance(invoice_id, str) or key in selected_keys
        or key not in eligible or decision not in {"RELATED", "UNCERTAIN"}
        or not isinstance(confidence, (int, float)) or isinstance(confidence, bool)
        or not isinstance(reason, str) or not isinstance(title, str) or not title.strip()
        or not isinstance(evidence, list) or not all(isinstance(item, str) for item in evidence)
    ):
        return None
    source, target = eligible[key]
    return source, target, decision, min(1.0, max(0.0, float(confidence))), reason[:1000], title.strip()[:255], evidence[:8]


def _parse_relation_decision(
    decision: object, candidate_count: int, decided_indexes: set[int],
) -> tuple[int, str, float, str, str, list[str]] | None:
    """Validate one model decision before it can influence the medical graph."""
    if not isinstance(decision, dict):
        return None
    candidate_index = decision.get("candidate_index")
    relation_decision = decision.get("decision")
    confidence = decision.get("confidence")
    reason = decision.get("reason")
    title = decision.get("event_title")
    evidence = decision.get("evidence")
    if (
        not isinstance(candidate_index, int) or isinstance(candidate_index, bool)
        or candidate_index in decided_indexes or not 0 <= candidate_index < candidate_count
        or relation_decision not in {"RELATED", "NOT_RELATED", "UNCERTAIN"}
        or not isinstance(confidence, (int, float)) or isinstance(confidence, bool)
        or not isinstance(reason, str) or not isinstance(title, str) or not title.strip()
        or not isinstance(evidence, list) or not all(isinstance(item, str) for item in evidence)
    ):
        return None
    return candidate_index, relation_decision, min(1.0, max(0.0, float(confidence))), reason[:1000], title.strip()[:255], evidence[:8]


def _relation_context(
    document: Prescription | ExpenseDocument, kind: str, include_extraction: bool = False,
) -> dict[str, object]:
    """Give the model complete extracted facts, not rule-derived scores or labels."""
    if kind == "prescription":
        context: dict[str, object] = {
            "patient_id": str(document.patient_id) if document.patient_id else None,
            "date": str(document.prescription_date) if document.prescription_date else None,
            "provider": document.provider,
            "requested_services": _services(document.extraction, "requested_services"),
            "prescribed_drugs": _evidence_values(document.extraction, "prescribed_drugs"),
            "requested_lab_tests": _evidence_values(document.extraction, "requested_lab_tests"),
        }
        if include_extraction:
            context["full_extraction"] = document.extraction
        return context
    context = {
        "patient_id": str(document.patient_id) if document.patient_id else None,
        "date": str(document.invoice_date) if document.invoice_date else None,
        "provider": document.provider_name,
        "services": _services(document.extraction, "services"),
        "billed_drugs": _evidence_values(document.extraction, "billed_drugs"),
        "billed_lab_tests": _evidence_values(document.extraction, "billed_lab_tests"),
    }
    if include_extraction:
        context["full_extraction"] = document.extraction
    return context


def _feedback_examples(
    feedback: list[AssociationFeedback], documents: dict[object, Document], patient_id: object | None
) -> list[dict[str, object]]:
    """Provide recent same-patient corrections as local few-shot guidance to the LLM."""
    examples: list[dict[str, object]] = []
    for item in feedback:
        if _is_legacy_rule_rejection(item):
            continue
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


def _is_legacy_rule_rejection(feedback: AssociationFeedback) -> bool:
    """Allow the LLM to reassess bulk rejections created by the retired rule engine."""
    return feedback.decision == "REJECTED" and feedback.reason == LEGACY_RULE_REJECTION_REASON


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
