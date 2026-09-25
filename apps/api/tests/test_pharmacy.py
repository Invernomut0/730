from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from sqlalchemy import delete, select

from app.models.entities import Document, Household, HouseholdMember, PharmacyReceipt, ReceiptLine, ReviewTask
from app.db.session import SessionLocal
from app.services.pharmacy import add_receipt_line, allocate_receipt, import_aifa_csv, match_receipt_lines, normalize_aic


def test_local_aifa_validation_and_mixed_allocation(tmp_path: Path) -> None:
    catalog = tmp_path / "aifa.csv"
    catalog.write_text("aic,name,active_ingredient,manufacturer\n123456789,Paracetamolo 500mg,paracetamolo,Example Pharma\n", encoding="utf-8")
    db = SessionLocal()
    document_id = receipt_id = household_id = payer_id = patient_id = line_id = None
    try:
        assert normalize_aic("AIC 123 456 789") == "123456789"
        assert import_aifa_csv(db, catalog, "2026-09-25") == 1
        household = Household(name=f"Pharmacy family {uuid4()}")
        db.add(household)
        db.flush()
        household_id = household.id
        payer = HouseholdMember(household_id=household.id, first_name="Payer", last_name="Example")
        patient = HouseholdMember(household_id=household.id, first_name="Patient", last_name="Example")
        db.add_all([payer, patient])
        document = Document(original_filename="receipt.pdf", mime_type="application/pdf", byte_size=1, sha256=uuid4().hex * 2, storage_key=f"originals/{uuid4()}.pdf")
        db.add(document)
        db.flush()
        document_id, payer_id, patient_id = document.id, payer.id, patient.id
        receipt = PharmacyReceipt(document_id=document.id, payer_id=payer.id, total_amount=Decimal("4.50"))
        db.add(receipt)
        db.flush()
        receipt_id = receipt.id
        line = add_receipt_line(db, receipt, "Paracetamolo 500mg", Decimal("4.50"), "123456789")
        db.commit()
        line_id = line.id
        assert line.aic_validated
        assert match_receipt_lines(db, receipt.id) == 0
        result = allocate_receipt(db, receipt.id, {line.id: patient.id})
        assert result.allocated_amount == Decimal("4.50")
        assert result.review_required
        assert db.get(ReceiptLine, line.id).patient_id == patient.id
        assert db.scalar(select(ReviewTask).where(ReviewTask.entity_id == line.id)) is not None
    finally:
        if line_id:
            db.execute(delete(ReviewTask).where(ReviewTask.entity_id == line_id))
            db.execute(delete(ReceiptLine).where(ReceiptLine.id == line_id))
        if receipt_id:
            db.execute(delete(PharmacyReceipt).where(PharmacyReceipt.id == receipt_id))
        if document_id:
            db.execute(delete(Document).where(Document.id == document_id))
        if payer_id or patient_id:
            db.execute(delete(HouseholdMember).where(HouseholdMember.id.in_([item for item in (payer_id, patient_id) if item])))
        if household_id:
            db.execute(delete(Household).where(Household.id == household_id))
        db.commit()
        db.close()
