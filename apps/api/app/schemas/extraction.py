"""Versioned structured-output contracts for local LLM extraction."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field


class EvidenceValue(BaseModel):
    value: str
    page: int | None = Field(default=None, ge=1)
    source_text: str | None = None
    bbox: list[float] | None = None
    confidence: float = Field(ge=0, le=1)


class DiagnosisEvidenceExtraction(BaseModel):
    kind: str = Field(pattern="^(CONFIRMED_DIAGNOSIS|SUSPECTED_DIAGNOSIS|DIAGNOSTIC_QUESTION|CLINICAL_INDICATION|SYMPTOM|ANAMNESIS)$")
    evidence: EvidenceValue


class PrescriptionExtraction(BaseModel):
    document_date: date | None = None
    patient: EvidenceValue | None = None
    patient_fiscal_code: EvidenceValue | None = None
    doctor: EvidenceValue | None = None
    provider: EvidenceValue | None = None
    prescription_number: EvidenceValue | None = None
    diagnosis_evidence: list[DiagnosisEvidenceExtraction] = Field(default_factory=list)
    requested_services: list[EvidenceValue] = Field(default_factory=list)
    prescribed_drugs: list[EvidenceValue] = Field(default_factory=list)


class InvoiceService(BaseModel):
    description: EvidenceValue
    amount: Decimal | None = None


class InvoiceExtraction(BaseModel):
    invoice_number: EvidenceValue | None = None
    invoice_date: date | None = None
    provider_name: EvidenceValue | None = None
    provider_vat_number: EvidenceValue | None = None
    provider_fiscal_code: EvidenceValue | None = None
    patient_name: EvidenceValue | None = None
    patient_fiscal_code: EvidenceValue | None = None
    services: list[InvoiceService] = Field(default_factory=list)
    net_amount: Decimal | None = None
    vat: Decimal | None = None
    stamp_duty: Decimal | None = None
    total_amount: Decimal | None = None
    payment_method: EvidenceValue | None = None
    payment_traceability_hint: EvidenceValue | None = None
