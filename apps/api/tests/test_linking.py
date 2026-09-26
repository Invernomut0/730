from datetime import date
from uuid import uuid4

from app.services.linking import is_patient_date_review_candidate, score_prescription_invoice


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


def test_incompatible_specialties_never_link_on_generic_visit_word() -> None:
    patient = uuid4()
    candidate = score_prescription_invoice(
        patient,
        patient,
        date(2026, 1, 15),
        date(2026, 1, 20),
        ["visita gastroenterologica (controllo)"],
        ["visita multidisciplinare"],
    )

    assert candidate.score == 0
    assert candidate.conflicts == ["incompatible_clinical_specialty"]
    assert "service_matches_prescription" not in candidate.evidence


def test_all_itemized_drugs_and_lab_tests_must_match_invoice_lines() -> None:
    patient = uuid4()
    candidate = score_prescription_invoice(
        patient,
        patient,
        date(2026, 2, 1),
        date(2026, 2, 4),
        [],
        ["Tachipirina 1000", "Augmentin 875", "Emocromo completo", "AST"],
        ["Tachipirina 1000 mg", "Augmentin 875 mg"],
        ["Emocromo completo", "AST"],
        ["Tachipirina 1000", "Augmentin 875"],
        ["Emocromo completo", "AST"],
    )

    assert candidate.score >= 0.95
    assert "all_prescribed_drugs_match_invoice" in candidate.evidence
    assert "all_requested_lab_tests_match_invoice" in candidate.evidence


def test_missing_one_itemized_lab_test_blocks_invoice_link() -> None:
    patient = uuid4()
    candidate = score_prescription_invoice(
        patient,
        patient,
        date(2026, 2, 1),
        date(2026, 2, 4),
        [],
        ["Emocromo completo"],
        [],
        ["Emocromo completo", "TSH"],
        [],
        ["Emocromo completo"],
    )

    assert candidate.score == 0
    assert candidate.conflicts == ["requested_lab_tests_missing_from_invoice"]


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


def test_same_patient_and_date_window_without_service_match_creates_review_candidate() -> None:
    patient = uuid4()

    candidate = score_prescription_invoice(
        patient,
        patient,
        date(2026, 5, 6),
        date(2026, 5, 9),
        ["visita gastroenterologica"],
        ["iniezione terapeutica"],
    )

    assert 0.44 < candidate.score < 0.46
    assert is_patient_date_review_candidate(candidate)
