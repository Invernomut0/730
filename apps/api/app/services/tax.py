"""Conservative local tax allocation service."""
from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.entities import ExpenseDocument, PaymentEvidence, ReimbursementAllocation, TaxAllocation, TaxRuleSet


def evaluate_expense(db: Session, tax_year: int, expense_id, taxpayer_id) -> TaxAllocation:
    """Create a tax allocation only when an official reviewed rule set is available."""
    rules = db.scalar(select(TaxRuleSet).where(TaxRuleSet.tax_year == tax_year, TaxRuleSet.reviewed.is_(True)))
    expense = db.get(ExpenseDocument, expense_id)
    if rules is None or expense is None:
        raise ValueError("Reviewed tax rules and expense document are required.")
    reimbursement = sum((Decimal(str(item.amount)) for item in db.scalars(select(ReimbursementAllocation).where(ReimbursementAllocation.expense_document_id == expense_id))), Decimal(0))
    evidence = db.scalar(select(PaymentEvidence).where(PaymentEvidence.expense_document_id == expense_id))
    gross = Decimal(str(expense.total_amount or 0))
    eligible = max(Decimal(0), gross - reimbursement) if rules.rules.get("reimbursements_reduce_base", False) else gross
    allocation = TaxAllocation(tax_year=tax_year, taxpayer_id=taxpayer_id, expense_document_id=expense_id, gross_amount=gross, reimbursed_amount=reimbursement, eligible_amount=eligible, status="ELIGIBLE" if evidence and evidence.traceable else "REVIEW_REQUIRED")
    db.add(allocation); db.commit(); return allocation
