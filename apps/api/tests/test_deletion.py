from pathlib import Path
from uuid import uuid4

from app.db.session import SessionLocal
from app.models.entities import Document, DocumentPage, Household, HouseholdMember
from app.services.deletion import delete_document_group, delete_household
from app.services.thumbnails import thumbnail_path


def test_delete_document_group_removes_records_and_local_artifacts(tmp_path: Path) -> None:
    database = SessionLocal()
    document_id = None
    storage_key = f"originals/test/{uuid4()}.pdf"
    sha256 = "d" * 64
    try:
        document = Document(
            original_filename="synthetic-delete.pdf",
            mime_type="application/pdf",
            byte_size=1,
            sha256=sha256,
            storage_key=storage_key,
        )
        database.add(document)
        database.flush()
        document_id = document.id
        database.add(DocumentPage(document_id=document.id, page_number=1, text="Synthetic", source="native"))
        database.commit()
        original = tmp_path / storage_key
        original.parent.mkdir(parents=True)
        original.write_bytes(b"%PDF-1.4\n")
        preview = thumbnail_path(tmp_path, sha256)
        preview.parent.mkdir(parents=True)
        preview.write_bytes(b"preview")

        assert delete_document_group(database, tmp_path, document.id) == 1
        assert database.get(Document, document.id) is None
        assert not original.exists()
        assert not preview.exists()
    finally:
        if document_id and database.get(Document, document_id):
            database.delete(database.get(Document, document_id))
            database.commit()
        database.close()


def test_delete_household_removes_members() -> None:
    database = SessionLocal()
    household_id = member_id = None
    try:
        household = Household(name=f"Synthetic delete family {uuid4()}")
        database.add(household)
        database.flush()
        household_id = household.id
        member = HouseholdMember(household_id=household.id, first_name="Laura", last_name="Bianchi")
        database.add(member)
        database.commit()
        member_id = member.id

        assert delete_household(database, Path("/tmp"), household.id) == 0
        assert database.get(Household, household.id) is None
        assert database.get(HouseholdMember, member.id) is None
    finally:
        if member_id and database.get(HouseholdMember, member_id):
            database.delete(database.get(HouseholdMember, member_id))
        if household_id and database.get(Household, household_id):
            database.delete(database.get(Household, household_id))
        database.commit()
        database.close()