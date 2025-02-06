"""create_job_tables

Revision ID: 2024_02_06_01
Revises: cad4ffb43d2f
Create Date: 2025-02-06 00:01:23.406173

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '2024_02_06_01'
down_revision: Union[str, None] = 'cad4ffb43d2f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create accounting firms table
    op.create_table('jobsapp_accountingfirm',
        sa.Column('id', sa.INTEGER(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('slug', sa.String(255), nullable=False),
        sa.Column('link', sa.String(255), nullable=False),
        sa.Column('twitter_link', sa.String(255), nullable=True),
        sa.Column('linkedin_link', sa.String(255), nullable=True),
        sa.Column('location', sa.String(255), nullable=True),
        sa.Column('ranking', sa.INTEGER(), nullable=True),
        sa.Column('about', sa.TEXT(), nullable=True),
        sa.Column('script', sa.TEXT(), nullable=True),
        sa.Column('logo', sa.String(255), nullable=True),
        sa.Column('country', sa.String(255), nullable=True),
        sa.Column('jobs_count', sa.INTEGER(), nullable=True),
        sa.Column('last_scraped', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id', name='jobsapp_accountingfirm_pkey'),
        sa.UniqueConstraint('slug', name='jobsapp_accountingfirm_slug_key')
    )

    # Create jobs table
    op.create_table('jobsapp_job',
        sa.Column('id', sa.INTEGER(), autoincrement=True, nullable=False),
        sa.Column('firm_id', sa.INTEGER(), nullable=False),
        sa.Column('job_title', sa.String(255), nullable=False),
        sa.Column('seniority', sa.String(255), nullable=True),
        sa.Column('service', sa.String(255), nullable=True),
        sa.Column('industry', sa.String(255), nullable=True),
        sa.Column('location', sa.String(255), nullable=True),
        sa.Column('employment', sa.String(255), nullable=True),
        sa.Column('salary', sa.String(255), nullable=True),
        sa.Column('description', sa.TEXT(), nullable=True),
        sa.Column('link', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('date_published', sa.DateTime(), nullable=True),
        sa.Column('req_no', sa.String(255), nullable=True),
        sa.ForeignKeyConstraint(['firm_id'], ['jobsapp_accountingfirm.id'], name='jobsapp_job_firm_id_fkey'),
        sa.PrimaryKeyConstraint('id', name='jobsapp_job_pkey')
    )

    # Create indexes
    op.create_index('idx_jobsapp_job_firm_id', 'jobsapp_job', ['firm_id'], unique=False)
    op.create_index('idx_jobsapp_job_location', 'jobsapp_job', ['location'], unique=False)
    op.create_index('idx_jobsapp_job_seniority', 'jobsapp_job', ['seniority'], unique=False)
    op.create_index('idx_jobsapp_job_service', 'jobsapp_job', ['service'], unique=False)


def downgrade() -> None:
    # Drop indexes
    op.drop_index('idx_jobsapp_job_service', table_name='jobsapp_job')
    op.drop_index('idx_jobsapp_job_seniority', table_name='jobsapp_job')
    op.drop_index('idx_jobsapp_job_location', table_name='jobsapp_job')
    op.drop_index('idx_jobsapp_job_firm_id', table_name='jobsapp_job')

    # Drop tables
    op.drop_table('jobsapp_job')
    op.drop_table('jobsapp_accountingfirm') 