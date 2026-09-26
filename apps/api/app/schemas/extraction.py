"""Versioned structured-output contracts for local LLM extraction."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from math import isfinite
import re

from pydantic import BaseModel, Field, field_validator, model_validator


_LAB_SERVICE_CODE = re.compile(r"(?:^|\s)90\.\d{2}", re.IGNORECASE)
_MEDICATION_MARKER = re.compile(
    r"\b(AIC|COMPRESS[AE]|CPR|CAPSUL[AE]|BUSTIN[AE]|GOCCE|SCIROPPO|FLACON[EI]|FIAL[EA]|POMATA|CREMA)\b",
    re.IGNORECASE,
)
_LAB_ANALYTE = re.compile(
    r"\b(EMOCROMO|CREATININA|CALPROTECTINA|FERRITINA|GLICEMIA|COLESTEROLO|TRIGLICERIDI|TRANSAMINASI|TSH|AST|ALT|VITAMINA\s+D\s*\(\s*25\s*OH\s*\))\b",
    re.IGNORECASE,
)


def _item_source(item: EvidenceValue) -> str:
    return f"{item.value} {item.source_text or ''}"


def _is_lab_test(item: EvidenceValue) -> bool:
    """Recognize Italian laboratory service codes and unambiguous analytes."""
    return bool(_LAB_SERVICE_CODE.search(_item_source(item)) or _LAB_ANALYTE.search(item.value))


def _is_medication(item: EvidenceValue) -> bool:
    """Recognize printed medicine forms without guessing from a product name alone."""
    return bool(_MEDICATION_MARKER.search(_item_source(item)))


def _unique_items(items: list[EvidenceValue]) -> list[EvidenceValue]:
    """Keep one evidence record per normalized item while preserving source order."""
    result: list[EvidenceValue] = []
    seen: set[str] = set()
    for item in items:
        key = " ".join(item.value.casefold().split())
        if key not in seen:
            result.append(item)
            seen.add(key)
    return result


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

    @model_validator(mode="after")
    def normalize_item_types(self) -> PrescriptionExtraction:
        """Correct occasional local-model confusion between analytes and medicines."""
        drugs: list[EvidenceValue] = []
        lab_tests: list[EvidenceValue] = []
        for item in self.prescribed_drugs:
            (lab_tests if _is_lab_test(item) else drugs).append(item)
        for item in self.requested_lab_tests:
            (drugs if _is_medication(item) and not _is_lab_test(item) else lab_tests).append(item)
        self.prescribed_drugs = _unique_items(drugs)
        self.requested_lab_tests = _unique_items(lab_tests)
        return self


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


class GenericClinicalExtraction(BaseModel):
    """Lenient structured facts retained when no specialist document schema fits."""

    document_date: date | None = None
    patient: EvidenceValue | None = None
    patient_fiscal_code: EvidenceValue | None = None
    provider: EvidenceValue | None = None
    document_kind: EvidenceValue | None = None
    summary: EvidenceValue | None = None
    clinical_findings: list[EvidenceValue] = Field(default_factory=list)
    medications: list[EvidenceValue] = Field(default_factory=list)
    laboratory_tests: list[EvidenceValue] = Field(default_factory=list)
    services: list[EvidenceValue] = Field(default_factory=list)

    @field_validator("document_date", mode="before")
    @classmethod
    def normalize_document_date(cls, value: object) -> object:
        return normalize_italian_date(value)
