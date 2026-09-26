"""Explainable, precision-first prescription-to-invoice linking."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class LinkCandidate:
    score: float
    evidence: list[str]
    conflicts: list[str]


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
    wanted = " ".join(prescription_services).casefold()
    billed = " ".join(invoice_services).casefold()
    if wanted and billed and any(term in billed for term in wanted.split() if len(term) > 4):
        score += 0.50
        evidence.append("service_matches_prescription")
    return LinkCandidate(min(score, 1.0), evidence, conflicts)
