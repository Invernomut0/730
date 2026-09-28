"""Persist operator decisions for primary LLM relationship inference.

Revision ID: 20260928_0010
Revises: 20260926_0009
"""

import sqlalchemy as sa
from alembic import op


revision = "20260928_0010"
down_revision = "20260926_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "association_feedback",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source_document_id", sa.Uuid(), nullable=False),
        sa.Column("target_document_id", sa.Uuid(), nullable=False),
        sa.Column("decision", sa.String(length=16), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["source_document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["target_document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_association_feedback_source_document_id", "association_feedback", ["source_document_id"])
    op.create_index("ix_association_feedback_target_document_id", "association_feedback", ["target_document_id"])


def downgrade() -> None:
    op.drop_index("ix_association_feedback_target_document_id", table_name="association_feedback")
    op.drop_index("ix_association_feedback_source_document_id", table_name="association_feedback")
    op.drop_table("association_feedback")