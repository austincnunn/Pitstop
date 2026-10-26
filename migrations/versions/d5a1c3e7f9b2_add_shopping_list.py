"""add shopping list projects/items, receipt link and show_menu_shopping

Revision ID: d5a1c3e7f9b2
Revises: c4e9a1f7b3d2
Create Date: 2026-10-25 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = 'd5a1c3e7f9b2'
down_revision = 'c4e9a1f7b3d2'
branch_labels = None
depends_on = None


def upgrade():
    # Tables may already exist: app startup runs db.create_all()
    inspector = sa.inspect(op.get_bind())
    tables = inspector.get_table_names()

    if 'shopping_projects' not in tables:
        op.create_table(
            'shopping_projects',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('vehicle_id', sa.Integer(), sa.ForeignKey('vehicles.id'), nullable=False),
            sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
            sa.Column('name', sa.String(length=200), nullable=False),
            sa.Column('category', sa.String(length=50), nullable=False),
            sa.Column('notes', sa.Text(), nullable=True),
            sa.Column('expense_id', sa.Integer(), sa.ForeignKey('expenses.id'), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
        )

    if 'shopping_items' not in tables:
        op.create_table(
            'shopping_items',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('project_id', sa.Integer(), sa.ForeignKey('shopping_projects.id'), nullable=False),
            sa.Column('name', sa.String(length=200), nullable=False),
            sa.Column('part_number', sa.String(length=100), nullable=True),
            sa.Column('url', sa.String(length=500), nullable=True),
            sa.Column('quantity', sa.Integer(), nullable=True),
            sa.Column('est_price', sa.Float(), nullable=True),
            sa.Column('notes', sa.Text(), nullable=True),
            sa.Column('is_purchased', sa.Boolean(), nullable=True),
            sa.Column('purchased_price', sa.Float(), nullable=True),
            sa.Column('purchased_date', sa.Date(), nullable=True),
            sa.Column('vendor', sa.String(length=100), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
        )

    attachment_columns = [c['name'] for c in inspector.get_columns('attachments')]
    if 'shopping_item_id' not in attachment_columns:
        with op.batch_alter_table('attachments', schema=None) as batch_op:
            batch_op.add_column(sa.Column('shopping_item_id', sa.Integer(), nullable=True))
            batch_op.create_foreign_key('fk_attachments_shopping_item_id', 'shopping_items',
                                        ['shopping_item_id'], ['id'])

    user_columns = [c['name'] for c in inspector.get_columns('users')]
    if 'show_menu_shopping' not in user_columns:
        op.add_column('users', sa.Column('show_menu_shopping', sa.Boolean(), nullable=True,
                                         server_default=sa.true()))


def downgrade():
    inspector = sa.inspect(op.get_bind())

    user_columns = [c['name'] for c in inspector.get_columns('users')]
    if 'show_menu_shopping' in user_columns:
        with op.batch_alter_table('users', schema=None) as batch_op:
            batch_op.drop_column('show_menu_shopping')

    attachment_columns = [c['name'] for c in inspector.get_columns('attachments')]
    if 'shopping_item_id' in attachment_columns:
        # The FK is unnamed if the column came from db.create_all() or the startup column patcher
        fk_names = [fk['name'] for fk in inspector.get_foreign_keys('attachments')]
        with op.batch_alter_table('attachments', schema=None) as batch_op:
            if 'fk_attachments_shopping_item_id' in fk_names:
                batch_op.drop_constraint('fk_attachments_shopping_item_id', type_='foreignkey')
            batch_op.drop_column('shopping_item_id')

    tables = inspector.get_table_names()
    if 'shopping_items' in tables:
        op.drop_table('shopping_items')
    if 'shopping_projects' in tables:
        op.drop_table('shopping_projects')
