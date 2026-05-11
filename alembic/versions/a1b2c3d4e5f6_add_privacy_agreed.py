"""add privacy_agreed column

Revision ID: a1b2c3d4e5f6
Revises: f7e2c1d3a4b5
Create Date: 2026-05-11

"""
from alembic import op
import sqlalchemy as sa

revision = 'a1b2c3d4e5f6'
down_revision = 'f7e2c1d3a4b5'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('users', sa.Column('privacy_agreed', sa.Boolean(), nullable=False, server_default='false'))


def downgrade() -> None:
    op.drop_column('users', 'privacy_agreed')
