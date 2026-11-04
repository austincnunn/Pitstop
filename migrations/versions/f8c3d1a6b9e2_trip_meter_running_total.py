"""trip meter readings are distance since last fill-up: recompute derived odometers

Revision ID: f8c3d1a6b9e2
Revises: e6b2f8a4c1d3
Create Date: 2026-11-03 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = 'f8c3d1a6b9e2'
down_revision = 'e6b2f8a4c1d3'
branch_labels = None
depends_on = None


def upgrade():
    # Frozen copy of Vehicle.rebuild_trip_odometers (don't import app models in migrations)
    conn = op.get_bind()
    vehicle_ids = [r[0] for r in conn.execute(sa.text(
        'SELECT DISTINCT vehicle_id FROM fuel_logs WHERE trip_reading IS NOT NULL'))]
    for vehicle_id in vehicle_ids:
        logs = conn.execute(sa.text(
            'SELECT id, odometer, trip_reading, is_full_tank, exclude_from_consumption '
            'FROM fuel_logs WHERE vehicle_id = :v ORDER BY date, id'), {'v': vehicle_id}).mappings().all()
        prev_odometer = prev_trip = None
        pending_break = False
        for log in logs:
            odometer = log['odometer']
            if log['trip_reading'] is not None:
                odometer = round((prev_odometer or 0) + log['trip_reading'], 1)
            elif prev_trip is not None:
                pending_break = True
            unknown = pending_break and bool(log['is_full_tank']) and not log['exclude_from_consumption']
            if unknown:
                pending_break = False
            conn.execute(sa.text('UPDATE fuel_logs SET odometer = :o, distance_unknown = :u WHERE id = :id'),
                         {'o': odometer, 'u': unknown, 'id': log['id']})
            prev_odometer, prev_trip = odometer, log['trip_reading']


def downgrade():
    pass
