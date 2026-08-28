"""Pydantic schemas for Bevi Stoq inventory management."""
from datetime import datetime
from pydantic import BaseModel, Field


# ================================================================ CATEGORIES

class CategoryBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=150)
    description: str | None = None


class CategoryCreate(CategoryBase):
    pass


class CategoryUpdate(BaseModel):
    name: str | None = None
    description: str | None = None


class CategoryOut(CategoryBase):
    id: int
    active: bool
    created_at: datetime
    created_by_user_id: int
    updated_at: datetime

    class Config:
        from_attributes = True


# ================================================================ PRODUCTS

class ProductBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    category_id: int
    default_unit: str = Field(..., min_length=1, max_length=50)
    low_stock_alert_level: float = Field(default=0, ge=0)


class ProductCreate(ProductBase):
    pass


class ProductUpdate(BaseModel):
    name: str | None = None
    category_id: int | None = None
    low_stock_alert_level: float | None = None


class ProductOut(ProductBase):
    id: int
    active: bool
    created_at: datetime
    created_by_user_id: int
    updated_at: datetime

    class Config:
        from_attributes = True


class ProductDetailOut(ProductOut):
    """Product with inventory totals."""
    total_physical_stock: float = 0
    total_reserved_stock: float = 0
    total_available_stock: float = 0
    status: str  # NORMAL, LOW_STOCK, OUT_OF_STOCK


# ================================================================ LOCATIONS

class LocationBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=150)
    description: str | None = None


class LocationCreate(LocationBase):
    pass


class LocationUpdate(BaseModel):
    name: str | None = None
    description: str | None = None


class LocationOut(LocationBase):
    id: int
    active: bool
    created_at: datetime
    created_by_user_id: int
    updated_at: datetime

    class Config:
        from_attributes = True


# ================================================================ INVENTORY

class InventoryLocationBreakdown(BaseModel):
    """Stock at a specific location."""
    location_id: int
    location_name: str
    physical_stock: float
    reserved_stock: float
    available_stock: float


class InventoryOut(BaseModel):
    product_id: int
    location_id: int
    physical_stock: float
    reserved_stock: float
    available_stock: float
    updated_at: datetime

    class Config:
        from_attributes = True


# ================================================================ STOCK MOVEMENTS

class StockMovementCreate(BaseModel):
    product_id: int
    location_id: int
    movement_type: str
    quantity: float = Field(..., gt=0)
    unit: str
    reference_id: int | None = None
    notes: str | None = None


class StockMovementOut(BaseModel):
    id: int
    product_id: int
    location_id: int
    movement_type: str
    quantity: float
    unit: str
    reference_id: int | None = None
    notes: str | None = None
    created_at: datetime
    created_by_user_id: int

    class Config:
        from_attributes = True


# ================================================================ STOCK TRANSFER

class StockTransferCreate(BaseModel):
    product_id: int
    from_location_id: int
    to_location_id: int
    quantity: float = Field(..., gt=0)
    unit: str
    notes: str | None = None


class StockTransferOut(BaseModel):
    product_id: int
    from_location_id: int
    to_location_id: int
    quantity: float
    unit: str
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


# ================================================================ ADD STOCK

class AddStockCreate(BaseModel):
    product_id: int
    location_id: int
    quantity: float = Field(..., gt=0)
    unit: str
    reference: str | None = None
    notes: str | None = None


# ================================================================ CUSTOMER REQUIREMENTS

class RequirementItemInput(BaseModel):
    product_id: int
    quantity_required: float = Field(..., gt=0)
    unit: str


class CustomerRequirementCreate(BaseModel):
    customer_id: int | None = None
    customer_name: str = Field(..., min_length=1, max_length=200)
    items: list[RequirementItemInput] = Field(..., min_items=1)


class RequirementItemOut(BaseModel):
    id: int
    product_id: int
    quantity_required: float
    unit: str
    quantity_reserved: float
    quantity_fulfilled: float
    product_name: str | None = None
    available_stock: float = 0

    class Config:
        from_attributes = True


class CustomerRequirementOut(BaseModel):
    id: int
    customer_id: int | None
    customer_name: str
    status: str
    created_at: datetime
    created_by_user_id: int
    updated_at: datetime
    items: list[RequirementItemOut] = []

    class Config:
        from_attributes = True


class RequirementAvailabilityCheck(BaseModel):
    """Response for availability checking."""
    requirement_id: int
    status: str  # available, partially_available, shortage
    items_availability: list[dict]  # {product_id, required, available, shortage, status}
    can_reserve: bool


# ================================================================ COMBOS

class ComboItemInput(BaseModel):
    product_id: int
    quantity: float = Field(..., gt=0)
    unit: str


class ComboCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = None
    items: list[ComboItemInput] = Field(..., min_items=1)


class ComboItemOut(BaseModel):
    id: int
    product_id: int
    quantity: float
    unit: str
    product_name: str | None = None
    available_stock: float = 0

    class Config:
        from_attributes = True


class ComboOut(BaseModel):
    id: int
    name: str
    description: str | None = None
    active: bool
    created_at: datetime
    created_by_user_id: int
    updated_at: datetime
    items: list[ComboItemOut] = []

    class Config:
        from_attributes = True


class ComboAvailabilityOut(BaseModel):
    """Combo availability check."""
    combo_id: int
    name: str
    is_available: bool
    items: list[dict]  # {product_id, required_qty, available_qty, status}
    maximum_possible_combos: int


# ================================================================ DASHBOARD

class DashboardSummary(BaseModel):
    total_stock_value: float  # Could be in units or count
    low_stock_count: int
    out_of_stock_count: int
    pending_requirements_count: int


class StockByCategory(BaseModel):
    category_id: int
    category_name: str
    total_quantity: float
    product_count: int


class StockByLocation(BaseModel):
    location_id: int
    location_name: str
    total_quantity: float
    product_count: int


class RecentMovement(BaseModel):
    id: int
    product_name: str
    location_name: str
    movement_type: str
    quantity: float
    unit: str
    created_at: datetime
    created_by_name: str | None = None


class DashboardOut(BaseModel):
    summary: DashboardSummary
    stock_by_category: list[StockByCategory] = []
    stock_by_location: list[StockByLocation] = []
    recent_movements: list[RecentMovement] = []


# ================================================================ SEARCH

class SearchResult(BaseModel):
    type: str  # "product", "category", "location", "requirement"
    id: int
    name: str
    extra_info: str | None = None


class SearchResultsOut(BaseModel):
    products: list[SearchResult] = []
    categories: list[SearchResult] = []
    locations: list[SearchResult] = []
    requirements: list[SearchResult] = []
