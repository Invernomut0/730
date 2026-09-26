from datetime import date
from uuid import uuid4

from app.services.linking import score_prescription_invoice


def test_matching_prescription_and_invoice_auto_confirm() -> None:
    patient = uuid4()
    candidate = score_prescription_invoice(
        patient,
        patient,
        date(2026, 3, 1),
        date(2026, 3, 5),
        ["visita ortopedica"],
        ["Visita ortopedica privata"],
    )
    assert candidate.score >= 0.95
    assert candidate.conflicts == []
    assert "same_patient" in candidate.evidence
    assert "service_matches_prescription" in candidate.evidence


def test_explicit_patient_mismatch_never_auto_links() -> None:
    candidate = score_prescription_invoice(
        uuid4(),
        uuid4(),
        date(2026, 3, 1),
        date(2026, 3, 5),
        ["visita ortopedica"],
        ["Visita ortopedica"],
    )
    assert candidate.score == 0
    assert candidate.conflicts == ["different_patient"]


def test_invoice_before_prescription_is_never_a_link_candidate() -> None:
    patient = uuid4()
    candidate = score_prescription_invoice(
        patient,
        patient,
        date(2026, 9, 2),
        date(2026, 4, 14),
        ["visita specialistica"],
        ["Visita specialistica"],
    )

    assert candidate.score == 0
    assert candidate.evidence == ["same_patient"]
    assert candidate.conflicts == ["invoice_before_prescription"]


def test_invoice_outside_thirty_day_window_is_never_a_link_candidate() -> None:
    patient = uuid4()
    candidate = score_prescription_invoice(
        patient,
        patient,
        date(2026, 1, 23),
        date(2026, 4, 14),
        ["visita specialistica"],
        ["Visita specialistica"],
    )

    assert candidate.score == 0
    assert candidate.evidence == ["same_patient"]
    assert candidate.conflicts == ["invoice_outside_link_window"]
