import json
from pathlib import Path

import pytest

from app.models.entities import DocumentType
from app.services.calibration import load_document_classification_calibration


def test_document_classification_calibration_is_complete_and_synthetic() -> None:
    samples = load_document_classification_calibration()

    assert len(samples) == 12
    assert {sample.expected_output.document_type for sample in samples} == set(DocumentType)
    assert all(sample.source == "synthetic" for sample in samples)
    assert len({sample.sample_id for sample in samples}) == len(samples)


def test_calibration_loader_rejects_duplicate_identifiers(tmp_path: Path) -> None:
    record = {
        "dataset_version": "v1",
        "sample_id": "CAL-CLF-001",
        "task": "document_classification",
        "prompt_name": "document-classifier",
        "prompt_version": "v1",
        "input_text": "Fattura sanitaria.",
        "expected_output": {"document_type": "INVOICE"},
        "source": "synthetic",
        "tags": ["invoice"],
    }
    path = tmp_path / "duplicate.jsonl"
    path.write_text(f"{json.dumps(record)}\n{json.dumps(record)}\n", encoding="utf-8")

    with pytest.raises(ValueError, match="Duplicate calibration sample identifier"):
        load_document_classification_calibration(path)