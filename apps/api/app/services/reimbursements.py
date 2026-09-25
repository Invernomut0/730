"""Line-level reimbursement allocation and out-of-pocket reconciliation."""
from decimal import Decimal
from uuid import UUID
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.models.entities import ExpenseDocument, Reimbursement, ReimbursementAllocation


def allocate_reimbursement(db: Session, reimbursement_id: UUID, expense_id: UUID, amount: Decimal) -> ReimbursementAllocation:
    """Allocate a reimbursement without exceeding either source or expense amount."""
    reimbursement = db.get(Reimbursement, reimbursement_id)
    expense = db.get(ExpenseDocument, expense_id)
    if reimbursement is None or expense is None or amount <= 0:
        raise ValueError("Invalid reimbursement allocation.")
    used = Decimal(str(db.scalar(select(func.coalesce(func.sum(ReimbursementAllocation.amount), 0)).where(ReimbursementAllocation.reimbursement_id == reimbursement_id)) or 0))
    allocated = Decimal(str(db.scalar(select(func.coalesce(func.sum(ReimbursementAllocation.amount), 0)).where(ReimbursementAllocation.expense_document_id == expense_id)) or 0))
    if used + amount > Decimal(str(reimbursement.amount)) or allocated + amount > Decimal(str(expense.total_amount or 0)):
        raise ValueError("Allocation exceeds reimbursement or expense amount.")
    item = ReimbursementAllocation(reimbursement_id=reimbursement_id, expense_document_id=expense_id, amount=amount)
    db.add(item); db.commit(); return item


def out_of_pocket(db: Session, expense_id: UUID) -> Decimal:
    """Return gross expense less recorded reimbursement allocations."""
    expense = db.get(ExpenseDocument, expense_id)
    if expense is None:
        raise ValueError("Expense document not found.")
    reimbursed = db.scalar(select(func.coalesce(func.sum(ReimbursementAllocation.amount), 0)).where(ReimbursementAllocation.expense_document_id == expense_id))
    return max(Decimal(0), Decimal(str(expense.total_amount or 0)) - Decimal(str(reimbursed or 0)))
