"""Local native text extraction and conservative deterministic classification."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import fitz

from app.models.entities import DocumentType


class ExtractionFailed(RuntimeError):
    """Raised when native text cannot be extracted from a supported PDF."""


@dataclass(frozen=True)
class ExtractedPage:
    page_number: int
    text: str
    confidence: float


def extract_pdf_text(path: Path) -> list[ExtractedPage]:
    """Extract native PDF text; OCR belongs to a future provider implementation."""
    try:
        with fitz.open(path) as pdf:
            return [ExtractedPage(index + 1, page.get_text("text").strip(), 1.0) for index, page in enumerate(pdf)]
    except (fitz.FileDataError, RuntimeError) as error:
        raise ExtractionFailed("PDF text extraction failed.") from error


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
