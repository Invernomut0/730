"""Add a logical presentation name for archived documents.

Revision ID: 20260925_0002
Revises: 20260925_0001
"""

import sqlalchemy as sa
from alembic import op

revision = "20260925_0002"
down_revision = "20260925_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add the optional deterministic logical filename."""
    op.add_column("documents", sa.Column("logical_name", sa.String(length=255), nullable=True))


def downgrade() -> None:
    """Remove the logical presentation name."""
    op.drop_column("documents", "logical_name")