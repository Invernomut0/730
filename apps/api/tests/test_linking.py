"""Temporal integrity checks for LLM-assisted relationship inference."""

from datetime import date

from app.services.eventing import is_temporally_possible


def test_invoice_before_prescription_is_never_an_llm_candidate() -> None:
	assert not is_temporally_possible(date(2026, 1, 23), date(2026, 1, 20))


def test_same_day_or_later_invoice_is_temporally_possible() -> None:
	assert is_temporally_possible(date(2026, 1, 23), date(2026, 1, 23))
	assert is_temporally_possible(date(2026, 1, 23), date(2026, 1, 24))
