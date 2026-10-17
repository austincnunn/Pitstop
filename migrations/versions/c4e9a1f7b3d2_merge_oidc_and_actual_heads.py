"""merge oidc_subject and actual_transaction_id heads

Both migrations were branched from f3a7c9b1d2e4, which left two heads and made
`flask db upgrade` refuse to run.

Revision ID: c4e9a1f7b3d2
Revises: b7e2d4a9c1f0, b8d4e2a6c1f9
Create Date: 2026-10-17 00:00:00.000000
"""

revision = 'c4e9a1f7b3d2'
down_revision = ('b7e2d4a9c1f0', 'b8d4e2a6c1f9')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
