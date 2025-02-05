"""Add user_searches table

Revision ID: add_user_searches
Revises: 
Create Date: 2024-03-19 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_user_searches'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('user_searches',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('telegram_id', sa.Integer(), nullable=True),
        sa.Column('search_query', sa.String(), nullable=False),
        sa.Column('structured_preferences', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_user_searches_id'), 'user_searches', ['id'], unique=False)
    op.create_index(op.f('ix_user_searches_telegram_id'), 'user_searches', ['telegram_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_user_searches_telegram_id'), table_name='user_searches')
    op.drop_index(op.f('ix_user_searches_id'), table_name='user_searches')
    op.drop_table('user_searches') 