"""Pydantic-validated structured extraction with AI provenance."""

from __future__ import annotations

import hashlib
import time
from pathlib import Path
from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session

from app.adapters.lmstudio import LLMProvider, LLMUnavailable
from app.models.entities import AIExecution, Document, DocumentType, ExpenseDocument, Prescription
from app.schemas.extraction import InvoiceExtraction, PrescriptionExtraction
from app.services.identity import resolve_patient


async def structure_document(db: Session, document: Document, text: str, provider: LLMProvider) -> None:
    """Extract a typed record and persist provenance for a classified document."""
    if document.document_type not in {DocumentType.PRESCRIPTION, DocumentType.INVOICE}:
        return
    schema: type[BaseModel] = PrescriptionExtraction if document.document_type == DocumentType.PRESCRIPTION else InvoiceExtraction
    prompt_name = "prescription-extractor" if document.document_type == DocumentType.PRESCRIPTION else "invoice-extractor"
    prompt_path = Path("/prompts") / prompt_name / "v1.md"
    prompt = f"{prompt_path.read_text()}\n\nDocument text:\n{text}"
    execution = AIExecution(document_id=document.id, provider="lmstudio", model="", prompt_name=prompt_name, prompt_version="v1", schema_version="v1", input_hash=hashlib.sha256(text.encode()).hexdigest(), status="STARTED")
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
    execution.model = provider.model_id
    execution.duration_ms = int((time.monotonic() - started) * 1000)
    if isinstance(extracted, PrescriptionExtraction):
        patient = resolve_patient(db, extracted.patient_fiscal_code.value if extracted.patient_fiscal_code else None, extracted.patient.value if extracted.patient else None)
        db.add(Prescription(document_id=document.id, patient_id=patient.member_id, prescription_date=extracted.document_date, provider=extracted.provider.value if extracted.provider else None, extraction=extracted.model_dump(mode="json")))
        document.patient_id = patient.member_id
        document.document_date = extracted.document_date
    else:
        patient = resolve_patient(db, extracted.patient_fiscal_code.value if extracted.patient_fiscal_code else None, extracted.patient_name.value if extracted.patient_name else None)
        db.add(ExpenseDocument(document_id=document.id, patient_id=patient.member_id, invoice_date=extracted.invoice_date, provider_name=extracted.provider_name.value if extracted.provider_name else None, total_amount=extracted.total_amount, extraction=extracted.model_dump(mode="json")))
        document.patient_id = patient.member_id
        document.document_date = extracted.invoice_date
    db.commit()
