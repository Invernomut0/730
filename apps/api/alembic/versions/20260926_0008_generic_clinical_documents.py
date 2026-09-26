"""Add persisted generic clinical document extraction.

Revision ID: 20260926_0008
Revises: 20260926_0007
"""

from alembic import op
from app.models.entities import Base

revision = "20260926_0008"
down_revision = "20260926_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    Base.metadata.create_all(op.get_bind())


def downgrade() -> None:
    op.drop_table("clinical_documents")