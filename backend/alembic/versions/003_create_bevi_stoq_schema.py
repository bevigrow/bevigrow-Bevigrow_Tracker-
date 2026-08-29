"""Create complete Bevi Stoq inventory management schema

Revision ID: 003_create_bevi_stoq_schema
Revises: 002_presend_review
Create Date: 2026-08-29 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = '003_create_bevi_stoq_schema'
down_revision = '002_presend_review'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Categories table
    op.create_table(
        'bs_categories',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(150), nullable=False, unique=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('created_by_user_id', sa.Integer(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_by_user_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['updated_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.Index('ix_bs_categories_name', 'name'),
        sa.Index('ix_bs_categories_active', 'active'),
        schema='bevigrow'
    )

    # Products table
    op.create_table(
        'bs_products',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('category_id', sa.Integer(), nullable=False),
        sa.Column('default_unit', sa.String(50), nullable=False),
        sa.Column('low_stock_threshold', sa.Float(), nullable=False, server_default='0'),
        sa.Column('active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('created_by_user_id', sa.Integer(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_by_user_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['category_id'], ['bevigrow.bs_categories.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['updated_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.Index('ix_bs_products_name', 'name'),
        sa.Index('ix_bs_products_active', 'active'),
        sa.Index('ix_bs_products_category_id', 'category_id'),
        schema='bevigrow'
    )

    # Locations table
    op.create_table(
        'bs_locations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(150), nullable=False, unique=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('created_by_user_id', sa.Integer(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_by_user_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['updated_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.Index('ix_bs_locations_name', 'name'),
        sa.Index('ix_bs_locations_active', 'active'),
        schema='bevigrow'
    )

    # Inventory table (stock levels by product/location)
    op.create_table(
        'bs_inventory',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('product_id', sa.Integer(), nullable=False),
        sa.Column('location_id', sa.Integer(), nullable=False),
        sa.Column('physical_stock', sa.Float(), nullable=False, server_default='0'),
        sa.Column('reserved_stock', sa.Float(), nullable=False, server_default='0'),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_by_user_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['product_id'], ['bevigrow.bs_products.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['location_id'], ['bevigrow.bs_locations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['updated_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('product_id', 'location_id', name='unique_product_location'),
        sa.Index('ix_bs_inventory_product_id', 'product_id'),
        sa.Index('ix_bs_inventory_location_id', 'location_id'),
        schema='bevigrow'
    )

    # Stock movements (audit trail)
    op.create_table(
        'bs_stock_movements',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('product_id', sa.Integer(), nullable=False),
        sa.Column('from_location_id', sa.Integer(), nullable=True),
        sa.Column('to_location_id', sa.Integer(), nullable=True),
        sa.Column('movement_type', sa.String(50), nullable=False),
        sa.Column('quantity', sa.Float(), nullable=False),
        sa.Column('unit', sa.String(50), nullable=True),
        sa.Column('reference_id', sa.Integer(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), index=True),
        sa.Column('created_by_user_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['product_id'], ['bevigrow.bs_products.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['from_location_id'], ['bevigrow.bs_locations.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['to_location_id'], ['bevigrow.bs_locations.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.Index('ix_bs_stock_movements_product_id', 'product_id'),
        sa.Index('ix_bs_stock_movements_movement_type', 'movement_type'),
        sa.Index('ix_bs_stock_movements_created_at', 'created_at'),
        schema='bevigrow'
    )

    # Restocks (with supplier info, dates, costs)
    op.create_table(
        'bs_restocks',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('product_id', sa.Integer(), nullable=False),
        sa.Column('location_id', sa.Integer(), nullable=False),
        sa.Column('quantity', sa.Float(), nullable=False),
        sa.Column('unit', sa.String(50), nullable=True),
        sa.Column('restock_date', sa.DateTime(timezone=True), nullable=False),
        sa.Column('supplier_name', sa.String(200), nullable=True),
        sa.Column('cost_per_unit', sa.Float(), nullable=True),
        sa.Column('total_cost', sa.Float(), nullable=True),
        sa.Column('reference_id', sa.String(100), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('status', sa.String(50), server_default='pending'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('created_by_user_id', sa.Integer(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_by_user_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['product_id'], ['bevigrow.bs_products.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['location_id'], ['bevigrow.bs_locations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['updated_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.Index('ix_bs_restocks_product_id', 'product_id'),
        sa.Index('ix_bs_restocks_status', 'status'),
        sa.Index('ix_bs_restocks_restock_date', 'restock_date'),
        schema='bevigrow'
    )

    # Customer requirements
    op.create_table(
        'bs_customer_requirements',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('contact_id', sa.Integer(), nullable=True),
        sa.Column('customer_name', sa.String(200), nullable=False),
        sa.Column('status', sa.String(50), nullable=False, server_default='pending'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('created_by_user_id', sa.Integer(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_by_user_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['contact_id'], ['bevigrow.contacts.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['updated_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.Index('ix_bs_customer_requirements_status', 'status'),
        schema='bevigrow'
    )

    # Requirement items (line items in a requirement)
    op.create_table(
        'bs_requirement_items',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('requirement_id', sa.Integer(), nullable=False),
        sa.Column('product_id', sa.Integer(), nullable=False),
        sa.Column('quantity_required', sa.Float(), nullable=False),
        sa.Column('unit', sa.String(50), nullable=True),
        sa.Column('quantity_reserved', sa.Float(), nullable=False, server_default='0'),
        sa.Column('quantity_fulfilled', sa.Float(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['requirement_id'], ['bevigrow.bs_customer_requirements.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['product_id'], ['bevigrow.bs_products.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.Index('ix_bs_requirement_items_requirement_id', 'requirement_id'),
        schema='bevigrow'
    )

    # Customer purchases
    op.create_table(
        'bs_customer_purchases',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('contact_id', sa.Integer(), nullable=True),
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
        sa.ForeignKeyConstraint(['contact_id'], ['bevigrow.contacts.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['product_id'], ['bevigrow.bs_products.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['updated_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.Index('ix_bs_customer_purchases_product_id', 'product_id'),
        sa.Index('ix_bs_customer_purchases_payment_status', 'payment_status'),
        sa.Index('ix_bs_customer_purchases_purchase_date', 'purchase_date'),
        schema='bevigrow'
    )

    # Combos (bundled products)
    op.create_table(
        'bs_combos',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('created_by_user_id', sa.Integer(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_by_user_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['updated_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.Index('ix_bs_combos_name', 'name'),
        sa.Index('ix_bs_combos_active', 'active'),
        schema='bevigrow'
    )

    # Combo items (products in a combo)
    op.create_table(
        'bs_combo_items',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('combo_id', sa.Integer(), nullable=False),
        sa.Column('product_id', sa.Integer(), nullable=False),
        sa.Column('quantity', sa.Float(), nullable=False),
        sa.Column('unit', sa.String(50), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['combo_id'], ['bevigrow.bs_combos.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['product_id'], ['bevigrow.bs_products.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.Index('ix_bs_combo_items_combo_id', 'combo_id'),
        schema='bevigrow'
    )


def downgrade() -> None:
    op.drop_table('bs_combo_items', schema='bevigrow')
    op.drop_table('bs_combos', schema='bevigrow')
    op.drop_table('bs_customer_purchases', schema='bevigrow')
    op.drop_table('bs_requirement_items', schema='bevigrow')
    op.drop_table('bs_customer_requirements', schema='bevigrow')
    op.drop_table('bs_restocks', schema='bevigrow')
    op.drop_table('bs_stock_movements', schema='bevigrow')
    op.drop_table('bs_inventory', schema='bevigrow')
    op.drop_table('bs_locations', schema='bevigrow')
    op.drop_table('bs_products', schema='bevigrow')
    op.drop_table('bs_categories', schema='bevigrow')
