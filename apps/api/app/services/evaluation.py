"""Pure, privacy-safe metrics for local AI calibration runs."""

from __future__ import annotations

from app.schemas.calibration import (
    ClassificationMismatch,
    DocumentClassificationCalibrationSample,
    DocumentClassificationDecision,
    DocumentClassificationEvaluation,
)


def evaluate_document_classification(
    samples: list[DocumentClassificationCalibrationSample],
    decisions: list[DocumentClassificationDecision],
    model: str,
    minimum_accuracy: float,
) -> DocumentClassificationEvaluation:
    """Calculate exact classification accuracy without retaining sample inputs."""
    if not samples or len(samples) != len(decisions):
        raise ValueError("Calibration decisions must match the non-empty sample set.")
    if not 0 <= minimum_accuracy <= 1:
        raise ValueError("Minimum accuracy must be between zero and one.")

    mismatches = [
        ClassificationMismatch(
            sample_id=sample.sample_id,
            expected_document_type=sample.expected_output.document_type,
            actual_document_type=decision.document_type,
        )
        for sample, decision in zip(samples, decisions, strict=True)
        if sample.expected_output.document_type != decision.document_type
    ]
    correct_count = len(samples) - len(mismatches)
    accuracy = correct_count / len(samples)
    first_sample = samples[0]
    return DocumentClassificationEvaluation(
        dataset_version=first_sample.dataset_version,
        prompt_name=first_sample.prompt_name,
        prompt_version=first_sample.prompt_version,
        provider="rizzo-flow",
        model=model,
        sample_count=len(samples),
        correct_count=correct_count,
        accuracy=accuracy,
        minimum_accuracy=minimum_accuracy,
        passed=accuracy >= minimum_accuracy,
        mismatches=mismatches,
    )