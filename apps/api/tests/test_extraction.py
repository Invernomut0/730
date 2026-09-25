from pathlib import Path

import fitz

from app.core.config import Settings
from app.models.entities import DocumentType
from app.services.extraction import ExtractedPage, classify_document, extract_pdf_text, text_is_insufficient
from app.schemas.extraction import InvoiceExtraction, MedicalReportExtraction, PrescriptionExtraction


def test_native_text_quality_requires_ocr_when_empty() -> None:
    assert text_is_insufficient([ExtractedPage(page_number=1, text="", confidence=1.0)])


def test_native_text_quality_skips_ocr_when_meaningful() -> None:
    assert not text_is_insufficient([ExtractedPage(page_number=1, text="Documento sanitario con testo nativo sufficiente per evitare OCR locale.", confidence=1.0)])


def test_invoice_markers_override_incidental_quota_ricetta_wording() -> None:
    text = """
    FATTURA N.: 5116119
    P.IVA: FK260026187
    VISITA MULTIDISCIPLINARE
    Quota Ricetta -11,50
    Imponibile IVA 36,00
    Totale Fattura 36,00
    """

    assert classify_document(text) == DocumentType.INVOICE


def test_native_pdf_extraction_persists_normalized_word_boxes(tmp_path: Path) -> None:
    path = tmp_path / "clinical-report.pdf"
    pdf = fitz.open()
    page = pdf.new_page(width=200, height=100)
    page.insert_text((20, 30), "Humanitas Report")
    pdf.save(path)
    pdf.close()

    extracted = extract_pdf_text(path)

    words = extracted[0].blocks["words"] if extracted[0].blocks else []
    humanitas = next(word for word in words if word["text"] == "Humanitas")
    assert extracted[0].blocks and extracted[0].blocks["coordinate_space"] == "normalized"
    assert 0 < humanitas["left"] < 1
    assert 0 < humanitas["top"] < 1
    assert 0 < humanitas["width"] < 1
    assert 0 < humanitas["height"] < 1


def test_local_llm_timeout_has_a_safe_default_for_large_models() -> None:
    settings = Settings(lmstudio_request_timeout_seconds=180)
    assert settings.lmstudio_request_timeout_seconds == 180


def test_extractions_normalize_unambiguous_italian_dates() -> None:
    prescription = PrescriptionExtraction.model_validate({"document_date": "25/09/2026"})
    invoice = InvoiceExtraction.model_validate({"invoice_date": "25-09-2026"})

    assert prescription.document_date is not None and prescription.document_date.isoformat() == "2026-09-25"
    assert invoice.invoice_date is not None and invoice.invoice_date.isoformat() == "2026-09-25"


def test_medical_report_extraction_preserves_patient_date_and_activities() -> None:
    report = MedicalReportExtraction.model_validate({
        "report_date": "20/01/2026",
        "patient": {"value": "Lorenzo Vismara", "confidence": 0.99},
        "requested_visits": [{"kind": "VISIT", "evidence": {"value": "Visita multidisciplinare", "confidence": 0.95}}],
        "operations": [{"kind": "SURGERY", "evidence": {"value": "Resezione ileo-cecale", "confidence": 0.92}}],
        "follow_up_activities": [{"kind": "FOLLOW_UP", "evidence": {"value": "Controllo gastroenterologico", "confidence": 0.9}, "scheduled_date": "25/06/2024"}],
    })

    assert report.report_date is not None and report.report_date.isoformat() == "2026-01-20"
    assert report.patient and report.patient.value == "Lorenzo Vismara"
    assert report.requested_visits[0].kind == "VISIT"
    assert report.operations[0].kind == "SURGERY"
    assert report.follow_up_activities[0].scheduled_date is not None
    assert report.follow_up_activities[0].scheduled_date.isoformat() == "2024-06-25"
