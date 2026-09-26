from datetime import date
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.db.session import SessionLocal
from app.core.config import get_settings
from app.main import app
from app.models.entities import Document, DocumentLink, DocumentState, DocumentType, ExpenseDocument, MedicalEvent, MedicalReport, Prescription, ReviewTask, ReviewType


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
        database.add_all([
            Prescription(document_id=prescription_id, prescription_date=date(2026, 3, 1)),
            ExpenseDocument(document_id=invoice_id, invoice_date=date(2026, 3, 5)),
        ])
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


def test_listing_reviews_resolves_orphaned_document_review() -> None:
    database = SessionLocal()
    review_id = None
    try:
        review = ReviewTask(
            type=ReviewType.LINK_AMBIGUOUS,
            entity_type="Document",
            entity_id=uuid4(),
            context={"candidate_document_id": str(uuid4())},
        )
        database.add(review)
        database.commit()
        review_id = review.id

        with TestClient(app) as client:
            response = client.get("/api/v1/review-tasks")

        assert response.status_code == 200
        assert all(item["id"] != str(review_id) for item in response.json())
        database.refresh(review)
        assert review.status == "RESOLVED"
        assert review.resolution == {"action": "documents_removed"}
    finally:
        if review_id:
            database.execute(delete(ReviewTask).where(ReviewTask.id == review_id))
        database.commit()
        database.close()


def test_impossible_date_link_review_is_archived_and_cannot_be_confirmed() -> None:
    database = SessionLocal()
    prescription_id = invoice_id = review_id = None
    try:
        prescription_document = Document(original_filename="late-prescription.pdf", mime_type="application/pdf", byte_size=1, sha256=f"{uuid4().hex}{uuid4().hex}"[:64], storage_key=f"originals/test/{uuid4()}.pdf", document_type=DocumentType.PRESCRIPTION)
        invoice_document = Document(original_filename="early-invoice.pdf", mime_type="application/pdf", byte_size=1, sha256=f"{uuid4().hex}{uuid4().hex}"[:64], storage_key=f"originals/test/{uuid4()}.pdf", document_type=DocumentType.INVOICE)
        database.add_all([prescription_document, invoice_document])
        database.flush()
        prescription_id, invoice_id = prescription_document.id, invoice_document.id
        database.add_all([
            Prescription(document_id=prescription_id, prescription_date=date(2026, 9, 2)),
            ExpenseDocument(document_id=invoice_id, invoice_date=date(2026, 4, 14)),
        ])
        review = ReviewTask(type=ReviewType.LINK_AMBIGUOUS, entity_type="Document", entity_id=prescription_id, context={"candidate_document_id": str(invoice_id), "score": 0.8, "evidence": ["same_patient"], "conflicts": ["invoice_before_prescription"]})
        database.add(review)
        database.commit()
        review_id = review.id

        with TestClient(app) as client:
            rejected = client.post(f"/api/v1/review-tasks/{review_id}/resolve", json={"resolution": {"action": "confirmed_related"}})
            listed = client.get("/api/v1/review-tasks")

        assert rejected.status_code == 422
        assert all(item["id"] != str(review_id) for item in listed.json())
        database.refresh(review)
        assert review.status == "RESOLVED"
        assert review.resolution == {"action": "invoice_before_prescription"}
    finally:
        if review_id:
            database.execute(delete(ReviewTask).where(ReviewTask.id == review_id))
        if prescription_id and invoice_id:
            database.execute(delete(ExpenseDocument).where(ExpenseDocument.document_id == invoice_id))
            database.execute(delete(Prescription).where(Prescription.document_id == prescription_id))
            database.execute(delete(Document).where(Document.id.in_([prescription_id, invoice_id])))
        database.commit()
        database.close()


def test_outside_window_link_review_is_archived() -> None:
    database = SessionLocal()
    prescription_id = invoice_id = review_id = None
    try:
        prescription_document = Document(original_filename="january-prescription.pdf", mime_type="application/pdf", byte_size=1, sha256=f"{uuid4().hex}{uuid4().hex}"[:64], storage_key=f"originals/test/{uuid4()}.pdf", document_type=DocumentType.PRESCRIPTION)
        invoice_document = Document(original_filename="april-invoice.pdf", mime_type="application/pdf", byte_size=1, sha256=f"{uuid4().hex}{uuid4().hex}"[:64], storage_key=f"originals/test/{uuid4()}.pdf", document_type=DocumentType.INVOICE)
        database.add_all([prescription_document, invoice_document])
        database.flush()
        prescription_id, invoice_id = prescription_document.id, invoice_document.id
        database.add_all([
            Prescription(document_id=prescription_id, prescription_date=date(2026, 1, 23)),
            ExpenseDocument(document_id=invoice_id, invoice_date=date(2026, 4, 14)),
        ])
        review = ReviewTask(type=ReviewType.LINK_AMBIGUOUS, entity_type="Document", entity_id=prescription_id, context={"candidate_document_id": str(invoice_id), "score": 0.8, "evidence": ["same_patient"], "conflicts": []})
        database.add(review)
        database.commit()
        review_id = review.id

        with TestClient(app) as client:
            listed = client.get("/api/v1/review-tasks")

        assert all(item["id"] != str(review_id) for item in listed.json())
        database.refresh(review)
        assert review.status == "RESOLVED"
        assert review.resolution == {"action": "invoice_outside_link_window"}
    finally:
        if review_id:
            database.execute(delete(ReviewTask).where(ReviewTask.id == review_id))
        if prescription_id and invoice_id:
            database.execute(delete(ExpenseDocument).where(ExpenseDocument.document_id == invoice_id))
            database.execute(delete(Prescription).where(Prescription.document_id == prescription_id))
            database.execute(delete(Document).where(Document.id.in_([prescription_id, invoice_id])))
        database.commit()
        database.close()


