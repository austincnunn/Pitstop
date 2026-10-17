"""add oidc_subject to users

Revision ID: b7e2d4a9c1f0
Revises: f3a7c9b1d2e4
Create Date: 2026-10-17 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = 'b7e2d4a9c1f0'
down_revision = 'f3a7c9b1d2e4'
branch_labels = None
depends_on = None


def upgrade():
    # _run_schema_migrations() may have added these at app startup already
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    user_columns = [c['name'] for c in inspector.get_columns('users')]
    if 'oidc_subject' not in user_columns:
        op.add_column('users', sa.Column('oidc_subject', sa.String(length=255), nullable=True))

    user_indexes = [idx['name'] for idx in inspector.get_indexes('users')]
    if 'ix_users_oidc_subject' not in user_indexes:
        op.create_index('ix_users_oidc_subject', 'users', ['oidc_subject'], unique=True)


def downgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_index('ix_users_oidc_subject')
        batch_op.drop_column('oidc_subject')
