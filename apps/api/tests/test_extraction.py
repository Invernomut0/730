from app.core.config import Settings
from app.models.entities import DocumentType
from app.services.extraction import ExtractedPage, classify_document, text_is_insufficient
from app.schemas.extraction import InvoiceExtraction, PrescriptionExtraction


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


def test_local_llm_timeout_has_a_safe_default_for_large_models() -> None:
    settings = Settings(lmstudio_request_timeout_seconds=180)
    assert settings.lmstudio_request_timeout_seconds == 180


def test_extractions_normalize_unambiguous_italian_dates() -> None:
    prescription = PrescriptionExtraction.model_validate({"document_date": "25/09/2026"})
    invoice = InvoiceExtraction.model_validate({"invoice_date": "25-09-2026"})

    assert prescription.document_date is not None and prescription.document_date.isoformat() == "2026-09-25"
    assert invoice.invoice_date is not None and invoice.invoice_date.isoformat() == "2026-09-25"
