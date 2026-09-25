"""make dark_mode nullable (null = follow device)

Revision ID: ae8e314f1df9
Revises: dae71d6eccf1
Create Date: 2026-09-25 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'ae8e314f1df9'
down_revision = 'dae71d6eccf1'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.alter_column('dark_mode', existing_type=sa.Boolean(), nullable=True)


def downgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.alter_column('dark_mode', existing_type=sa.Boolean(), nullable=False, server_default=sa.false())
