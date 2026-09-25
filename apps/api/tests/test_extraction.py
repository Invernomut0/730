from app.services.extraction import ExtractedPage, text_is_insufficient


def test_native_text_quality_requires_ocr_when_empty() -> None:
    assert text_is_insufficient([ExtractedPage(page_number=1, text="", confidence=1.0)])


def test_native_text_quality_skips_ocr_when_meaningful() -> None:
    assert not text_is_insufficient([ExtractedPage(page_number=1, text="Documento sanitario con testo nativo sufficiente per evitare OCR locale.", confidence=1.0)])
