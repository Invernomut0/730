import pytest

from app.commands.evaluate_rizzo import build_parser
from app.models.entities import DocumentType
from app.schemas.calibration import DocumentClassificationDecision
from app.services.calibration import load_document_classification_calibration
from app.services.evaluation import evaluate_document_classification


def test_evaluation_reports_accuracy_and_synthetic_identifiers_only() -> None:
    samples = load_document_classification_calibration()
    decisions = [
        DocumentClassificationDecision(
            document_type=sample.expected_output.document_type,
            confidence=0.99,
        )
        for sample in samples
    ]
    decisions[0] = DocumentClassificationDecision(document_type=DocumentType.UNKNOWN, confidence=0.8)

    report = evaluate_document_classification(samples, decisions, "rizzo-flow", 0.95)

    assert report.accuracy == pytest.approx(11 / 12)
    assert not report.passed
    assert report.mismatches[0].sample_id == "CAL-CLF-001"
    assert report.mismatches[0].expected_document_type == DocumentType.PRESCRIPTION


def test_evaluation_rejects_missing_decisions() -> None:
    samples = load_document_classification_calibration()

    with pytest.raises(ValueError, match="must match"):
        evaluate_document_classification(samples, [], "rizzo-flow", 0.95)


def test_evaluate_rizzo_parser_accepts_threshold_and_report_path() -> None:
    arguments = build_parser().parse_args(["--minimum-accuracy", "0.9", "--output", "build/report.json"])

    assert arguments.minimum_accuracy == 0.9
    assert str(arguments.output) == "build/report.json"