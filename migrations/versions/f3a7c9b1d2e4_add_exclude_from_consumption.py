"""add exclude_from_consumption to fuel_logs

Revision ID: f3a7c9b1d2e4
Revises: ae8e314f1df9
Create Date: 2026-10-10 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = 'f3a7c9b1d2e4'
down_revision = 'ae8e314f1df9'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('fuel_logs', schema=None) as batch_op:
        batch_op.add_column(sa.Column('exclude_from_consumption', sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade():
    with op.batch_alter_table('fuel_logs', schema=None) as batch_op:
        batch_op.drop_column('exclude_from_consumption')
