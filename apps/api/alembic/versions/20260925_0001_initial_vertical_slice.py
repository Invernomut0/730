"""Initial schema for the HealthDocs foundation and vertical slice.

Revision ID: 20260925_0001
Revises:
Create Date: 2026-09-25
"""

from alembic import op

from app.models.entities import Base

revision = "20260925_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create the versioned initial schema from the audited ORM metadata."""
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    """Remove all foundation tables in reverse dependency order."""
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
