"""Versioned, conservative insurance-candidacy evaluation and package export."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import fitz
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


def coverage_amount(amount: Decimal, rules: dict[str, object], in_network: bool = False) -> Decimal:
    """Apply deductible or coinsurance/minimum, capped by the configured limit."""
    if in_network and "in_network_deductible_eur" in rules:
        eligible = max(Decimal(0), amount - Decimal(str(rules["in_network_deductible_eur"])))
    elif "out_network_coinsurance_percent" in rules:
        retained = max(amount * Decimal(str(rules["out_network_coinsurance_percent"])) / 100, Decimal(str(rules.get("out_network_minimum_eur", 0))))
        eligible = max(Decimal(0), amount - retained)
    elif "coinsurance_percent" in rules:
        retained = min(amount * Decimal(str(rules["coinsurance_percent"])) / 100, Decimal(str(rules.get("coinsurance_cap_eur", amount))))
        eligible = max(Decimal(0), amount - retained)
    else:
        eligible = amount
    limit = rules.get("annual_limit_eur", rules.get("annual_household_limit_eur"))
    return min(eligible, Decimal(str(limit))) if limit is not None else eligible


def expense_amount(expense: ExpenseDocument) -> Decimal | None:
    """Return an invoice total only when a structured source contains a valid amount."""
    value = expense.total_amount if expense.total_amount is not None else expense.extraction.get("total_amount")
    if isinstance(value, dict):
        value = value.get("value")
    try:
        amount = Decimal(str(value))
    except (ArithmeticError, ValueError):
        return None
    return amount if amount >= 0 else None


def evaluate_event(db: Session, event_id: UUID, category_name: str = "specialist_and_diagnostics") -> InsuranceEvaluation:
    """Evaluate linked documents against the reviewed local 2026 policy category."""
    ruleset = yaml.safe_load(Path("/rules/insurance/2026.yml").read_text())
    categories = ruleset["categories"]
    if category_name not in categories:
        raise ValueError("Unknown insurance category.")
    category = dict(categories[category_name])
    if "parent" in category:
        category = {**categories[category["parent"]], **category}
    links = list(db.scalars(select(DocumentLink).where(DocumentLink.medical_event_id == event_id)))
    ids = {link.source_document_id for link in links} | {link.target_document_id for link in links}
    prescriptions = list(db.scalars(select(Prescription).where(Prescription.document_id.in_(ids))))
    expenses = list(db.scalars(select(ExpenseDocument).where(ExpenseDocument.document_id.in_(ids))))
    diagnosis = any(bool(item.extraction.get("diagnosis_evidence")) for item in prescriptions)
    required = list(category.get("required_documents", ["valid_expense_document"]))
    if category.get("prescription_required") or category.get("diagnosis_required"):
        required.append("prescription")
    if category.get("diagnosis_required"):
        required.append("diagnosis_or_clinical_indication")
    evidence = {"prescription" if prescriptions else "", "valid_expense_document" if expenses else "", "diagnosis_or_clinical_indication" if diagnosis else ""}
    missing = [item for item in dict.fromkeys(required) if item not in evidence]
    amounts = [amount for item in expenses if (amount := expense_amount(item)) is not None]
    amount = sum(amounts, Decimal(0))
    complete = not missing
    warnings = ["Candidate only: policy verification remains required."]
    if expenses and not amounts:
        warnings.append("Invoice total is unavailable: no reimbursement estimate was calculated.")
    return InsuranceEvaluation(category=category_name, status="candidate" if complete else "review_required", documentation_complete=complete, estimated_eligible_amount=coverage_amount(amount, category) if complete and amounts else Decimal(0), rules=[f"{ruleset['version']}: {category_name}", "human_review_required"], evidence=sorted(item for item in evidence if item), missing_documents=missing, warnings=warnings)


def evaluate_specialist_and_diagnostics(db: Session, event_id: UUID) -> InsuranceEvaluation:
    """Backward-compatible default evaluation."""
    return evaluate_event(db, event_id)


def export_package(output_root: Path, event_id: UUID, evaluation: InsuranceEvaluation) -> Path:
    """Create a local PDF summary without embedding originals or clinical text."""
    output_root.mkdir(parents=True, exist_ok=True)
    path = output_root / f"insurance-{event_id}.pdf"
    pdf = fitz.open()
    page = pdf.new_page()
    page.insert_text((50, 60), "HealthDocs insurance candidate package\n\n" + f"Event: {event_id}\nCategory: {evaluation.category}\nStatus: {evaluation.status}\nEstimated eligible amount: EUR {evaluation.estimated_eligible_amount}\n\nEvidence: {', '.join(evaluation.evidence) or 'none'}\nMissing: {', '.join(evaluation.missing_documents) or 'none'}\n\nHuman policy review required.", fontsize=11)
    pdf.save(path)
    pdf.close()
    return path
