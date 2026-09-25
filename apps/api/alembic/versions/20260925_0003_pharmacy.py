"""Add local pharmacy catalog, receipt, and allocation tables.

Revision ID: 20260925_0003
Revises: 20260925_0002
"""

from alembic import op

from app.models.entities import Base

revision = "20260925_0003"
down_revision = "20260925_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create the pharmacy tables from the versioned ORM metadata."""
    Base.metadata.create_all(op.get_bind())


def downgrade() -> None:
    """Drop pharmacy tables in dependency order."""
    for table in ("receipt_lines", "pharmacy_receipts", "prescription_items", "drug_packages"):
        op.drop_table(table)