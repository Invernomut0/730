"""Explainable, precision-first prescription-to-invoice linking."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import re
import unicodedata


@dataclass(frozen=True)
class LinkCandidate:
    score: float
    evidence: list[str]
    conflicts: list[str]


_GENERIC_SERVICE_WORDS = {
    "ambulatoriale", "controllo", "della", "delle", "degli", "diagnostica", "esame", "prestazione",
    "privata", "richiesta", "sanitaria", "servizio", "specialistica", "visita",
}
_SPECIALTY_ALIASES = {
    "ALLERGOLOGY": ("allerg",),
    "CARDIOLOGY": ("cardio",),
    "DERMATOLOGY": ("dermat",),
    "ENDOCRINOLOGY": ("endocrin",),
    "GASTROENTEROLOGY": ("gastroenter",),
    "GYNECOLOGY": ("ginecol",),
    "MULTIDISCIPLINARY": ("multidisciplin",),
    "NEUROLOGY": ("neurolog",),
    "ONCOLOGY": ("oncolog",),
    "OPHTHALMOLOGY": ("oftalm",),
    "ORTHOPEDICS": ("ortoped",),
    "OTORHINOLARYNGOLOGY": ("otorino", "otorinolaring"),
    "PEDIATRICS": ("pediatric",),
    "PULMONOLOGY": ("pneumolog",),
    "UROLOGY": ("urolog",),
}


def _normalized_service_text(services: list[str]) -> str:
    """Normalize Italian clinical-service wording without changing source data."""
    text = unicodedata.normalize("NFKD", " ".join(services).casefold())
    return "".join(character for character in text if not unicodedata.combining(character))


def _specialties(services: list[str]) -> set[str]:
    text = _normalized_service_text(services)
    return {
        specialty
        for specialty, aliases in _SPECIALTY_ALIASES.items()
        if any(alias in text for alias in aliases)
    }


def _meaningful_terms(services: list[str]) -> set[str]:
    return {
        term
        for term in re.findall(r"[a-z]{4,}", _normalized_service_text(services))
        if term not in _GENERIC_SERVICE_WORDS
    }


def score_prescription_invoice(
    prescription_patient_id: object | None,
    invoice_patient_id: object | None,
    prescription_date: date | None,
    invoice_date: date | None,
    prescription_services: list[str],
    invoice_services: list[str],
) -> LinkCandidate:
    """Score transparent strong signals; an explicit patient mismatch prevents linking."""
    evidence: list[str] = []
    conflicts: list[str] = []
    score = 0.0
    if prescription_patient_id and invoice_patient_id:
        if prescription_patient_id != invoice_patient_id:
            return LinkCandidate(0.0, evidence, ["different_patient"])
        score += 0.30
        evidence.append("same_patient")
    if prescription_date and invoice_date:
        days = (invoice_date - prescription_date).days
        if 0 <= days <= 30:
            score += 0.15
            evidence.append(f"invoice_{days}_days_after_prescription")
        elif days < 0:
            return LinkCandidate(0.0, evidence, ["invoice_before_prescription"])
        else:
            return LinkCandidate(0.0, evidence, ["invoice_outside_link_window"])
    requested_specialties = _specialties(prescription_services)
    billed_specialties = _specialties(invoice_services)
    if requested_specialties and billed_specialties and requested_specialties.isdisjoint(billed_specialties):
        return LinkCandidate(0.0, evidence, ["incompatible_clinical_specialty"])

    requested_terms = _meaningful_terms(prescription_services)
    billed_terms = _meaningful_terms(invoice_services)
    specialty_match = bool(requested_specialties & billed_specialties)
    lexical_match = bool(requested_terms & billed_terms)
    if prescription_services and invoice_services and (specialty_match or lexical_match):
        score += 0.50
        evidence.append("service_matches_prescription")
    return LinkCandidate(min(score, 1.0), evidence, conflicts)
