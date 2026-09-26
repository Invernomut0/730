from __future__ import annotations

from typing import Any, ClassVar
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.db.session import SessionLocal
from app.main import app
from app.models.entities import (
    AIExecution,
    ClinicalDocument,
    Document,
    DocumentLink,
    DocumentState,
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

    def __init__(self, patient_name: str = "Laura Bianchi") -> None:
        self.patient_name = patient_name

    async def models(self) -> list[str]:
        return [self.model_id]

    async def structured_completion(self, _prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        evidence = {"value": self.patient_name, "page": 1, "source_text": self.patient_name, "confidence": 1.0}
        if schema["title"] == "PrescriptionExtraction":
            return {
                "document_date": "2026-03-01",
                "patient": evidence,
                "diagnosis_evidence": [{"kind": "CLINICAL_INDICATION", "evidence": {"value": "Dolore ginocchio", "page": 1, "source_text": "Dolore ginocchio", "confidence": 0.9}}],
                "requested_services": [{"value": "visita ortopedica", "page": 1, "source_text": "visita ortopedica", "confidence": 1.0}],
            }
        if schema["title"] == "GenericClinicalExtraction":
            return {
                "document_date": "2026-03-07",
                "patient": evidence,
                "provider": {"value": "Laboratorio locale", "confidence": 0.95},
                "summary": {"value": "Esiti di laboratorio", "confidence": 0.92},
                "laboratory_tests": [{"value": "Emocromo completo", "confidence": 0.96}],
            }
        return {
            "invoice_date": "2026-03-05",
            "patient_name": evidence,
            "provider_name": {"value": "Studio Ortopedico", "page": 1, "source_text": "Studio Ortopedico", "confidence": 1.0},
            "services": [{"description": {"value": "visita ortopedica", "page": 1, "source_text": "visita ortopedica", "confidence": 1.0}, "amount": "180.00"}],
            "total_amount": "180.00",
        }


@pytest.mark.asyncio
async def test_prescription_invoice_vertical_slice_creates_event(monkeypatch: pytest.MonkeyPatch) -> None:
    database = SessionLocal()
    household_id = member_id = prescription_document_id = invoice_document_id = None
    try:
        patient_suffix = uuid4().hex[:12]
        household = Household(name=f"Synthetic family {uuid4()}")
        database.add(household)
        database.flush()
        household_id = household.id
        member = HouseholdMember(household_id=household.id, first_name="Synthetic", last_name=patient_suffix)
        database.add(member)
        database.flush()
        member_id = member.id
        prescription_document = Document(original_filename="synthetic-prescription.pdf", logical_name="2026-03-01_prescrizione_ortopedica.pdf", mime_type="application/pdf", byte_size=1, sha256="a" * 64, storage_key=f"originals/{uuid4()}.pdf", document_type=DocumentType.PRESCRIPTION)
        invoice_document = Document(original_filename="synthetic-invoice.pdf", logical_name="2026-03-05_fattura_ortopedica.pdf", mime_type="application/pdf", byte_size=1, sha256="b" * 64, storage_key=f"originals/{uuid4()}.pdf", document_type=DocumentType.INVOICE)
        database.add_all([prescription_document, invoice_document])
        database.commit()
        prescription_document_id, invoice_document_id = prescription_document.id, invoice_document.id

        provider = SyntheticLLMProvider(f"Synthetic {patient_suffix}")
        await structure_document(database, prescription_document, "Synthetic prescription", provider)
        await structure_document(database, invoice_document, "Synthetic invoice", provider)
        prescription_document.state = DocumentState.COMPLETE
        invoice_document.state = DocumentState.COMPLETE
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
        queued_documents: list[str] = []

        class LocalQueue:
            values: ClassVar[dict[str, str]] = {}

            async def enqueue_job(self, name: str, document_id: str) -> None:
                assert name == "process_document"
                queued_documents.append(document_id)

            async def get(self, key: str) -> str | None:
                return self.values.get(key)

            async def set(self, key: str, value: str) -> None:
                self.values[key] = value

            async def delete(self, key: str) -> int:
                return int(self.values.pop(key, None) is not None)

            async def aclose(self) -> None:
                return None

        async def create_local_queue(*_args: object, **_kwargs: object) -> LocalQueue:
            return LocalQueue()

        monkeypatch.setattr("app.api.v1.router.create_pool", create_local_queue)
        monkeypatch.setattr("app.services.runtime_settings.create_pool", create_local_queue)
        with TestClient(app) as client:
            approved = client.post(f"/api/v1/medical-events/{event.id}/association", json={"action": "approve"})
            proposed = client.get("/api/v1/medical-events?status=PROPOSED")
            confirmed = client.get("/api/v1/medical-events?status=CONFIRMED")
            rebuilt = client.post("/api/v1/medical-events/rebuild-associations")
        assert approved.status_code == 200
        assert approved.json()["status"] == "CONFIRMED"
        assert str(event.id) not in {item["id"] for item in proposed.json()}
        assert str(event.id) in {item["id"] for item in confirmed.json()}
        assert rebuilt.status_code == 200
        assert rebuilt.json()["documents_queued"] == 0
        assert rebuilt.json()["documents_rebuilt"] >= 2
        assert queued_documents == []
        assert database.scalar(select(MedicalEvent).where(MedicalEvent.id == event.id)) is None
        rebuilt_link = database.scalar(select(DocumentLink).where(
            DocumentLink.source_document_id == prescription_document_id,
            DocumentLink.target_document_id == invoice_document_id,
        ))
        assert rebuilt_link is not None
        assert rebuilt_link.medical_event_id != event.id
        assert database.scalar(select(Prescription).where(Prescription.document_id == prescription_document_id)) is not None
        assert database.scalar(select(ExpenseDocument).where(ExpenseDocument.document_id == invoice_document_id)) is not None
        database.refresh(prescription_document)
        database.refresh(invoice_document)
        assert prescription_document.state == DocumentState.COMPLETE
        assert invoice_document.state == DocumentState.COMPLETE
        with TestClient(app) as client:
            saved_settings = client.put("/api/v1/settings/llm", json={
                "document_model": "small-extraction-model",
                "classification_model": "small-model",
                "fallback_model": "fallback-model",
                "relation_model": "relation-model",
                "rizzo_flow_enabled": True,
                "rizzo_flow_base_url": "http://localhost:8788",
            })
            reloaded_settings = client.get("/api/v1/settings/llm")
            stopped = client.post("/api/v1/settings/jobs/stop")
            resumed = client.post("/api/v1/settings/jobs/resume")
        assert saved_settings.status_code == 200
        assert saved_settings.json()["document_model"] == "small-extraction-model"
        assert saved_settings.json()["relation_model"] == "relation-model"
        assert reloaded_settings.json()["relation_model"] == "relation-model"
        assert stopped.json()["jobs_paused"] is True
        assert resumed.json()["jobs_paused"] is False
        database.refresh(prescription_document)
        assert prescription_document.state == DocumentState.COMPLETE
        queued_documents.clear()
        with TestClient(app) as client:
            forced = client.post(f"/api/v1/documents/{prescription_document_id}/reanalyze")
        assert forced.status_code == 200
        assert forced.json()["documents_queued"] == 1
        assert queued_documents == [str(prescription_document_id)]
        database.refresh(prescription_document)
        assert prescription_document.state == DocumentState.EXTRACTING
        assert prescription_document.analysis_started_at is not None
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


@pytest.mark.asyncio
async def test_generic_clinical_extraction_persists_fallback_facts() -> None:
    database = SessionLocal()
    document_id = None
    try:
        document = Document(
            original_filename="generic-clinical.pdf",
            mime_type="application/pdf",
            byte_size=1,
            sha256="c" * 64,
            storage_key=f"originals/{uuid4()}.pdf",
            document_type=DocumentType.OTHER,
        )
        database.add(document)
        database.commit()
        document_id = document.id

        await structure_document(database, document, "Synthetic generic clinical document", SyntheticLLMProvider())

        extracted = database.scalar(select(ClinicalDocument).where(ClinicalDocument.document_id == document.id))
        assert extracted is not None
        assert extracted.provider == "Laboratorio locale"
        assert extracted.extraction["laboratory_tests"][0]["value"] == "Emocromo completo"
    finally:
        if document_id:
            database.rollback()
            database.execute(delete(ClinicalDocument).where(ClinicalDocument.document_id == document_id))
            database.execute(delete(AIExecution).where(AIExecution.document_id == document_id))
            database.execute(delete(Document).where(Document.id == document_id))
            database.commit()
        database.close()
