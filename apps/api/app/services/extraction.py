"""Local native text extraction and conservative deterministic classification."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory
import time

import fitz
from PIL import Image, ImageSequence
from pillow_heif import register_heif_opener
from sqlalchemy.orm import Session

from app.adapters.lmstudio import LLMProvider, LLMUnavailable
from app.adapters.ocr import OCRProvider
from app.models.entities import AIExecution, Document, DocumentType

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
    """Extract native PDF text with normalized word boxes for the document viewer."""
    try:
        with fitz.open(path) as pdf:
            pages: list[ExtractedPage] = []
            for index, page in enumerate(pdf, start=1):
                page_width = max(page.rect.width, 1)
                page_height = max(page.rect.height, 1)
                words = [
                    {
                        "text": text,
                        "left": x0 / page_width,
                        "top": y0 / page_height,
                        "width": (x1 - x0) / page_width,
                        "height": (y1 - y0) / page_height,
                    }
                    for x0, y0, x1, y1, text, *_ in page.get_text("words")
                    if text.strip()
                ]
                pages.append(
                    ExtractedPage(
                        index,
                        page.get_text("text").strip(),
                        1.0,
                        {"coordinate_space": "normalized", "words": words},
                    )
                )
            return pages
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
    if any(token in normalized for token in ("FATTURA", "IMPONIBILE", "PARTITA IVA")):
        return DocumentType.INVOICE
    if any(token in normalized for token in ("RICETTA", "PRESCRIZIONE", "MEDICO PRESCRITTORE")):
        return DocumentType.PRESCRIPTION
    if "REFERTO" in normalized:
        return DocumentType.MEDICAL_REPORT
    return DocumentType.UNKNOWN


async def classify_document_with_model(
    db: Session,
    document: Document,
    text: str,
    provider: LLMProvider,
) -> DocumentType:
    """Use the small local model only when deterministic document typing is inconclusive."""
    execution = AIExecution(
        document_id=document.id,
        provider="lmstudio",
        model=provider.model_id,
        prompt_name="document-classifier",
        prompt_version="v1",
        schema_version="v1",
        input_hash=hashlib.sha256(text.encode()).hexdigest(),
        status="STARTED",
    )
    db.add(execution)
    db.commit()
    started = time.monotonic()
    schema = {
        "type": "object",
        "properties": {
            "document_type": {
                "type": "string",
                "enum": [item.value for item in DocumentType if item != DocumentType.UNKNOWN],
            }
        },
        "required": ["document_type"],
        "additionalProperties": False,
    }
    try:
        decision = await provider.structured_completion(
            "Classify this healthcare document as exactly one allowed document_type.\n\n"
            f"Document text:\n{text}",
            schema,
        )
        document_type = DocumentType(str(decision["document_type"]))
    except (KeyError, TypeError, ValueError, LLMUnavailable) as error:
        execution.status = "FAILED"
        execution.duration_ms = int((time.monotonic() - started) * 1000)
        db.commit()
        raise LLMUnavailable("Small-model document classification was unavailable or invalid.") from error
    execution.status = "SUCCEEDED"
    execution.duration_ms = int((time.monotonic() - started) * 1000)
    db.commit()
    return document_type
