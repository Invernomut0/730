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
_GENERIC_ITEM_WORDS = _GENERIC_SERVICE_WORDS | {
    "analisi", "cliniche", "completo", "con", "del", "dei", "ed", "ematiche",
    "farmaco", "farmaci", "laboratorio", "medicinale", "medicinali", "sangue",
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


def _items_match(requested_items: list[str], billed_items: list[str]) -> bool:
    """Require each explicitly prescribed item to match a distinct invoice line."""
    available = [_item_terms(item) for item in billed_items]
    if not requested_items or not available:
        return False
    used: set[int] = set()
    for requested in requested_items:
        requested_terms = _item_terms(requested)
        if not requested_terms:
            return False
        match = next(
            (
                index
                for index, billed_terms in enumerate(available)
                if index not in used and requested_terms & billed_terms
            ),
            None,
        )
        if match is None:
            return False
        used.add(match)
    return True


def _item_terms(item: str) -> set[str]:
    """Keep concise clinical abbreviations such as AST, ALT, TSH and INR."""
    ignored = _GENERIC_ITEM_WORDS | {"al", "con", "da", "del", "della", "di", "e", "il", "in", "la", "le", "lo", "mg", "ml", "nr", "un"}
    return {
        term
        for term in re.findall(r"[a-z0-9]{2,}", _normalized_service_text([item]))
        if term not in ignored
    }


def score_prescription_invoice(
    prescription_patient_id: object | None,
    invoice_patient_id: object | None,
    prescription_date: date | None,
    invoice_date: date | None,
    prescription_services: list[str],
    invoice_services: list[str],
    prescription_drugs: list[str] | None = None,
    prescription_lab_tests: list[str] | None = None,
    invoice_drugs: list[str] | None = None,
    invoice_lab_tests: list[str] | None = None,
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

    prescribed_drugs = prescription_drugs or []
    requested_lab_tests = prescription_lab_tests or []
    billed_drugs = invoice_drugs or invoice_services
    billed_lab_tests = invoice_lab_tests or invoice_services
    detailed_match = False
    if prescribed_drugs:
        if not _items_match(prescribed_drugs, billed_drugs):
            return LinkCandidate(0.0, evidence, ["prescribed_drugs_missing_from_invoice"])
        detailed_match = True
        evidence.append("all_prescribed_drugs_match_invoice")
    if requested_lab_tests:
        if not _items_match(requested_lab_tests, billed_lab_tests):
            return LinkCandidate(0.0, evidence, ["requested_lab_tests_missing_from_invoice"])
        detailed_match = True
        evidence.append("all_requested_lab_tests_match_invoice")

    requested_terms = _meaningful_terms(prescription_services)
    billed_terms = _meaningful_terms(invoice_services)
    specialty_match = bool(requested_specialties & billed_specialties)
    lexical_match = bool(requested_terms & billed_terms)
    if prescription_services and invoice_services and (specialty_match or lexical_match):
        score += 0.50
        evidence.append("service_matches_prescription")
    elif detailed_match:
        score += 0.50
    return LinkCandidate(min(score, 1.0), evidence, conflicts)
