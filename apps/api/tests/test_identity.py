import pytest

from app.services.identity import normalize_fiscal_code


def test_normalize_fiscal_code_removes_whitespace_and_uppercases() -> None:
    assert normalize_fiscal_code(" rssmra80a01h501u ") == "RSSMRA80A01H501U"


def test_normalize_fiscal_code_rejects_invalid_shape() -> None:
    with pytest.raises(ValueError, match="16 letters or digits"):
        normalize_fiscal_code("NOT-VALID")