def test_retrying_classification_review_queues_local_processing() -> None:
    database = SessionLocal()
    document_id = review_id = None
    storage_path = None
    try:
        settings = get_settings()
        storage_key = f"originals/test/{uuid4()}.pdf"
        storage_path = settings.storage_root / storage_key
        storage_path.parent.mkdir(parents=True, exist_ok=True)
        storage_path.write_bytes(b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n")
        document = Document(
            original_filename="retry-review.pdf",
            mime_type="application/pdf",
            byte_size=storage_path.stat().st_size,
            sha256=f"{uuid4().hex}{uuid4().hex}"[:64],
            storage_key=storage_key,
            state=DocumentState.REVIEW_REQUIRED,
        )
        database.add(document)
        database.flush()
        document_id = document.id
        review = ReviewTask(
            type=ReviewType.DOCUMENT_TYPE_UNCERTAIN,
            entity_type="Document",
            entity_id=document.id,
            context={"reason": "structured_extraction_unavailable_or_invalid"},
        )
        database.add(review)
        database.commit()
        review_id = review.id

        with TestClient(app) as client:
            response = client.post(f"/api/v1/review-tasks/{review_id}/retry")

        assert response.status_code == 200
        database.refresh(review)
        database.refresh(document)
        assert review.status == "RESOLVED"
        assert review.resolution == {"action": "retry_requested"}
        assert document.state in {DocumentState.STORED, DocumentState.EXTRACTING, DocumentState.REVIEW_REQUIRED}
    finally:
        if document_id:
            database.execute(delete(ReviewTask).where(ReviewTask.entity_id == document_id))
            database.execute(delete(Document).where(Document.id == document_id))
        database.commit()
        if storage_path:
            storage_path.unlink(missing_ok=True)
        database.close()


def test_manually_completing_classification_review_persists_structured_report() -> None:
    database = SessionLocal()
    document_id = review_id = None
    try:
        document = Document(
            original_filename="unclassified-report.pdf",
            mime_type="application/pdf",
            byte_size=1,
            sha256=f"{uuid4().hex}{uuid4().hex}"[:64],
            storage_key=f"originals/test/{uuid4()}.pdf",
            state=DocumentState.REVIEW_REQUIRED,
        )
        database.add(document)
        database.flush()
        document_id = document.id
        review = ReviewTask(type=ReviewType.DOCUMENT_TYPE_UNCERTAIN, entity_type="Document", entity_id=document.id)
        database.add(review)
        database.commit()
        review_id = review.id

        with TestClient(app) as client:
            response = client.post(
                f"/api/v1/review-tasks/{review_id}/complete-manually",
                json={"document_type": "MEDICAL_REPORT", "document_date": "2026-09-26", "patient_name": "Lorenzo Vismara", "service_description": "Referto cardiologico", "provider_name": "Centro medico"},
            )

        assert response.status_code == 200
        database.refresh(document)
        database.refresh(review)
        report = database.scalar(select(MedicalReport).where(MedicalReport.document_id == document_id))
        assert document.document_type == DocumentType.MEDICAL_REPORT
        assert document.state == DocumentState.COMPLETE
        assert document.logical_name and document.logical_name.startswith("2026-09-26_medical_report_")
        assert report is not None and report.extraction["requested_visits"][0]["evidence"]["value"] == "Referto cardiologico"
        assert review.status == "RESOLVED"
        assert review.resolution == {"action": "completed_manually", "document_type": "MEDICAL_REPORT"}
    finally:
        if review_id:
            database.execute(delete(ReviewTask).where(ReviewTask.id == review_id))
        if document_id:
            database.execute(delete(MedicalReport).where(MedicalReport.document_id == document_id))
            database.execute(delete(Document).where(Document.id == document_id))
        database.commit()
        database.close()