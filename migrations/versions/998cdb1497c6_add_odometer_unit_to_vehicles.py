"""add odometer_unit to vehicles

Revision ID: 998cdb1497c6
Revises:
Create Date: 2026-02-19 20:44:52.486701

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '998cdb1497c6'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('vehicles', schema=None) as batch_op:
        batch_op.add_column(sa.Column('odometer_unit', sa.String(length=10), nullable=True))


def downgrade():
    with op.batch_alter_table('vehicles', schema=None) as batch_op:
        batch_op.drop_column('odometer_unit')
