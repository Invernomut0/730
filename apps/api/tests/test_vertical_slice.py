from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.db.session import SessionLocal
from app.main import app
from app.models.entities import (
    AIExecution,
    Document,
    DocumentLink,
    DocumentType,
    ExpenseDocument,
    Household,
    HouseholdMember,
    MedicalEvent,
    Prescription,
)
from app.services.eventing import cluster_document
from app.services.structuring import structure_document


class SyntheticLLMProvider:
    """Test-only local-provider substitute permitted for structured extraction tests."""

    model_id = "synthetic-local-model"

    async def models(self) -> list[str]:
        return [self.model_id]

    async def structured_completion(self, _prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        evidence = {"value": "Laura Bianchi", "page": 1, "source_text": "Laura Bianchi", "confidence": 1.0}
        if schema["title"] == "PrescriptionExtraction":
            return {
                "document_date": "2026-03-01",
                "patient": evidence,
                "diagnosis_evidence": [{"kind": "CLINICAL_INDICATION", "evidence": {"value": "Dolore ginocchio", "page": 1, "source_text": "Dolore ginocchio", "confidence": 0.9}}],
                "requested_services": [{"value": "visita ortopedica", "page": 1, "source_text": "visita ortopedica", "confidence": 1.0}],
            }
        return {
            "invoice_date": "2026-03-05",
            "patient_name": evidence,
            "provider_name": {"value": "Studio Ortopedico", "page": 1, "source_text": "Studio Ortopedico", "confidence": 1.0},
            "services": [{"description": {"value": "visita ortopedica", "page": 1, "source_text": "visita ortopedica", "confidence": 1.0}, "amount": "180.00"}],
            "total_amount": "180.00",
        }


@pytest.mark.asyncio
async def test_prescription_invoice_vertical_slice_creates_event() -> None:
    database = SessionLocal()
    household_id = member_id = prescription_document_id = invoice_document_id = None
    try:
        household = Household(name=f"Synthetic family {uuid4()}")
        database.add(household)
        database.flush()
        household_id = household.id
        member = HouseholdMember(household_id=household.id, first_name="Laura", last_name="Bianchi")
        database.add(member)
        database.flush()
        member_id = member.id
        prescription_document = Document(original_filename="synthetic-prescription.pdf", logical_name="2026-03-01_prescrizione_ortopedica.pdf", mime_type="application/pdf", byte_size=1, sha256="a" * 64, storage_key=f"originals/{uuid4()}.pdf", document_type=DocumentType.PRESCRIPTION)
        invoice_document = Document(original_filename="synthetic-invoice.pdf", logical_name="2026-03-05_fattura_ortopedica.pdf", mime_type="application/pdf", byte_size=1, sha256="b" * 64, storage_key=f"originals/{uuid4()}.pdf", document_type=DocumentType.INVOICE)
        database.add_all([prescription_document, invoice_document])
        database.commit()
        prescription_document_id, invoice_document_id = prescription_document.id, invoice_document.id

        provider = SyntheticLLMProvider()
        await structure_document(database, prescription_document, "Synthetic prescription", provider)
        await structure_document(database, invoice_document, "Synthetic invoice", provider)
        cluster_document(database, invoice_document, auto_confirm_threshold=0.95, suggest_threshold=0.75)
        database.commit()

        event = database.scalar(select(MedicalEvent).where(MedicalEvent.household_member_id == member.id))
        assert event is not None
        assert event.title == "visita ortopedica"
        event.title = "Linked medical care"
        database.commit()
        assert event.confidence == pytest.approx(0.95)
        link = database.scalar(select(DocumentLink).where(DocumentLink.medical_event_id == event.id))
        assert link is not None
        assert link.evidence == ["same_patient", "invoice_4_days_after_prescription", "service_matches_prescription"]
        with TestClient(app) as client:
            graph = client.get(f"/api/v1/medical-events/{event.id}/graph")
        assert graph.status_code == 200
        assert {node["label"] for node in graph.json()["nodes"]} >= {"2026-03-01_prescrizione_ortopedica.pdf", "2026-03-05_fattura_ortopedica.pdf"}
        assert any(node["label"] == "visita ortopedica" for node in graph.json()["nodes"])
        with TestClient(app) as client:
            evaluation = client.get(f"/api/v1/medical-events/{event.id}/insurance-evaluation")
        assert evaluation.status_code == 200
        assert evaluation.json()["documented_amount"] == "180.00"
        assert evaluation.json()["estimated_eligible_amount"] == "144.00"
        assert database.scalar(select(Prescription).where(Prescription.document_id == prescription_document.id)).patient_id == member.id
        assert database.scalar(select(ExpenseDocument).where(ExpenseDocument.document_id == invoice_document.id)).patient_id == member.id
    finally:
        event_ids = select(MedicalEvent.id).where(MedicalEvent.household_member_id == member_id) if member_id else select(MedicalEvent.id).where(False)
        database.execute(delete(DocumentLink).where(DocumentLink.source_document_id.in_([item for item in (prescription_document_id, invoice_document_id) if item])))
        database.execute(delete(AIExecution).where(AIExecution.document_id.in_([item for item in (prescription_document_id, invoice_document_id) if item])))
        database.execute(delete(ExpenseDocument).where(ExpenseDocument.document_id == invoice_document_id))
        database.execute(delete(Prescription).where(Prescription.document_id == prescription_document_id))
        database.execute(delete(MedicalEvent).where(MedicalEvent.id.in_(event_ids)))
        database.execute(delete(Document).where(Document.id.in_([item for item in (prescription_document_id, invoice_document_id) if item])))
        database.execute(delete(HouseholdMember).where(HouseholdMember.id == member_id))
        database.execute(delete(Household).where(Household.id == household_id))
        database.commit()
        database.close()
