"""user designation

Revision ID: 0003
Revises: 0002
"""
from alembic import op
import sqlalchemy as sa

revision = '0003'
down_revision = '0002'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('users') as batch:
        batch.add_column(sa.Column('designation', sa.String(length=200), nullable=False, server_default=''))


def downgrade():
    with op.batch_alter_table('users') as batch:
        batch.drop_column('designation')
