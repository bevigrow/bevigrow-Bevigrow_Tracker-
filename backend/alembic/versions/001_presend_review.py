"""Add Pre-Send Review and Resend Approval

Revision ID: 001_presend_review
Revises:
Create Date: 2026-08-26 11:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '001_presend_review'
down_revision = '000_create_campaign_tables'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create ApprovedResend table
    op.create_table(
        'approved_resends',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('original_send_id', sa.Integer(), nullable=True, index=True),
        sa.Column('original_send_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('campaign_id', sa.Integer(), nullable=False, index=True),
        sa.Column('target_id', sa.Integer(), nullable=False, index=True),
        sa.Column('email', sa.String(255), nullable=False, index=True),
        sa.Column('company_name', sa.String(200), nullable=False),
        sa.Column('original_company_name', sa.String(200), nullable=True),
        sa.Column('contact_person', sa.String(150), nullable=True),
        sa.Column('country', sa.String(100), nullable=True),
        sa.Column('original_subject', sa.String(300), nullable=True),
        sa.Column('new_subject', sa.String(300), nullable=True),
        sa.Column('original_body_preview', sa.Text(), nullable=True),
        sa.Column('new_body_preview', sa.Text(), nullable=True),
        sa.Column('reason', sa.String(20), nullable=False, server_default='other'),
        sa.Column('reason_notes', sa.String(500), nullable=True),
        sa.Column('approved_by_id', sa.Integer(), nullable=False),
        sa.Column('approved_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('resend_status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('new_send_id', sa.Integer(), nullable=True, index=True),
        sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('error_message', sa.String(400), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['campaign_id'], ['campaigns.id']),
        sa.ForeignKeyConstraint(['target_id'], ['campaign_targets.id']),
        sa.ForeignKeyConstraint(['approved_by_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        schema='bevigrow'
    )

    # Add columns to campaign_targets
    op.add_column(
        'campaign_targets',
        sa.Column('is_resend_approved', sa.Boolean(), nullable=False, server_default='false'),
        schema='bevigrow'
    )
    op.add_column(
        'campaign_targets',
        sa.Column('resend_reason', sa.String(100), nullable=True),
        schema='bevigrow'
    )
    op.add_column(
        'campaign_targets',
        sa.Column('resend_notes', sa.String(500), nullable=True),
        schema='bevigrow'
    )
    op.add_column(
        'campaign_targets',
        sa.Column('approved_by_id', sa.Integer(), nullable=True),
        schema='bevigrow'
    )
    op.add_column(
        'campaign_targets',
        sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
        schema='bevigrow'
    )

    # Add foreign key for approved_by_id
    op.create_foreign_key(
        'fk_campaign_targets_approved_by_id',
        'campaign_targets',
        'users',
        ['approved_by_id'],
        ['id'],
        ondelete='SET NULL',
        schema='bevigrow'
    )


def downgrade() -> None:
    # Drop foreign key
    op.drop_constraint(
        'fk_campaign_targets_approved_by_id',
        'campaign_targets',
        schema='bevigrow'
    )

    # Drop columns from campaign_targets
    op.drop_column('campaign_targets', 'approved_at', schema='bevigrow')
    op.drop_column('campaign_targets', 'approved_by_id', schema='bevigrow')
    op.drop_column('campaign_targets', 'resend_notes', schema='bevigrow')
    op.drop_column('campaign_targets', 'resend_reason', schema='bevigrow')
    op.drop_column('campaign_targets', 'is_resend_approved', schema='bevigrow')

    # Drop ApprovedResend table
    op.drop_table('approved_resends', schema='bevigrow')
