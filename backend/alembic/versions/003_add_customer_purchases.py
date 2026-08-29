"""Add customer purchases table

Revision ID: 003_add_customer_purchases
Revises: 002_create_bevi_stoq_tables
Create Date: 2026-08-29 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = '003_add_customer_purchases'
down_revision = '002_create_bevi_stoq_tables'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Customer purchases table
    op.create_table(
        'bs_customer_purchases',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('customer_id', sa.Integer(), nullable=True),
        sa.Column('customer_name', sa.String(200), nullable=False),
        sa.Column('product_id', sa.Integer(), nullable=False),
        sa.Column('quantity', sa.Float(), nullable=False),
        sa.Column('unit', sa.String(50), nullable=True),
        sa.Column('purchase_date', sa.DateTime(timezone=True), nullable=False),
        sa.Column('payment_status', sa.String(50), nullable=False, server_default='pending'),
        sa.Column('payment_method', sa.String(100), nullable=True),
        sa.Column('amount', sa.Float(), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('created_by_user_id', sa.Integer(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_by_user_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['customer_id'], ['bevigrow.contacts.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['product_id'], ['bevigrow.bs_products.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['updated_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.Index('ix_bs_customer_purchases_product_id', 'product_id'),
        sa.Index('ix_bs_customer_purchases_payment_status', 'payment_status'),
        sa.Index('ix_bs_customer_purchases_purchase_date', 'purchase_date'),
        schema='bevigrow'
    )


def downgrade() -> None:
    op.drop_table('bs_customer_purchases', schema='bevigrow')
