"""Pydantic-validated structured extraction with AI provenance."""

from __future__ import annotations

import hashlib
import time
from pathlib import Path
from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session

from app.adapters.lmstudio import LLMProvider, LLMUnavailable
from app.models.entities import AIExecution, ClinicalDocument, Document, DocumentType, ExpenseDocument, MedicalReport, Prescription, ReviewTask, ReviewType
from app.schemas.extraction import GenericClinicalExtraction, InvoiceExtraction, MedicalReportExtraction, PrescriptionExtraction
from app.services.identity import resolve_patient


async def structure_document(db: Session, document: Document, text: str, provider: LLMProvider) -> None:
    """Extract a typed record and persist provenance for a classified document."""
    schema_by_type: dict[DocumentType, type[BaseModel]] = {
        DocumentType.PRESCRIPTION: PrescriptionExtraction,
        DocumentType.INVOICE: InvoiceExtraction,
        DocumentType.MEDICAL_REPORT: MedicalReportExtraction,
        DocumentType.PHARMACY_RECEIPT: GenericClinicalExtraction,
        DocumentType.OTHER: GenericClinicalExtraction,
    }
    prompt_by_type = {
        DocumentType.PRESCRIPTION: ("prescription-extractor", "v3"),
        DocumentType.INVOICE: ("invoice-extractor", "v2"),
        DocumentType.MEDICAL_REPORT: ("medical-report-extractor", "v1"),
        DocumentType.PHARMACY_RECEIPT: ("generic-clinical-extractor", "v1"),
        DocumentType.OTHER: ("generic-clinical-extractor", "v1"),
    }
    schema = schema_by_type[document.document_type]
    prompt_name, prompt_version = prompt_by_type[document.document_type]
    prompt_path = Path("/prompts") / prompt_name / f"{prompt_version}.md"
    prompt = f"{prompt_path.read_text()}\n\nDocument text:\n{text}"
    execution = AIExecution(
        document_id=document.id,
        provider="lmstudio",
        model=provider.model_id,
        prompt_name=prompt_name,
        prompt_version=prompt_version,
        schema_version=prompt_version,
        input_hash=hashlib.sha256(text.encode()).hexdigest(),
        status="STARTED",
    )
    db.add(execution)
    db.commit()
    started = time.monotonic()
    try:
        raw = await provider.structured_completion(prompt, schema.model_json_schema())
        extracted = schema.model_validate(raw)
    except (LLMUnavailable, ValidationError) as error:
        execution.status = "FAILED"
        execution.duration_ms = int((time.monotonic() - started) * 1000)
        db.commit()
        raise LLMUnavailable("Structured extraction was unavailable or invalid.") from error
    execution.status = "SUCCEEDED"
    execution.duration_ms = int((time.monotonic() - started) * 1000)
    if isinstance(extracted, PrescriptionExtraction):
        patient = resolve_patient(db, extracted.patient_fiscal_code.value if extracted.patient_fiscal_code else None, extracted.patient.value if extracted.patient else None)
        db.add(Prescription(document_id=document.id, patient_id=patient.member_id, prescription_date=extracted.document_date, provider=extracted.provider.value if extracted.provider else None, extraction=extracted.model_dump(mode="json")))
        document.patient_id = patient.member_id
        document.document_date = extracted.document_date
    elif isinstance(extracted, InvoiceExtraction):
        patient = resolve_patient(db, extracted.patient_fiscal_code.value if extracted.patient_fiscal_code else None, extracted.patient_name.value if extracted.patient_name else None)
        db.add(ExpenseDocument(document_id=document.id, patient_id=patient.member_id, invoice_date=extracted.invoice_date, provider_name=extracted.provider_name.value if extracted.provider_name else None, total_amount=extracted.total_amount, extraction=extracted.model_dump(mode="json")))
        document.patient_id = patient.member_id
        document.document_date = extracted.invoice_date
    elif isinstance(extracted, MedicalReportExtraction):
        patient = resolve_patient(db, extracted.patient_fiscal_code.value if extracted.patient_fiscal_code else None, extracted.patient.value if extracted.patient else None)
        db.add(MedicalReport(document_id=document.id, patient_id=patient.member_id, report_date=extracted.report_date, provider=extracted.provider.value if extracted.provider else None, extraction=extracted.model_dump(mode="json")))
        document.patient_id = patient.member_id
        document.document_date = extracted.report_date
    else:
        patient = resolve_patient(db, extracted.patient_fiscal_code.value if extracted.patient_fiscal_code else None, extracted.patient.value if extracted.patient else None)
        db.add(ClinicalDocument(document_id=document.id, patient_id=patient.member_id, document_date=extracted.document_date, provider=extracted.provider.value if extracted.provider else None, extraction=extracted.model_dump(mode="json")))
        document.patient_id = patient.member_id
        document.document_date = extracted.document_date
    if patient.conflict:
        db.add(ReviewTask(
            type=ReviewType.PATIENT_CONFLICT,
            entity_type="Document",
            entity_id=document.id,
            context={"resolution_evidence": patient.evidence},
        ))
    db.commit()
