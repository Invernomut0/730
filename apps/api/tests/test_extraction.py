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
    settings = Settings()
    assert settings.lmstudio_request_timeout_seconds == 1800


def test_extractions_normalize_unambiguous_italian_dates() -> None:
    prescription = PrescriptionExtraction.model_validate({"document_date": "25/09/2026"})
    invoice = InvoiceExtraction.model_validate({"invoice_date": "25-09-2026"})

    assert prescription.document_date is not None and prescription.document_date.isoformat() == "2026-09-25"
    assert invoice.invoice_date is not None and invoice.invoice_date.isoformat() == "2026-09-25"


def test_prescription_and_invoice_preserve_itemized_drugs_and_lab_tests() -> None:
    prescription = PrescriptionExtraction.model_validate({
        "prescribed_drugs": [
            {"value": "Tachipirina 1000 mg", "confidence": 0.98},
            {"value": "Augmentin 875 mg", "confidence": 0.96},
        ],
        "requested_lab_tests": [
            {"value": "Emocromo completo", "confidence": 0.98},
            {"value": "AST", "confidence": 0.95},
        ],
    })
    invoice = InvoiceExtraction.model_validate({
        "billed_drugs": [{"value": "Tachipirina 1000", "confidence": 0.98}],
        "billed_lab_tests": [{"value": "Emocromo completo", "confidence": 0.98}],
    })

    assert [item.value for item in prescription.prescribed_drugs] == ["Tachipirina 1000 mg", "Augmentin 875 mg"]
    assert [item.value for item in prescription.requested_lab_tests] == ["Emocromo completo", "AST"]
    assert [item.value for item in invoice.billed_drugs] == ["Tachipirina 1000"]
    assert [item.value for item in invoice.billed_lab_tests] == ["Emocromo completo"]


def test_prescription_reclassifies_lab_service_codes_and_analytes_as_tests() -> None:
    prescription = PrescriptionExtraction.model_validate({
        "prescribed_drugs": [
            {"value": "VITAMINA D (25 OH)", "source_text": "90.44.6 (0090446) VITAMINA D (25 OH)", "confidence": 0.98},
            {"value": "Tachipirina 1000", "source_text": "AIC 012345678 CPR", "confidence": 0.98},
        ],
        "requested_lab_tests": [
            {"value": "CREATININA", "source_text": "90.16.3 (0090163.01) CREATININA", "confidence": 0.97},
            {"value": "CALPROTECTINA FECALE", "source_text": "90.12.A (009012A) CALPROTECTINA FECALE", "confidence": 0.97},
            {"value": "Augmentin", "source_text": "AIC 123456789 COMPRESSE", "confidence": 0.96},
        ],
    })

    assert [item.value for item in prescription.requested_lab_tests] == ["VITAMINA D (25 OH)", "CREATININA", "CALPROTECTINA FECALE"]
    assert [item.value for item in prescription.prescribed_drugs] == ["Tachipirina 1000", "Augmentin"]


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


def test_laboratory_report_preserves_each_printed_result_without_interpretation() -> None:
    report = MedicalReportExtraction.model_validate({
        "report_kind": "LABORATORY_RESULTS",
        "laboratory_results": [
            {
                "analyte": {"value": "Emocromo", "confidence": 0.99},
                "result": {"value": "5.12", "confidence": 0.99},
                "unit": {"value": "milioni/uL", "confidence": 0.98},
                "reference_range": {"value": "4.20 - 5.80", "confidence": 0.98},
            },
            {
                "analyte": {"value": "Creatinina", "confidence": 0.99},
                "result": {"value": "0.89", "confidence": 0.99},
                "unit": {"value": "mg/dL", "confidence": 0.98},
            },
        ],
    })

    assert report.report_kind == "LABORATORY_RESULTS"
    assert report.laboratory_results[0].analyte.value == "Emocromo"
    assert report.laboratory_results[0].reference_range and report.laboratory_results[0].reference_range.value == "4.20 - 5.80"
    assert report.laboratory_results[1].result and report.laboratory_results[1].result.value == "0.89"


def test_medical_report_extraction_normalizes_numeric_string_bounding_boxes() -> None:
    report = MedicalReportExtraction.model_validate({
        "patient": {"value": "Laura Bianchi", "confidence": 0.99, "bbox": ["0.12", "0.24", "0.31", "0.08"]},
        "diagnosis_evidence": [{"kind": "CONFIRMED_DIAGNOSIS", "evidence": {"value": "Condizione documentata", "confidence": 0.9, "bbox": ["0.2", "0.3", "0.4", "0.1"]}}],
    })

    assert report.patient and report.patient.bbox == [0.12, 0.24, 0.31, 0.08]
    assert report.diagnosis_evidence[0].evidence.bbox == [0.2, 0.3, 0.4, 0.1]


def test_medical_report_extraction_discards_incomplete_optional_bounding_box() -> None:
    report = MedicalReportExtraction.model_validate({
        "patient": {"value": "Laura Bianchi", "confidence": 0.99, "bbox": [None]},
    })

    assert report.patient and report.patient.bbox is None
