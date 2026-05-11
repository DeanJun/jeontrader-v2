"""add settings table

Revision ID: c3f1a2b4d5e6
Revises: 8db656abf9d7
Create Date: 2026-05-11

"""
from alembic import op
import sqlalchemy as sa

revision = 'c3f1a2b4d5e6'
down_revision = '8db656abf9d7'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'settings',
        sa.Column('key', sa.String(100), primary_key=True),
        sa.Column('value', sa.Text, nullable=False),
    )
    op.execute("INSERT INTO settings (key, value) VALUES ('invite_code', 'dnt1!')")


def downgrade() -> None:
    op.drop_table('settings')
