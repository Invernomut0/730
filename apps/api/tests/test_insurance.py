from decimal import Decimal

from app.models.entities import ExpenseDocument
from app.services.insurance import coverage_amount, expense_amount


def test_coverage_amount_applies_deductible_coinsurance_and_cap() -> None:
    assert coverage_amount(Decimal(180), {"in_network_deductible_eur": 15, "annual_limit_eur": 3000}, True) == Decimal(165)
    assert coverage_amount(Decimal(100), {"out_network_coinsurance_percent": 20, "out_network_minimum_eur": 35}) == Decimal(65)
    assert coverage_amount(Decimal(50000), {"coinsurance_percent": 15, "coinsurance_cap_eur": 4000, "annual_household_limit_eur": 300000}) == Decimal(46000)


def test_expense_amount_falls_back_to_the_extracted_invoice_total() -> None:
    expense = ExpenseDocument(extraction={"total_amount": "180.50"})

    assert expense_amount(expense) == Decimal("180.50")