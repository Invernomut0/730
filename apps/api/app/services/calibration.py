"""Load privacy-safe calibration datasets for offline AI evaluation."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from app.models.entities import DocumentType
from app.schemas.calibration import DocumentClassificationCalibrationSample


def document_classification_dataset_path() -> Path:
    """Return the immutable calibration fixture included in the application image."""
    return Path(__file__).resolve().parents[1] / "calibration" / "document-classifier-v1.jsonl"


def load_document_classification_calibration(
    path: Path | None = None,
) -> list[DocumentClassificationCalibrationSample]:
    """Load validated JSONL records without exposing their text in errors or logs."""
    dataset_path = path or document_classification_dataset_path()
    try:
        lines = dataset_path.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        raise ValueError("Calibration dataset is unavailable.") from error

    samples: list[DocumentClassificationCalibrationSample] = []
    sample_ids: set[str] = set()
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            sample = DocumentClassificationCalibrationSample.model_validate(json.loads(line))
        except (json.JSONDecodeError, ValidationError) as error:
            raise ValueError(f"Invalid calibration record at line {line_number}.") from error
        if sample.sample_id in sample_ids:
            raise ValueError(f"Duplicate calibration sample identifier at line {line_number}.")
        sample_ids.add(sample.sample_id)
        samples.append(sample)

    expected_types = set(DocumentType)
    actual_types = {sample.expected_output.document_type for sample in samples}
    if not samples or actual_types != expected_types:
        raise ValueError("Calibration dataset must cover every document type.")
    return samples