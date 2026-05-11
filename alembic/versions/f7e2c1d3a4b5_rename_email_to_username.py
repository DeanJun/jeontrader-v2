"""rename email to username

Revision ID: f7e2c1d3a4b5
Revises: c3f1a2b4d5e6
Create Date: 2026-05-11

"""
from alembic import op

revision = 'f7e2c1d3a4b5'
down_revision = 'c3f1a2b4d5e6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column('users', 'email', new_column_name='username')


def downgrade() -> None:
    op.alter_column('users', 'username', new_column_name='email')
