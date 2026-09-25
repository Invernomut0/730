"""Add structured local medical report persistence.

Revision ID: 20260925_0007
Revises: 20260925_0006
"""
from alembic import op
from app.models.entities import Base

revision = "20260925_0007"
down_revision = "20260925_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    Base.metadata.create_all(op.get_bind())


def downgrade() -> None:
    op.drop_table("medical_reports")