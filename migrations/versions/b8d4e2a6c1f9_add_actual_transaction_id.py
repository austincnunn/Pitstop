"""add actual_transaction_id to expenses

Revision ID: b8d4e2a6c1f9
Revises: f3a7c9b1d2e4
Create Date: 2026-10-17 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = 'b8d4e2a6c1f9'
down_revision = 'f3a7c9b1d2e4'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('expenses', schema=None) as batch_op:
        batch_op.add_column(sa.Column('actual_transaction_id', sa.String(length=64), nullable=True))
        batch_op.create_unique_constraint('uq_expenses_actual_transaction_id', ['actual_transaction_id'])


def downgrade():
    with op.batch_alter_table('expenses', schema=None) as batch_op:
        batch_op.drop_constraint('uq_expenses_actual_transaction_id', type_='unique')
        batch_op.drop_column('actual_transaction_id')
