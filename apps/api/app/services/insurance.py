"""Rule-driven insurance candidacy evaluation for the initial vertical slice."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import yaml
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import DocumentLink, ExpenseDocument, Prescription


@dataclass(frozen=True)
class InsuranceEvaluation:
    category: str
    status: str
    documentation_complete: bool
    estimated_eligible_amount: Decimal
    rules: list[str]
    evidence: list[str]
    missing_documents: list[str]
    warnings: list[str]


def evaluate_specialist_and_diagnostics(db: Session, event_id: UUID) -> InsuranceEvaluation:
    """Evaluate only the documented 2026 specialist/diagnostic candidate rule."""
    rules = yaml.safe_load(Path("/rules/insurance/2026.yml").read_text())
    category = rules["categories"]["specialist_and_diagnostics"]
    links = list(db.scalars(select(DocumentLink).where(DocumentLink.medical_event_id == event_id)))
    document_ids = {link.source_document_id for link in links} | {link.target_document_id for link in links}
    prescriptions = list(db.scalars(select(Prescription).where(Prescription.document_id.in_(document_ids))))
    expenses = list(db.scalars(select(ExpenseDocument).where(ExpenseDocument.document_id.in_(document_ids))))
    diagnosis_present = any(bool(item.extraction.get("diagnosis_evidence")) for item in prescriptions)
    missing: list[str] = []
    if not prescriptions:
        missing.append("prescription")
    if not expenses:
        missing.append("valid_expense_document")
    if not diagnosis_present:
        missing.append("diagnosis_or_clinical_indication")
    amount = sum((Decimal(str(item.total_amount or 0)) for item in expenses), Decimal(0))
    annual_limit = Decimal(str(category["annual_limit_eur"]))
    complete = not missing
    return InsuranceEvaluation(
        category="specialist_and_diagnostics",
        status="candidate" if complete else "review_required",
        documentation_complete=complete,
        estimated_eligible_amount=min(amount, annual_limit) if complete else Decimal(0),
        rules=["insurance-2026-v1: specialist_and_diagnostics", "diagnosis_required"],
        evidence=["linked_prescription" if prescriptions else "", "linked_expense_document" if expenses else ""],
        missing_documents=missing,
        warnings=["Candidate only: policy verification remains required."],
    )
