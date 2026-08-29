"""Pydantic schemas for Bevi Stoq inventory management."""
from datetime import datetime
from pydantic import BaseModel, Field


# ================================================================ CATEGORY
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
    updated_at: datetime

    model_config = {"from_attributes": True}


# ================================================================ PRODUCT
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
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProductDetailOut(ProductOut):
    total_physical_stock: float
    total_reserved_stock: float
    total_available_stock: float
    status: str  # NORMAL, LOW_STOCK, OUT_OF_STOCK


# ================================================================ LOCATION
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
    updated_at: datetime

    model_config = {"from_attributes": True}


# ================================================================ INVENTORY
class InventoryOut(BaseModel):
    id: int
    product_id: int
    location_id: int
    physical_stock: float
    reserved_stock: float
    available_stock: float = Field(...)
    updated_at: datetime

    model_config = {"from_attributes": True}

    @staticmethod
    def from_inventory(inv):
        return InventoryOut(
            id=inv.id,
            product_id=inv.product_id,
            location_id=inv.location_id,
            physical_stock=inv.physical_stock,
            reserved_stock=inv.reserved_stock,
            available_stock=inv.physical_stock - inv.reserved_stock,
            updated_at=inv.updated_at,
        )


# ================================================================ STOCK MOVEMENT
class StockMovementCreate(BaseModel):
    product_id: int
    location_id: int
    movement_type: str
    quantity: float = Field(..., gt=0)
    unit: str = Field(..., min_length=1, max_length=50)
    reference_id: int | None = None
    supplier: str | None = None
    cost_per_unit: float | None = Field(None, ge=0)
    total_cost: float | None = Field(None, ge=0)
    notes: str | None = None


class StockMovementOut(BaseModel):
    id: int
    product_id: int
    location_id: int
    movement_type: str
    quantity: float
    unit: str
    reference_id: int | None
    supplier: str | None
    cost_per_unit: float | None
    total_cost: float | None
    notes: str | None
    created_at: datetime
    created_by_user_id: int

    model_config = {"from_attributes": True}


# ================================================================ STOCK OPERATIONS
class AddStockCreate(BaseModel):
    product_id: int
    location_id: int
    quantity: float = Field(..., gt=0)
    unit: str
    restock_date: str | None = None
    supplier: str | None = None
    cost_per_unit: float | None = Field(None, ge=0)
    total_cost: float | None = Field(None, ge=0)
    reference_id: int | None = None
    notes: str | None = None


class StockTransferCreate(BaseModel):
    product_id: int
    from_location_id: int
    to_location_id: int
    quantity: float = Field(..., gt=0)
    unit: str
    transfer_date: str | None = None
    notes: str | None = None


# ================================================================ CUSTOMER REQUIREMENT
class CustomerRequirementCreate(BaseModel):
    customer_name: str = Field(..., min_length=1, max_length=200)
    customer_id: int | None = None
    items: list["RequirementItemCreate"]


class RequirementItemCreate(BaseModel):
    product_id: int
    quantity_required: float = Field(..., gt=0)
    unit: str


class RequirementItemOut(BaseModel):
    id: int
    requirement_id: int
    product_id: int
    quantity_required: float
    unit: str
    quantity_reserved: float
    quantity_fulfilled: float
    created_at: datetime

    model_config = {"from_attributes": True}


class CustomerRequirementOut(BaseModel):
    id: int
    customer_id: int | None
    customer_name: str
    status: str
    items: list[RequirementItemOut]
    created_at: datetime
    created_by_user_id: int
    updated_at: datetime

    model_config = {"from_attributes": True}


class RequirementAvailabilityCheck(BaseModel):
    requirement_id: int
    available: bool
    total_shortage: float


# ================================================================ COMBO
class ComboItemCreate(BaseModel):
    product_id: int
    quantity: float = Field(..., gt=0)
    unit: str


class ComboCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = None
    items: list[ComboItemCreate]


class ComboItemOut(BaseModel):
    id: int
    combo_id: int
    product_id: int
    quantity: float
    unit: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ComboOut(BaseModel):
    id: int
    name: str
    description: str | None
    active: bool
    items: list[ComboItemOut]
    created_at: datetime
    created_by_user_id: int
    updated_at: datetime

    model_config = {"from_attributes": True}


class ComboAvailabilityOut(BaseModel):
    combo_id: int
    combo_name: str
    available: bool
    max_complete_combos: int
    shortage_items: list[str]


# ================================================================ DASHBOARD
class StockByCategory(BaseModel):
    category_name: str
    total_available_stock: float
    low_stock_count: int
    out_of_stock_count: int


class StockByLocation(BaseModel):
    location_name: str
    total_available_stock: float


class RecentMovement(BaseModel):
    id: int
    product_name: str
    movement_type: str
    quantity: float
    unit: str
    location_name: str
    created_at: datetime


class DashboardSummary(BaseModel):
    total_products: int
    total_locations: int
    total_categories: int
    total_stock_value: float | None
    low_stock_count: int
    out_of_stock_count: int


class DashboardOut(BaseModel):
    summary: DashboardSummary
    by_category: list[StockByCategory]
    by_location: list[StockByLocation]
    recent_movements: list[RecentMovement]


# ================================================================ SEARCH
class SearchResult(BaseModel):
    id: int
    name: str
    type: str  # product, category, location


class SearchResultsOut(BaseModel):
    products: list[SearchResult]
    categories: list[SearchResult]
    locations: list[SearchResult]


# ================================================================ CUSTOMER PURCHASES
class CustomerPurchaseCreate(BaseModel):
    customer_name: str = Field(..., min_length=1, max_length=200)
    product_id: int
    quantity: float = Field(..., gt=0)
    unit: str
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
    customer_id: int | None
    customer_name: str
    product_id: int
    quantity: float
    unit: str
    purchase_date: datetime
    payment_status: str
    payment_method: str | None
    amount: float
    notes: str | None
    created_at: datetime
    created_by_user_id: int
    updated_at: datetime

    model_config = {"from_attributes": True}
