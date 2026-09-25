"""Add local pre-filled 730 import and normalized row tables.

Revision ID: 20260925_0006
Revises: 20260925_0005
"""
from alembic import op
from app.models.entities import Base

revision = "20260925_0006"
down_revision = "20260925_0005"
branch_labels = None
depends_on = None

def upgrade() -> None:
    Base.metadata.create_all(op.get_bind())

def downgrade() -> None:
    op.drop_table("precompiled_730_rows")
    op.drop_table("precompiled_730_imports")