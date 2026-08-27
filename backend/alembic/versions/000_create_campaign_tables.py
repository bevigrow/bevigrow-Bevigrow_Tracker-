"""Create base campaign tables - campaigns and campaign_targets

Revision ID: 000_create_campaign_tables
Revises:
Create Date: 2026-08-27 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = '000_create_campaign_tables'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create campaigns table
    op.create_table(
        'campaigns',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(300), nullable=False),
        sa.Column('status', sa.String(50), nullable=False, server_default='draft'),
        sa.Column('mode', sa.String(50), nullable=False, server_default='manual'),
        sa.Column('daily_limit', sa.Integer(), nullable=False, server_default='50'),
        sa.Column('template_id', sa.Integer(), nullable=True),
        sa.Column('source_filename', sa.String(255), nullable=True),
        sa.Column('allow_recontact', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('last_target_id', sa.Integer(), nullable=True),
        sa.Column('last_activity_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('owner_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['owner_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        schema='bevigrow'
    )

    # Create campaign_targets table
    op.create_table(
        'campaign_targets',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('campaign_id', sa.Integer(), nullable=False),
        sa.Column('position', sa.Integer(), nullable=False),
        sa.Column('company_name', sa.String(300), nullable=False),
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('contact_person', sa.String(150), nullable=True),
        sa.Column('website', sa.String(255), nullable=True),
        sa.Column('country', sa.String(100), nullable=True),
        sa.Column('location', sa.String(100), nullable=True),
        sa.Column('linkedin', sa.String(255), nullable=True),
        sa.Column('contact_form', sa.String(255), nullable=True),
        sa.Column('phone', sa.String(50), nullable=True),
        sa.Column('category', sa.String(100), nullable=True),
        sa.Column('extra', sa.Text(), nullable=True),
        sa.Column('normalized_company', sa.String(300), nullable=True),
        sa.Column('normalized_email', sa.String(255), nullable=True),
        sa.Column('domain', sa.String(255), nullable=True),
        sa.Column('skip_reason', sa.String(255), nullable=True),
        sa.Column('state', sa.String(50), nullable=False, server_default='pending'),
        sa.Column('attempt_no', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_error', sa.String(400), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['campaign_id'], ['bevigrow.campaigns'], ['id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        schema='bevigrow'
    )

    # Create indexes
    op.create_index('ix_campaigns_owner_id', 'campaigns', ['owner_id'], schema='bevigrow')
    op.create_index('ix_campaigns_status', 'campaigns', ['status'], schema='bevigrow')
    op.create_index('ix_campaign_targets_campaign_id', 'campaign_targets', ['campaign_id'], schema='bevigrow')
    op.create_index('ix_campaign_targets_state', 'campaign_targets', ['state'], schema='bevigrow')
    op.create_index('ix_campaign_targets_email', 'campaign_targets', ['email'], schema='bevigrow')


def downgrade() -> None:
    op.drop_table('campaign_targets', schema='bevigrow')
    op.drop_table('campaigns', schema='bevigrow')
