from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.db.session import SessionLocal
from app.main import app
from app.models.entities import Household, HouseholdMember


def test_create_and_list_household_member_against_postgres() -> None:
    household_name = f"Synthetic Household {uuid4()}"
    household_id: str | None = None
    member_id: str | None = None
    try:
        with TestClient(app) as client:
            household = client.post("/api/v1/households", json={"name": household_name})
            assert household.status_code == 201
            household_id = household.json()["id"]
            member = client.post(
                "/api/v1/household-members",
                json={
                    "household_id": household_id,
                    "first_name": "Laura",
                    "last_name": "Bianchi",
                    "fiscal_code": "tstfam00a00a000a",
                    "relationship_type": "daughter",
                },
            )
            assert member.status_code == 201
            member_id = member.json()["id"]
            households = client.get("/api/v1/households")
            assert households.status_code == 200
            created = next(item for item in households.json() if item["id"] == household_id)
            assert created["members"] == [
                {
                    "id": member_id,
                    "first_name": "Laura",
                    "last_name": "Bianchi",
                    "fiscal_code": "TSTFAM00A00A000A",
                    "relationship_type": "daughter",
                }
            ]
    finally:
        database = SessionLocal()
        try:
            if member_id:
                database.execute(delete(HouseholdMember).where(HouseholdMember.id == member_id))
            if household_id:
                database.execute(delete(Household).where(Household.id == household_id))
            database.commit()
        finally:
            database.close()
