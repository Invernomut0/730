"""Prevent duplicate prescription-to-invoice relation pairs.

Revision ID: 20260926_0007
Revises: 20260925_0007
"""

from alembic import op


revision = "20260926_0007"
down_revision = "20260925_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        DELETE FROM document_links AS duplicate
        USING document_links AS retained
        WHERE duplicate.source_document_id = retained.source_document_id
          AND duplicate.target_document_id = retained.target_document_id
          AND duplicate.id > retained.id
        """
    )
    op.create_unique_constraint(
        "uq_document_links_source_target",
        "document_links",
        ["source_document_id", "target_document_id"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_document_links_source_target", "document_links", type_="unique")