"""Pydantic schemas for Bevi Stoq inventory management."""
from datetime import datetime
from pydantic import BaseModel, Field


# ================================================================ CATEGORIES
class CategoryCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=150)
    description: str | None = None


class CategoryUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=150)
    description: str | None = None
    active: bool | None = None


class CategoryOut(BaseModel):
    id: int
    name: str
    description: str | None
    active: bool
    created_at: datetime
    created_by_user_id: int

    model_config = {"from_attributes": True}


# ================================================================ PRODUCTS
class ProductCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    category_id: int
    default_unit: str = Field(..., min_length=1, max_length=50)
    low_stock_alert_level: float = Field(default=0, ge=0)


class ProductUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    category_id: int | None = None
    default_unit: str | None = Field(None, min_length=1, max_length=50)
    low_stock_alert_level: float | None = Field(None, ge=0)
    active: bool | None = None


class ProductOut(BaseModel):
    id: int
    name: str
    category_id: int
    default_unit: str
    low_stock_alert_level: float
    active: bool
    created_at: datetime
    created_by_user_id: int

    model_config = {"from_attributes": True}


# ================================================================ LOCATIONS
class LocationCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=150)
    description: str | None = None


class LocationUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=150)
    description: str | None = None
    active: bool | None = None


class LocationOut(BaseModel):
    id: int
    name: str
    description: str | None
    active: bool
    created_at: datetime
    created_by_user_id: int

    model_config = {"from_attributes": True}


# ================================================================ INVENTORY
class InventoryOut(BaseModel):
    id: int
    product_id: int
    location_id: int
    physical_stock: float
    reserved_stock: float
    available_stock: float = 0

    model_config = {"from_attributes": True}


# ================================================================ STOCK MOVEMENTS
class StockMovementCreate(BaseModel):
    product_id: int
    from_location_id: int | None = None
    to_location_id: int | None = None
    movement_type: str
    quantity: float = Field(..., gt=0)
    unit: str | None = None
    reference_id: int | None = None
    notes: str | None = None


class StockMovementOut(BaseModel):
    id: int
    product_id: int
    from_location_id: int | None
    to_location_id: int | None
    movement_type: str
    quantity: float
    unit: str | None
    created_at: datetime
    created_by_user_id: int

    model_config = {"from_attributes": True}


# ================================================================ RESTOCKS
class RestockCreate(BaseModel):
    product_id: int
    location_id: int
    quantity: float = Field(..., gt=0)
    unit: str | None = None
    restock_date: datetime
    supplier_name: str | None = None
    cost_per_unit: float | None = None
    total_cost: float | None = None
    reference_id: str | None = None
    notes: str | None = None


class RestockUpdate(BaseModel):
    quantity: float | None = Field(None, gt=0)
    unit: str | None = None
    restock_date: datetime | None = None
    supplier_name: str | None = None
    cost_per_unit: float | None = None
    total_cost: float | None = None
    reference_id: str | None = None
    notes: str | None = None
    status: str | None = None


class RestockOut(BaseModel):
    id: int
    product_id: int
    location_id: int
    quantity: float
    unit: str | None
    restock_date: datetime
    supplier_name: str | None
    cost_per_unit: float | None
    total_cost: float | None
    reference_id: str | None
    notes: str | None
    status: str
    created_at: datetime
    created_by_user_id: int

    model_config = {"from_attributes": True}


# ================================================================ CUSTOMER REQUIREMENTS
class RequirementItemCreate(BaseModel):
    product_id: int
    quantity_required: float = Field(..., gt=0)
    unit: str | None = None


class RequirementCreate(BaseModel):
    customer_name: str = Field(..., min_length=1, max_length=200)
    contact_id: int | None = None
    items: list[RequirementItemCreate]


class RequirementItemOut(BaseModel):
    id: int
    product_id: int
    quantity_required: float
    unit: str | None
    quantity_reserved: float
    quantity_fulfilled: float
    created_at: datetime

    model_config = {"from_attributes": True}


class RequirementOut(BaseModel):
    id: int
    contact_id: int | None
    customer_name: str
    status: str
    created_at: datetime
    items: list[RequirementItemOut]

    model_config = {"from_attributes": True}


# ================================================================ CUSTOMER PURCHASES
class CustomerPurchaseCreate(BaseModel):
    customer_name: str = Field(..., min_length=1, max_length=200)
    contact_id: int | None = None
    product_id: int
    quantity: float = Field(..., gt=0)
    unit: str | None = None
    purchase_date: datetime
    payment_status: str = Field(default='pending')
    payment_method: str | None = None
    amount: float = Field(..., ge=0)
    notes: str | None = None


class CustomerPurchaseUpdate(BaseModel):
    customer_name: str | None = Field(None, min_length=1, max_length=200)
    product_id: int | None = None
    quantity: float | None = Field(None, gt=0)
    unit: str | None = None
    purchase_date: datetime | None = None
    payment_status: str | None = None
    payment_method: str | None = None
    amount: float | None = Field(None, ge=0)
    notes: str | None = None


class CustomerPurchaseOut(BaseModel):
    id: int
    contact_id: int | None
    customer_name: str
    product_id: int
    quantity: float
    unit: str | None
    purchase_date: datetime
    payment_status: str
    payment_method: str | None
    amount: float
    notes: str | None
    created_at: datetime
    created_by_user_id: int

    model_config = {"from_attributes": True}


# ================================================================ COMBOS
class ComboItemCreate(BaseModel):
    product_id: int
    quantity: float = Field(..., gt=0)
    unit: str | None = None


class ComboCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = None
    items: list[ComboItemCreate]


class ComboItemOut(BaseModel):
    id: int
    combo_id: int
    product_id: int
    quantity: float
    unit: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ComboOut(BaseModel):
    id: int
    name: str
    description: str | None
    active: bool
    items: list[ComboItemOut]
    created_at: datetime

    model_config = {"from_attributes": True}


# ================================================================ DASHBOARD
class ProductStatus(BaseModel):
    product_id: int
    product_name: str
    status: str
    current_stock: float
    threshold: float


class DashboardSummary(BaseModel):
    total_products: int
    low_stock_count: int
    out_of_stock_count: int
    total_locations: int
    total_categories: int


class DashboardOut(BaseModel):
    summary: DashboardSummary
    low_stock_products: list[ProductStatus]
    out_of_stock_products: list[ProductStatus]
    recent_movements: list[StockMovementOut]
