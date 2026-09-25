"""Add the pharmacy patient/payer review enum value.

Revision ID: 20260925_0004
Revises: 20260925_0003
"""

from alembic import op

revision = "20260925_0004"
down_revision = "20260925_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Extend PostgreSQL's existing review enum safely."""
    op.execute("ALTER TYPE reviewtype ADD VALUE IF NOT EXISTS 'PATIENT_PAYER_CONFLICT'")


def downgrade() -> None:
    """Enum values cannot be safely removed on PostgreSQL without table rewrites."""
