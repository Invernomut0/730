"""Transaction-safe removal of local records and their dependent data."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from uuid import UUID

from sqlalchemy import delete, or_, select, update
from sqlalchemy.orm import Session

from app.models.entities import (
    AIExecution,
    AuditEvent,
    Document,
    DocumentLink,
    DocumentPage,
    ExpenseDocument,
    Household,
    HouseholdMember,
    MedicalEvent,
    MedicalReport,
    PaymentEvidence,
    PharmacyReceipt,
    Precompiled730Row,
    Prescription,
    PrescriptionItem,
    ReceiptLine,
    Reimbursement,
    ReimbursementAllocation,
    ReviewTask,
    TaxAllocation,
)
from app.services.thumbnails import thumbnail_path


def _ids(rows: Iterable[UUID]) -> list[UUID]:
    return list(rows)


def _delete_reimbursements(db: Session, reimbursement_ids: list[UUID]) -> None:
    if not reimbursement_ids:
        return
    db.execute(delete(ReimbursementAllocation).where(ReimbursementAllocation.reimbursement_id.in_(reimbursement_ids)))
    db.execute(delete(Reimbursement).where(Reimbursement.id.in_(reimbursement_ids)))


def _delete_expense_dependents(db: Session, expense_ids: list[UUID]) -> None:
    if not expense_ids:
        return
    tax_ids = _ids(db.scalars(select(TaxAllocation.id).where(TaxAllocation.expense_document_id.in_(expense_ids))))
    if tax_ids:
        db.execute(
            update(Precompiled730Row)
            .where(Precompiled730Row.tax_allocation_id.in_(tax_ids))
            .values(tax_allocation_id=None, status="LOCAL_ONLY")
        )
        db.execute(delete(TaxAllocation).where(TaxAllocation.id.in_(tax_ids)))
    db.execute(delete(PaymentEvidence).where(PaymentEvidence.expense_document_id.in_(expense_ids)))


def delete_document_review_tasks(db: Session, document_ids: list[UUID]) -> None:
    """Delete reviews that reference a removed document as source or candidate."""
    document_id_values = {str(document_id) for document_id in document_ids}
    review_ids = [
        review.id
        for review in db.scalars(select(ReviewTask))
        if review.entity_id in document_ids
        or (
            review.entity_type == "Document"
            and isinstance(review.context.get("candidate_document_id"), str)
            and review.context["candidate_document_id"] in document_id_values
        )
    ]
    if review_ids:
        db.execute(delete(ReviewTask).where(ReviewTask.id.in_(review_ids)))


def delete_document_group(db: Session, storage_root: Path, document_id: UUID) -> int:
    """Delete a document and exact duplicates plus all dependent application data."""
    selected = db.get(Document, document_id)
    if selected is None:
        raise LookupError("Document not found.")
    documents = list(db.scalars(select(Document).where(Document.sha256 == selected.sha256)))
    document_ids = [item.id for item in documents]
    storage_keys = [item.storage_key for item in documents]
    sha256 = selected.sha256

    prescription_ids = _ids(db.scalars(select(Prescription.id).where(Prescription.document_id.in_(document_ids))))
    receipt_ids = _ids(db.scalars(select(PharmacyReceipt.id).where(PharmacyReceipt.document_id.in_(document_ids))))
    expense_ids = _ids(db.scalars(select(ExpenseDocument.id).where(ExpenseDocument.document_id.in_(document_ids))))
    reimbursement_ids = _ids(db.scalars(select(Reimbursement.id).where(Reimbursement.document_id.in_(document_ids))))
    prescription_item_ids = _ids(db.scalars(select(PrescriptionItem.id).where(PrescriptionItem.prescription_id.in_(prescription_ids)))) if prescription_ids else []
    receipt_line_ids = _ids(db.scalars(select(ReceiptLine.id).where(ReceiptLine.receipt_id.in_(receipt_ids)))) if receipt_ids else []

    _delete_reimbursements(db, reimbursement_ids)
    if receipt_line_ids or expense_ids:
        db.execute(delete(ReimbursementAllocation).where(or_(ReimbursementAllocation.receipt_line_id.in_(receipt_line_ids), ReimbursementAllocation.expense_document_id.in_(expense_ids))))
    _delete_expense_dependents(db, expense_ids)
    if receipt_line_ids:
        db.execute(delete(ReceiptLine).where(ReceiptLine.id.in_(receipt_line_ids)))
    if prescription_item_ids:
        db.execute(delete(PrescriptionItem).where(PrescriptionItem.id.in_(prescription_item_ids)))
    if receipt_ids:
        db.execute(delete(PharmacyReceipt).where(PharmacyReceipt.id.in_(receipt_ids)))
    if prescription_ids:
        db.execute(delete(Prescription).where(Prescription.id.in_(prescription_ids)))
    if expense_ids:
        db.execute(delete(ExpenseDocument).where(ExpenseDocument.id.in_(expense_ids)))
    db.execute(delete(MedicalReport).where(MedicalReport.document_id.in_(document_ids)))
    db.execute(delete(DocumentPage).where(DocumentPage.document_id.in_(document_ids)))
    db.execute(delete(AIExecution).where(AIExecution.document_id.in_(document_ids)))
    db.execute(delete(DocumentLink).where(or_(DocumentLink.source_document_id.in_(document_ids), DocumentLink.target_document_id.in_(document_ids))))
    delete_document_review_tasks(db, document_ids)
    db.execute(delete(AuditEvent).where(AuditEvent.entity_id.in_(document_ids)))
    db.execute(delete(Document).where(Document.id.in_(document_ids)))
    db.commit()

    for storage_key in storage_keys:
        (storage_root / storage_key).unlink(missing_ok=True)
    thumbnail_path(storage_root, sha256).unlink(missing_ok=True)
    return len(document_ids)


def delete_household(db: Session, storage_root: Path, household_id: UUID) -> int:
    """Delete a household, its members, and member-associated application data."""
    household = db.get(Household, household_id)
    if household is None:
        raise LookupError("Household not found.")
    member_ids = _ids(db.scalars(select(HouseholdMember.id).where(HouseholdMember.household_id == household_id)))
    document_ids = set(db.scalars(select(Document.id).where(Document.patient_id.in_(member_ids)))) if member_ids else set()
    if member_ids:
        document_ids.update(db.scalars(select(Prescription.document_id).where(Prescription.patient_id.in_(member_ids))))
        document_ids.update(db.scalars(select(ExpenseDocument.document_id).where(ExpenseDocument.patient_id.in_(member_ids))))
        document_ids.update(db.scalars(select(MedicalReport.document_id).where(MedicalReport.patient_id.in_(member_ids))))
        document_ids.update(db.scalars(select(PharmacyReceipt.document_id).where(PharmacyReceipt.payer_id.in_(member_ids))))
        document_ids.update(
            db.scalars(
                select(PharmacyReceipt.document_id)
                .join(ReceiptLine, ReceiptLine.receipt_id == PharmacyReceipt.id)
                .where(or_(ReceiptLine.patient_id.in_(member_ids), ReceiptLine.payer_id.in_(member_ids)))
            )
        )
    deleted_documents = 0
    for document_id in document_ids:
        if db.get(Document, document_id) is not None:
            deleted_documents += delete_document_group(db, storage_root, document_id)

    if member_ids:
        reimbursement_ids = _ids(db.scalars(select(Reimbursement.id).where(Reimbursement.payer_id.in_(member_ids))))
        _delete_reimbursements(db, reimbursement_ids)
        tax_ids = _ids(db.scalars(select(TaxAllocation.id).where(TaxAllocation.taxpayer_id.in_(member_ids))))
        if tax_ids:
            db.execute(update(Precompiled730Row).where(Precompiled730Row.tax_allocation_id.in_(tax_ids)).values(tax_allocation_id=None, status="LOCAL_ONLY"))
            db.execute(delete(TaxAllocation).where(TaxAllocation.id.in_(tax_ids)))
        event_ids = _ids(db.scalars(select(MedicalEvent.id).where(MedicalEvent.household_member_id.in_(member_ids))))
        if event_ids:
            db.execute(delete(DocumentLink).where(DocumentLink.medical_event_id.in_(event_ids)))
            db.execute(delete(MedicalEvent).where(MedicalEvent.id.in_(event_ids)))
        db.execute(delete(ReviewTask).where(ReviewTask.entity_id.in_(member_ids + [household_id])))
        db.execute(delete(AuditEvent).where(AuditEvent.entity_id.in_(member_ids + [household_id])))
        db.execute(delete(HouseholdMember).where(HouseholdMember.id.in_(member_ids)))
    db.execute(delete(Household).where(Household.id == household_id))
    db.commit()
    return deleted_documents