"""Local native text extraction and conservative deterministic classification."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory

import fitz
from PIL import Image, ImageSequence
from pillow_heif import register_heif_opener

from app.adapters.ocr import OCRProvider
from app.models.entities import DocumentType

register_heif_opener()


def _ocr_page(provider: OCRProvider, path: Path, page_number: int) -> ExtractedPage:
    """Preserve bounding boxes when the configured OCR provider supports them."""
    with_boxes = getattr(provider, "extract_with_boxes", None)
    if with_boxes is None:
        return ExtractedPage(page_number, provider.extract(path), 0.7)
    result = with_boxes(path)
    return ExtractedPage(page_number, result.text, 0.7, result.blocks)


class ExtractionFailed(RuntimeError):
    """Raised when native text cannot be extracted from a supported PDF."""


@dataclass(frozen=True)
class ExtractedPage:
    page_number: int
    text: str
    confidence: float
    blocks: dict[str, object] | None = None


def extract_pdf_text(path: Path) -> list[ExtractedPage]:
    """Extract native PDF text; OCR belongs to a future provider implementation."""
    try:
        with fitz.open(path) as pdf:
            return [ExtractedPage(index + 1, page.get_text("text").strip(), 1.0) for index, page in enumerate(pdf)]
    except (fitz.FileDataError, RuntimeError) as error:
        raise ExtractionFailed("PDF text extraction failed.") from error


def text_is_insufficient(pages: list[ExtractedPage]) -> bool:
    """Use OCR only when native PDF text has no meaningful content."""
    return not pages or sum(len(page.text.strip()) for page in pages) < 40


def extract_with_ocr(path: Path, mime_type: str, provider: OCRProvider) -> list[ExtractedPage]:
    """Extract OCR text locally from a raster image or rendered PDF pages."""
    if mime_type.startswith("image/"):
        if mime_type in {"image/tiff", "image/heic"}:
            with Image.open(path) as source, TemporaryDirectory() as directory:
                pages: list[ExtractedPage] = []
                for number, frame in enumerate(ImageSequence.Iterator(source), start=1):
                    rendered = Path(directory) / f"page-{number}.png"
                    frame.convert("RGB").save(rendered, "PNG")
                    pages.append(_ocr_page(provider, rendered, number))
                return pages
        return [_ocr_page(provider, path, 1)]
    try:
        with fitz.open(path) as pdf, TemporaryDirectory() as directory:
            pages: list[ExtractedPage] = []
            for number, page in enumerate(pdf, start=1):
                image = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
                rendered = Path(directory) / f"page-{number}.png"
                image.save(rendered)
                pages.append(_ocr_page(provider, rendered, number))
            return pages
    except (fitz.FileDataError, RuntimeError) as error:
        raise ExtractionFailed("OCR rendering failed.") from error


def classify_document(text: str) -> DocumentType:
    """Classify only strong textual signals; uncertain files remain UNKNOWN."""
    normalized = text.upper()
    if any(token in normalized for token in ("RICETTA", "PRESCRIZIONE", "MEDICO PRESCRITTORE")):
        return DocumentType.PRESCRIPTION
    if any(token in normalized for token in ("FATTURA", "IMPONIBILE", "PARTITA IVA")):
        return DocumentType.INVOICE
    if "REFERTO" in normalized:
        return DocumentType.MEDICAL_REPORT
    return DocumentType.UNKNOWN
