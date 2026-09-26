"""Versioned structured-output contracts for local LLM extraction."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from math import isfinite

from pydantic import BaseModel, Field, field_validator


def normalize_italian_date(value: object) -> object:
    """Convert unambiguous Italian day-first dates to ISO-compatible values."""
    if not isinstance(value, str):
        return value
    parts = value.replace("/", "-").split("-")
    if len(parts) == 3:
        try:
            day, month, year = (int(part) for part in parts)
            return date(year, month, day)
        except ValueError:
            pass
    return value


class EvidenceValue(BaseModel):
    value: str
    page: int | None = Field(default=None, ge=1)
    source_text: str | None = None
    bbox: list[float] | None = None
    confidence: float = Field(ge=0, le=1)

    @field_validator("bbox", mode="before")
    @classmethod
    def normalize_bbox_numbers(cls, value: object) -> object:
        """Normalize local-model coordinates or discard incomplete optional metadata."""
        if not isinstance(value, list):
            return value
        normalized: list[float] = []
        for coordinate in value:
            if isinstance(coordinate, str):
                try:
                    number = float(coordinate.strip())
                except ValueError:
                    return None
            elif isinstance(coordinate, (int, float)) and not isinstance(coordinate, bool):
                number = float(coordinate)
            else:
                return None
            if not isfinite(number):
                return None
            normalized.append(number)
        return normalized


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
    requested_lab_tests: list[EvidenceValue] = Field(default_factory=list)

    @field_validator("document_date", mode="before")
    @classmethod
    def normalize_document_date(cls, value: object) -> object:
        return normalize_italian_date(value)


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
    billed_drugs: list[EvidenceValue] = Field(default_factory=list)
    billed_lab_tests: list[EvidenceValue] = Field(default_factory=list)
    net_amount: Decimal | None = None
    vat: Decimal | None = None
    stamp_duty: Decimal | None = None
    total_amount: Decimal | None = None
    payment_method: EvidenceValue | None = None
    payment_traceability_hint: EvidenceValue | None = None

    @field_validator("invoice_date", mode="before")
    @classmethod
    def normalize_invoice_date(cls, value: object) -> object:
        return normalize_italian_date(value)


class ClinicalActivityExtraction(BaseModel):
    kind: str = Field(pattern="^(VISIT|SURGERY|FOLLOW_UP|THERAPY|HOSPITALIZATION|OTHER)$")
    evidence: EvidenceValue
    scheduled_date: date | None = None

    @field_validator("scheduled_date", mode="before")
    @classmethod
    def normalize_scheduled_date(cls, value: object) -> object:
        return normalize_italian_date(value)


class MedicalReportExtraction(BaseModel):
    report_date: date | None = None
    patient: EvidenceValue | None = None
    patient_fiscal_code: EvidenceValue | None = None
    provider: EvidenceValue | None = None
    diagnosis_evidence: list[DiagnosisEvidenceExtraction] = Field(default_factory=list)
    requested_visits: list[ClinicalActivityExtraction] = Field(default_factory=list)
    operations: list[ClinicalActivityExtraction] = Field(default_factory=list)
    follow_up_activities: list[ClinicalActivityExtraction] = Field(default_factory=list)

    @field_validator("report_date", mode="before")
    @classmethod
    def normalize_report_date(cls, value: object) -> object:
        return normalize_italian_date(value)
