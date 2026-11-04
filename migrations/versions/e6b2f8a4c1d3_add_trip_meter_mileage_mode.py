"""add trip meter mileage mode

Revision ID: e6b2f8a4c1d3
Revises: d5a1c3e7f9b2
Create Date: 2026-10-29 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = 'e6b2f8a4c1d3'
down_revision = 'd5a1c3e7f9b2'
branch_labels = None
depends_on = None


def upgrade():
    # Existing vehicles stay on odometer mode and existing fuel logs stay odometer entries.
    # Columns may already exist: app startup adds them via _run_schema_migrations.
    inspector = sa.inspect(op.get_bind())
    vehicle_cols = {c['name'] for c in inspector.get_columns('vehicles')}
    fuel_cols = {c['name'] for c in inspector.get_columns('fuel_logs')}

    with op.batch_alter_table('vehicles', schema=None) as batch_op:
        if 'mileage_mode' not in vehicle_cols:
            batch_op.add_column(sa.Column('mileage_mode', sa.String(length=10), nullable=False, server_default='odometer'))
    with op.batch_alter_table('fuel_logs', schema=None) as batch_op:
        if 'trip_reading' not in fuel_cols:
            batch_op.add_column(sa.Column('trip_reading', sa.Float(), nullable=True))
        if 'distance_unknown' not in fuel_cols:
            batch_op.add_column(sa.Column('distance_unknown', sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade():
    with op.batch_alter_table('fuel_logs', schema=None) as batch_op:
        batch_op.drop_column('distance_unknown')
        batch_op.drop_column('trip_reading')
    with op.batch_alter_table('vehicles', schema=None) as batch_op:
        batch_op.drop_column('mileage_mode')
