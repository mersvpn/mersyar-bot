"""add user info fields

Revision ID: 20251025_user_info
Revises: PUT_YOUR_LAST_REVISION_HERE
Create Date: 2025-10-25 05:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = '20251025_user_info'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('users', sa.Column('admin_note', sa.Text(), nullable=True))
    op.add_column('users', sa.Column('last_activity', sa.TIMESTAMP(), nullable=True))

def downgrade():
    op.drop_column('users', 'last_activity')
    op.drop_column('users', 'admin_note')
