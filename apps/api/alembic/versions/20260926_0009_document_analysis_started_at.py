"""Track the start of each document analysis for live operator progress.

Revision ID: 20260926_0009
Revises: 20260926_0008
"""

import sqlalchemy as sa
from alembic import op


revision = "20260926_0009"
down_revision = "20260926_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("analysis_started_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("documents", "analysis_started_at")