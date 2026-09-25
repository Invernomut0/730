from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.db.session import SessionLocal
from app.main import app
from app.models.entities import Document, DocumentLink, DocumentType, ExpenseDocument, MedicalEvent, Prescription, ReviewTask, ReviewType


def test_confirming_ambiguous_link_creates_manual_event() -> None:
    database = SessionLocal()
    prescription_id = invoice_id = review_id = event_id = None
    try:
        prescription_document = Document(
            original_filename="review-prescription.pdf",
            mime_type="application/pdf",
            byte_size=1,
            sha256=f"{uuid4().hex}{uuid4().hex}"[:64],
            storage_key=f"originals/test/{uuid4()}.pdf",
            document_type=DocumentType.PRESCRIPTION,
        )
        invoice_document = Document(
            original_filename="review-invoice.pdf",
            mime_type="application/pdf",
            byte_size=1,
            sha256=f"{uuid4().hex}{uuid4().hex}"[:64],
            storage_key=f"originals/test/{uuid4()}.pdf",
            document_type=DocumentType.INVOICE,
        )
        database.add_all([prescription_document, invoice_document])
        database.flush()
        prescription_id, invoice_id = prescription_document.id, invoice_document.id
        database.add_all([Prescription(document_id=prescription_id), ExpenseDocument(document_id=invoice_id)])
        review = ReviewTask(
            type=ReviewType.LINK_AMBIGUOUS,
            entity_type="Document",
            entity_id=prescription_id,
            context={"candidate_document_id": str(invoice_id), "score": 0.75, "evidence": ["same_patient"], "conflicts": ["invoice_before_prescription"]},
        )
        database.add(review)
        database.commit()
        review_id = review.id

        with TestClient(app) as client:
            response = client.post(f"/api/v1/review-tasks/{review_id}/resolve", json={"resolution": {"action": "confirmed_related"}})

        assert response.status_code == 200
        link = database.scalar(select(DocumentLink).where(DocumentLink.source_document_id == prescription_id, DocumentLink.target_document_id == invoice_id))
        assert link is not None
        assert link.relation_type == "MANUALLY_CONFIRMED"
        assert link.evidence == ["same_patient", "manual_review_confirmed"]
        event_id = link.medical_event_id
        assert database.get(MedicalEvent, event_id).status.value == "CONFIRMED"
    finally:
        if review_id:
            database.execute(delete(ReviewTask).where(ReviewTask.id == review_id))
        if prescription_id and invoice_id:
            database.execute(delete(DocumentLink).where(DocumentLink.source_document_id == prescription_id, DocumentLink.target_document_id == invoice_id))
            if event_id:
                database.execute(delete(MedicalEvent).where(MedicalEvent.id == event_id))
            database.execute(delete(ExpenseDocument).where(ExpenseDocument.document_id == invoice_id))
            database.execute(delete(Prescription).where(Prescription.document_id == prescription_id))
            database.execute(delete(Document).where(Document.id.in_([prescription_id, invoice_id])))
        database.commit()
        database.close()