from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import delete, select

from app.db.session import SessionLocal
from app.models.entities import AIExecution, Document, DocumentType, MedicalReport
from app.services.structuring import structure_document


class SyntheticMedicalReportProvider:
    """Return a representative local medical-report extraction for persistence tests."""

    model_id = "synthetic-local-medical-report"

    async def structured_completion(self, _prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        assert schema["title"] == "MedicalReportExtraction"
        evidence = {"value": "Lorenzo Vismara", "page": 1, "source_text": "VISMARA LORENZO", "confidence": 0.99}
        return {
            "report_date": "20/01/2026",
            "patient": evidence,
            "provider": {"value": "IRCCS Istituto Clinico Humanitas", "page": 1, "source_text": "Humanitas", "confidence": 0.98},
            "requested_visits": [{"kind": "VISIT", "evidence": {"value": "Visita multidisciplinare", "page": 1, "source_text": "VISITA MULTIDISCIPLINARE", "confidence": 0.95}}],
            "operations": [{"kind": "SURGERY", "evidence": {"value": "Resezione ileo-cecale", "page": 1, "source_text": "Resezione ileo-cecale", "confidence": 0.9}}],
            "follow_up_activities": [{"kind": "FOLLOW_UP", "evidence": {"value": "Controllo gastroenterologico", "page": 1, "source_text": "Controllo", "confidence": 0.9}}],
        }


@pytest.mark.asyncio
async def test_structure_medical_report_persists_patient_date_and_activities() -> None:
    database = SessionLocal()
    document_id = None
    try:
        document = Document(
            original_filename="synthetic-report.pdf",
            mime_type="application/pdf",
            byte_size=1,
            sha256=f"{uuid4().hex}{uuid4().hex}"[:64],
            storage_key=f"originals/test/{uuid4()}.pdf",
            document_type=DocumentType.MEDICAL_REPORT,
        )
        database.add(document)
        database.commit()
        document_id = document.id

        await structure_document(database, document, "Representative medical report", SyntheticMedicalReportProvider())

        report = database.scalar(select(MedicalReport).where(MedicalReport.document_id == document_id))
        assert report is not None
        assert report.report_date is not None and report.report_date.isoformat() == "2026-01-20"
        assert document.document_date == report.report_date
        assert report.extraction["requested_visits"][0]["kind"] == "VISIT"
        assert report.extraction["operations"][0]["kind"] == "SURGERY"
        assert report.extraction["follow_up_activities"][0]["kind"] == "FOLLOW_UP"
    finally:
        if document_id:
            database.execute(delete(AIExecution).where(AIExecution.document_id == document_id))
            database.execute(delete(MedicalReport).where(MedicalReport.document_id == document_id))
            database.execute(delete(Document).where(Document.id == document_id))
            database.commit()
        database.close()
