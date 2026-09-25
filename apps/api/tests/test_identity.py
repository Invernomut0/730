import pytest
from sqlalchemy import delete
from uuid import uuid4

from app.db.session import SessionLocal
from app.models.entities import Household, HouseholdMember
from app.services.identity import normalize_fiscal_code, resolve_patient


def test_normalize_fiscal_code_removes_whitespace_and_uppercases() -> None:
    assert normalize_fiscal_code(" rssmra80a01h501u ") == "RSSMRA80A01H501U"


def test_normalize_fiscal_code_rejects_invalid_shape() -> None:
    with pytest.raises(ValueError, match="16 letters or digits"):
        normalize_fiscal_code("NOT-VALID")


def test_unique_reversed_name_resolves_with_unmatched_fiscal_code_conflict() -> None:
    database = SessionLocal()
    household_id = member_id = None
    try:
        household = Household(name="Synthetic identity household")
        database.add(household)
        database.flush()
        household_id = household.id
        member = HouseholdMember(household_id=household.id, first_name="Giulia", last_name="Ferrari", fiscal_code=f"TEST{uuid4().hex[:12].upper()}")
        database.add(member)
        database.commit()
        member_id = member.id

        resolution = resolve_patient(database, "BRRRCR77T28L872J", "FERRARI GIULIA")

        assert resolution.member_id == member.id
        assert resolution.conflict
        assert resolution.evidence == ["reversed_full_name", "unmatched_fiscal_code"]
    finally:
        if member_id:
            database.execute(delete(HouseholdMember).where(HouseholdMember.id == member_id))
        if household_id:
            database.execute(delete(Household).where(Household.id == household_id))
        database.commit()
        database.close()
