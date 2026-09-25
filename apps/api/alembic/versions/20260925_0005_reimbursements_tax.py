"""Add reimbursement and tax ledger tables.

Revision ID: 20260925_0005
Revises: 20260925_0004
"""
from alembic import op
from app.models.entities import Base

revision = "20260925_0005"
down_revision = "20260925_0004"
branch_labels = None
depends_on = None

def upgrade() -> None:
    Base.metadata.create_all(op.get_bind())

def downgrade() -> None:
    for table in ("tax_allocations", "payment_evidence", "tax_rule_sets", "reimbursement_allocations", "reimbursements"):
        op.drop_table(table)