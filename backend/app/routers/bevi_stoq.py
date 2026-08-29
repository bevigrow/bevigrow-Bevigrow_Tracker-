"""Bevi Stoq inventory management API routes - Complete implementation."""
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

log = logging.getLogger(__name__)

from ..database import get_db
from ..deps import get_current_user
from ..models import (
    User, Category, Product, Location, Inventory, StockMovement,
    CustomerRequirement, RequirementItem, Combo, ComboItem,
    CustomerPurchase,
    StockMovementType, RequirementStatus, PaymentStatus
)
from ..schemas_bevi_stoq import (
    CategoryCreate, CategoryOut, CategoryUpdate,
    ProductCreate, ProductOut, ProductDetailOut, ProductUpdate,
    LocationCreate, LocationOut, LocationUpdate,
    InventoryOut,
    StockMovementOut, StockMovementCreate,
    StockTransferCreate, AddStockCreate,
    CustomerRequirementCreate, CustomerRequirementOut,
    RequirementAvailabilityCheck, RequirementItemOut,
    ComboCreate, ComboOut, ComboAvailabilityOut,
    DashboardOut, DashboardSummary, StockByCategory, StockByLocation,
    RecentMovement, SearchResultsOut, SearchResult,
    CustomerPurchaseCreate, CustomerPurchaseOut, CustomerPurchaseUpdate
)

router = APIRouter(prefix="/api/bevi-stoq", tags=["bevi-stoq"])


def utcnow():
    return datetime.now(timezone.utc)


def get_product_status(available_stock: float, low_stock_threshold: float) -> str:
    """Calculate product status based on available stock."""
    if available_stock <= 0:
        return "OUT_OF_STOCK"
    if available_stock <= low_stock_threshold:
        return "LOW_STOCK"
    return "NORMAL"


# ================================================================ CATEGORIES
@router.get("/categories", response_model=list[CategoryOut])
def list_categories(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    active_only: bool = True,
    search: str | None = None,
    limit: int = Query(100, le=1000),
    offset: int = Query(0, ge=0)
):
    """List categories."""
    query = select(Category)
    if active_only:
        query = query.where(Category.active == True)
    if search:
        query = query.where(Category.name.ilike(f"%{search}%"))
    query = query.limit(limit).offset(offset)
    return db.scalars(query).all()


@router.post("/categories", response_model=CategoryOut, status_code=201)
def create_category(
    data: CategoryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create category."""
    cat = Category(
        name=data.name,
        description=data.description,
        created_by_user_id=current_user.id
    )
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return cat


@router.get("/categories/{cat_id}", response_model=CategoryOut)
def get_category(
    cat_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user)
):
    """Get category detail."""
    cat = db.get(Category, cat_id)
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")
    return cat


@router.put("/categories/{cat_id}", response_model=CategoryOut)
def update_category(
    cat_id: int,
    data: CategoryUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update category."""
    cat = db.get(Category, cat_id)
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")

    if data.name is not None:
        cat.name = data.name
    if data.description is not None:
        cat.description = data.description
    if data.active is not None:
        cat.active = data.active

    cat.updated_at = utcnow()
    cat.updated_by_user_id = current_user.id
    db.commit()
    db.refresh(cat)
    return cat


@router.delete("/categories/{cat_id}", status_code=204)
def delete_category(
    cat_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Soft-delete category."""
    cat = db.get(Category, cat_id)
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")

    cat.active = False
    cat.updated_at = utcnow()
    cat.updated_by_user_id = current_user.id
    db.commit()


# ================================================================ PRODUCTS
@router.get("/products", response_model=list[ProductOut])
def list_products(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    category_id: int | None = None,
    active_only: bool = True,
    search: str | None = None,
    limit: int = Query(100, le=1000),
    offset: int = Query(0, ge=0)
):
    """List products with optional filters."""
    query = select(Product)
    if active_only:
        query = query.where(Product.active == True)
    if category_id:
        query = query.where(Product.category_id == category_id)
    if search:
        query = query.where(Product.name.ilike(f"%{search}%"))
    query = query.limit(limit).offset(offset)
    return db.scalars(query).all()


@router.post("/products", response_model=ProductOut, status_code=201)
def create_product(
    data: ProductCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create product with duplicate check."""
    if not data.name or not data.name.strip():
        raise HTTPException(status_code=400, detail="Product name cannot be empty")

    category = db.get(Category, data.category_id)
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    # Check duplicate (case-insensitive)
    product_name_normalized = data.name.strip()
    existing = db.scalar(
        select(Product).where(
            func.lower(func.trim(Product.name)) == func.lower(product_name_normalized),
            Product.category_id == data.category_id,
            Product.active == True
        )
    )
    if existing:
        log.warning(f"Duplicate product: {product_name_normalized} in category {data.category_id}")
        raise HTTPException(
            status_code=400,
            detail=f"Product '{existing.name}' already exists in this category"
        )

    prod = Product(
        name=product_name_normalized,
        category_id=data.category_id,
        default_unit=data.default_unit,
        low_stock_alert_level=data.low_stock_alert_level,
        created_by_user_id=current_user.id
    )
    db.add(prod)
    db.commit()
    db.refresh(prod)
    return prod


@router.get("/products/{prod_id}", response_model=ProductDetailOut)
def get_product_detail(
    prod_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user)
):
    """Get product detail with inventory totals and status."""
    prod = db.get(Product, prod_id)
    if not prod:
        raise HTTPException(status_code=404, detail="Product not found")

    total_physical = db.scalar(
        select(func.coalesce(func.sum(Inventory.physical_stock), 0))
        .where(Inventory.product_id == prod_id)
    ) or 0

    total_reserved = db.scalar(
        select(func.coalesce(func.sum(Inventory.reserved_stock), 0))
        .where(Inventory.product_id == prod_id)
    ) or 0

    available = total_physical - total_reserved
    status = get_product_status(available, prod.low_stock_alert_level)

    return ProductDetailOut(
        id=prod.id,
        name=prod.name,
        category_id=prod.category_id,
        default_unit=prod.default_unit,
        low_stock_alert_level=prod.low_stock_alert_level,
        active=prod.active,
        created_at=prod.created_at,
        created_by_user_id=prod.created_by_user_id,
        updated_at=prod.updated_at,
        total_physical_stock=total_physical,
        total_reserved_stock=total_reserved,
        total_available_stock=available,
        status=status
    )


@router.put("/products/{prod_id}", response_model=ProductOut)
def update_product(
    prod_id: int,
    data: ProductUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update product."""
    prod = db.get(Product, prod_id)
    if not prod:
        raise HTTPException(status_code=404, detail="Product not found")

    if data.name is not None:
        # Check duplicate excluding self
        existing = db.scalar(
            select(Product).where(
                func.lower(func.trim(Product.name)) == func.lower(data.name.strip()),
                Product.category_id == (data.category_id or prod.category_id),
                Product.id != prod_id,
                Product.active == True
            )
        )
        if existing:
            raise HTTPException(status_code=400, detail=f"Product '{existing.name}' already exists")
        prod.name = data.name.strip()

    if data.category_id is not None:
        prod.category_id = data.category_id
    if data.default_unit is not None:
        prod.default_unit = data.default_unit
    if data.low_stock_alert_level is not None:
        prod.low_stock_alert_level = data.low_stock_alert_level
    if data.active is not None:
        prod.active = data.active

    prod.updated_at = utcnow()
    prod.updated_by_user_id = current_user.id
    db.commit()
    db.refresh(prod)
    return prod


@router.delete("/products/{prod_id}", status_code=204)
def delete_product(
    prod_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Soft-delete product."""
    prod = db.get(Product, prod_id)
    if not prod:
        raise HTTPException(status_code=404, detail="Product not found")

    prod.active = False
    prod.updated_at = utcnow()
    prod.updated_by_user_id = current_user.id
    db.commit()


# ================================================================ LOCATIONS
@router.get("/locations", response_model=list[LocationOut])
def list_locations(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    active_only: bool = True,
    limit: int = Query(100, le=1000),
    offset: int = Query(0, ge=0)
):
    """List locations."""
    query = select(Location)
    if active_only:
        query = query.where(Location.active == True)
    query = query.limit(limit).offset(offset)
    return db.scalars(query).all()


@router.post("/locations", response_model=LocationOut, status_code=201)
def create_location(
    data: LocationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create location."""
    loc = Location(
        name=data.name,
        description=data.description,
        created_by_user_id=current_user.id
    )
    db.add(loc)
    db.commit()
    db.refresh(loc)
    return loc


@router.get("/locations/{loc_id}", response_model=LocationOut)
def get_location(
    loc_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user)
):
    """Get location detail."""
    loc = db.get(Location, loc_id)
    if not loc:
        raise HTTPException(status_code=404, detail="Location not found")
    return loc


@router.put("/locations/{loc_id}", response_model=LocationOut)
def update_location(
    loc_id: int,
    data: LocationUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update location."""
    loc = db.get(Location, loc_id)
    if not loc:
        raise HTTPException(status_code=404, detail="Location not found")

    if data.name is not None:
        loc.name = data.name
    if data.description is not None:
        loc.description = data.description
    if data.active is not None:
        loc.active = data.active

    loc.updated_at = utcnow()
    loc.updated_by_user_id = current_user.id
    db.commit()
    db.refresh(loc)
    return loc


@router.delete("/locations/{loc_id}", status_code=204)
def delete_location(
    loc_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Soft-delete location."""
    loc = db.get(Location, loc_id)
    if not loc:
        raise HTTPException(status_code=404, detail="Location not found")

    loc.active = False
    loc.updated_at = utcnow()
    loc.updated_by_user_id = current_user.id
    db.commit()


# ================================================================ INVENTORY & STOCK OPERATIONS
@router.get("/stock", response_model=list[InventoryOut])
def list_inventory(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    product_id: int | None = None,
    location_id: int | None = None,
    limit: int = Query(500, le=5000),
    offset: int = Query(0, ge=0)
):
    """List inventory with optional filters."""
    query = select(Inventory)
    if product_id:
        query = query.where(Inventory.product_id == product_id)
    if location_id:
        query = query.where(Inventory.location_id == location_id)
    query = query.limit(limit).offset(offset)

    return [
        InventoryOut.from_inventory(inv)
        for inv in db.scalars(query).all()
    ]


@router.post("/stock/add", status_code=201)
def add_stock(
    data: AddStockCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Add stock to a location."""
    prod = db.get(Product, data.product_id)
    if not prod:
        raise HTTPException(status_code=404, detail="Product not found")

    loc = db.get(Location, data.location_id)
    if not loc:
        raise HTTPException(status_code=404, detail="Location not found")

    if data.quantity <= 0:
        raise HTTPException(status_code=400, detail="Quantity must be positive")

    # Get or create inventory record
    inv = db.scalar(
        select(Inventory).where(
            Inventory.product_id == data.product_id,
            Inventory.location_id == data.location_id
        )
    )

    if not inv:
        inv = Inventory(
            product_id=data.product_id,
            location_id=data.location_id,
            physical_stock=0,
            reserved_stock=0
        )
        db.add(inv)

    # Update stock
    inv.physical_stock += data.quantity
    inv.updated_at = utcnow()
    inv.updated_by_user_id = current_user.id

    # Record movement
    movement = StockMovement(
        product_id=data.product_id,
        location_id=data.location_id,
        movement_type=StockMovementType.added,
        quantity=data.quantity,
        unit=data.unit,
        reference_id=data.reference_id,
        supplier=data.supplier,
        cost_per_unit=data.cost_per_unit,
        total_cost=data.total_cost,
        notes=data.notes,
        created_by_user_id=current_user.id
    )
    db.add(movement)
    db.commit()

    return {"status": "ok", "quantity_added": data.quantity}


@router.post("/stock-transfer", status_code=201)
def transfer_stock(
    data: StockTransferCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Transfer stock between locations."""
    if data.from_location_id == data.to_location_id:
        raise HTTPException(status_code=400, detail="From and To locations must be different")

    prod = db.get(Product, data.product_id)
    if not prod:
        raise HTTPException(status_code=404, detail="Product not found")

    from_loc = db.get(Location, data.from_location_id)
    to_loc = db.get(Location, data.to_location_id)
    if not from_loc or not to_loc:
        raise HTTPException(status_code=404, detail="Location not found")

    if data.quantity <= 0:
        raise HTTPException(status_code=400, detail="Quantity must be positive")

    # Check source has enough stock
    from_inv = db.scalar(
        select(Inventory).where(
            Inventory.product_id == data.product_id,
            Inventory.location_id == data.from_location_id
        )
    )

    if not from_inv or (from_inv.physical_stock - from_inv.reserved_stock) < data.quantity:
        raise HTTPException(status_code=400, detail="Insufficient available stock")

    # Get or create destination inventory
    to_inv = db.scalar(
        select(Inventory).where(
            Inventory.product_id == data.product_id,
            Inventory.location_id == data.to_location_id
        )
    )

    if not to_inv:
        to_inv = Inventory(
            product_id=data.product_id,
            location_id=data.to_location_id,
            physical_stock=0,
            reserved_stock=0
        )
        db.add(to_inv)

    # Transfer stock
    from_inv.physical_stock -= data.quantity
    to_inv.physical_stock += data.quantity
    from_inv.updated_at = utcnow()
    to_inv.updated_at = utcnow()
    from_inv.updated_by_user_id = current_user.id
    to_inv.updated_by_user_id = current_user.id

    # Record movements
    out_movement = StockMovement(
        product_id=data.product_id,
        location_id=data.from_location_id,
        movement_type=StockMovementType.transfer_out,
        quantity=data.quantity,
        unit=data.unit,
        notes=f"Transfer to {to_loc.name}" + (f": {data.notes}" if data.notes else ""),
        created_by_user_id=current_user.id
    )
    in_movement = StockMovement(
        product_id=data.product_id,
        location_id=data.to_location_id,
        movement_type=StockMovementType.transfer_in,
        quantity=data.quantity,
        unit=data.unit,
        notes=f"Transfer from {from_loc.name}" + (f": {data.notes}" if data.notes else ""),
        created_by_user_id=current_user.id
    )
    db.add(out_movement)
    db.add(in_movement)
    db.commit()

    return {"status": "ok", "quantity_transferred": data.quantity}


@router.get("/stock-movements", response_model=list[StockMovementOut])
def list_stock_movements(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    product_id: int | None = None,
    location_id: int | None = None,
    movement_type: str | None = None,
    limit: int = Query(500, le=5000),
    offset: int = Query(0, ge=0)
):
    """List stock movements with filters."""
    query = select(StockMovement)
    if product_id:
        query = query.where(StockMovement.product_id == product_id)
    if location_id:
        query = query.where(StockMovement.location_id == location_id)
    if movement_type:
        query = query.where(StockMovement.movement_type == movement_type)

    query = query.order_by(StockMovement.created_at.desc()).limit(limit).offset(offset)
    return db.scalars(query).all()


# ================================================================ CUSTOMER REQUIREMENTS
@router.post("/requirements", response_model=CustomerRequirementOut, status_code=201)
def create_requirement(
    data: CustomerRequirementCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create customer requirement."""
    if not data.items:
        raise HTTPException(status_code=400, detail="Requirement must have at least one item")

    req = CustomerRequirement(
        customer_name=data.customer_name,
        customer_id=data.customer_id,
        status=RequirementStatus.pending,
        created_by_user_id=current_user.id
    )
    db.add(req)
    db.flush()

    for item_data in data.items:
        prod = db.get(Product, item_data.product_id)
        if not prod:
            db.rollback()
            raise HTTPException(status_code=404, detail=f"Product {item_data.product_id} not found")

        item = RequirementItem(
            requirement_id=req.id,
            product_id=item_data.product_id,
            quantity_required=item_data.quantity_required,
            unit=item_data.unit
        )
        db.add(item)

    db.commit()
    db.refresh(req)
    return req


@router.get("/requirements", response_model=list[CustomerRequirementOut])
def list_requirements(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    status: str | None = None,
    customer_id: int | None = None,
    limit: int = Query(500, le=5000),
    offset: int = Query(0, ge=0)
):
    """List customer requirements."""
    query = select(CustomerRequirement)
    if status:
        query = query.where(CustomerRequirement.status == status)
    if customer_id:
        query = query.where(CustomerRequirement.customer_id == customer_id)
    query = query.order_by(CustomerRequirement.created_at.desc()).limit(limit).offset(offset)
    return db.scalars(query).all()


@router.post("/requirements/{req_id}/reserve", status_code=200)
def reserve_requirement(
    req_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Reserve stock for requirement."""
    req = db.get(CustomerRequirement, req_id)
    if not req:
        raise HTTPException(status_code=404, detail="Requirement not found")

    if req.status == RequirementStatus.fulfilled:
        raise HTTPException(status_code=400, detail="Cannot reserve fulfilled requirement")

    # Check availability for all items
    all_available = True
    for item in req.items:
        available = db.scalar(
            select(func.coalesce(func.sum(Inventory.physical_stock - Inventory.reserved_stock), 0))
            .where(Inventory.product_id == item.product_id)
        ) or 0

        if available < item.quantity_required:
            all_available = False
            break

    # Reserve stock
    for item in req.items:
        if item.quantity_reserved < item.quantity_required:
            to_reserve = item.quantity_required - item.quantity_reserved

            # Find available stock
            inv_list = db.scalars(
                select(Inventory)
                .where(Inventory.product_id == item.product_id)
                .where((Inventory.physical_stock - Inventory.reserved_stock) > 0)
            ).all()

            for inv in inv_list:
                if to_reserve <= 0:
                    break

                available = inv.physical_stock - inv.reserved_stock
                to_reserve_here = min(available, to_reserve)
                inv.reserved_stock += to_reserve_here
                item.quantity_reserved += to_reserve_here
                to_reserve -= to_reserve_here

                # Record movement
                movement = StockMovement(
                    product_id=item.product_id,
                    location_id=inv.location_id,
                    movement_type=StockMovementType.reserved,
                    quantity=to_reserve_here,
                    unit=item.unit,
                    notes=f"Reserved for requirement {req_id}",
                    created_by_user_id=current_user.id
                )
                db.add(movement)

    req.status = RequirementStatus.reserved if all_available else RequirementStatus.partially_available
    req.updated_at = utcnow()
    req.updated_by_user_id = current_user.id
    db.commit()

    return {"status": "ok"}


@router.post("/requirements/{req_id}/fulfill", status_code=200)
def fulfill_requirement(
    req_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Fulfill requirement."""
    req = db.get(CustomerRequirement, req_id)
    if not req:
        raise HTTPException(status_code=404, detail="Requirement not found")

    for item in req.items:
        to_fulfill = item.quantity_required - item.quantity_fulfilled
        if to_fulfill > 0:
            # Find reserved stock
            inv_list = db.scalars(
                select(Inventory)
                .where(Inventory.product_id == item.product_id)
                .where(Inventory.reserved_stock > 0)
            ).all()

            for inv in inv_list:
                if to_fulfill <= 0:
                    break

                to_fulfill_here = min(inv.reserved_stock, to_fulfill)
                inv.physical_stock -= to_fulfill_here
                inv.reserved_stock -= to_fulfill_here
                item.quantity_fulfilled += to_fulfill_here
                to_fulfill -= to_fulfill_here

                # Prevent negative stock
                if inv.physical_stock < 0:
                    inv.physical_stock = 0

                # Record movement
                movement = StockMovement(
                    product_id=item.product_id,
                    location_id=inv.location_id,
                    movement_type=StockMovementType.fulfilled,
                    quantity=to_fulfill_here,
                    unit=item.unit,
                    notes=f"Fulfilled for requirement {req_id}",
                    created_by_user_id=current_user.id
                )
                db.add(movement)

    req.status = RequirementStatus.fulfilled
    req.updated_at = utcnow()
    req.updated_by_user_id = current_user.id
    db.commit()

    return {"status": "ok"}


# ================================================================ DASHBOARD
@router.get("/dashboard", response_model=DashboardOut)
def get_dashboard(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user)
):
    """Get Bevi Stoq dashboard summary."""
    # Summary counts
    total_products = db.scalar(select(func.count(Product.id)).where(Product.active == True)) or 0
    total_locations = db.scalar(select(func.count(Location.id)).where(Location.active == True)) or 0
    total_categories = db.scalar(select(func.count(Category.id)).where(Category.active == True)) or 0

    # Stock analysis
    low_stock_count = 0
    out_of_stock_count = 0
    total_stock_value = 0

    products = db.scalars(select(Product).where(Product.active == True)).all()
    for prod in products:
        available = db.scalar(
            select(func.coalesce(func.sum(Inventory.physical_stock - Inventory.reserved_stock), 0))
            .where(Inventory.product_id == prod.id)
        ) or 0

        if available == 0:
            out_of_stock_count += 1
        elif available <= prod.low_stock_alert_level:
            low_stock_count += 1

        # Add cost value if available
        cost = db.scalar(
            select(func.coalesce(func.sum(StockMovement.total_cost), 0))
            .where(
                StockMovement.product_id == prod.id,
                StockMovement.movement_type == StockMovementType.added
            )
        )
        if cost:
            total_stock_value += cost

    # By category
    by_category = []
    categories = db.scalars(select(Category).where(Category.active == True)).all()
    for cat in categories:
        cat_products = db.scalars(
            select(Product).where(Product.category_id == cat.id, Product.active == True)
        ).all()

        total_available = 0
        low_count = 0
        out_count = 0

        for prod in cat_products:
            available = db.scalar(
                select(func.coalesce(func.sum(Inventory.physical_stock - Inventory.reserved_stock), 0))
                .where(Inventory.product_id == prod.id)
            ) or 0

            total_available += available
            if available == 0:
                out_count += 1
            elif available <= prod.low_stock_alert_level:
                low_count += 1

        by_category.append(StockByCategory(
            category_name=cat.name,
            total_available_stock=total_available,
            low_stock_count=low_count,
            out_of_stock_count=out_count
        ))

    # By location
    by_location = []
    locations = db.scalars(select(Location).where(Location.active == True)).all()
    for loc in locations:
        total_available = db.scalar(
            select(func.coalesce(func.sum(Inventory.physical_stock - Inventory.reserved_stock), 0))
            .where(Inventory.location_id == loc.id)
        ) or 0

        by_location.append(StockByLocation(
            location_name=loc.name,
            total_available_stock=total_available
        ))

    # Recent movements
    recent_movements = []
    movements = db.scalars(
        select(StockMovement)
        .order_by(StockMovement.created_at.desc())
        .limit(10)
    ).all()

    for mov in movements:
        prod = db.get(Product, mov.product_id)
        loc = db.get(Location, mov.location_id)

        recent_movements.append(RecentMovement(
            id=mov.id,
            product_name=prod.name if prod else "Unknown",
            movement_type=mov.movement_type.value,
            quantity=mov.quantity,
            unit=mov.unit,
            location_name=loc.name if loc else "Unknown",
            created_at=mov.created_at
        ))

    return DashboardOut(
        summary=DashboardSummary(
            total_products=total_products,
            total_locations=total_locations,
            total_categories=total_categories,
            total_stock_value=total_stock_value,
            low_stock_count=low_stock_count,
            out_of_stock_count=out_of_stock_count
        ),
        by_category=by_category,
        by_location=by_location,
        recent_movements=recent_movements
    )


# ================================================================ CUSTOMER PURCHASES
@router.get("/customer-purchases", response_model=list[CustomerPurchaseOut])
def list_customer_purchases(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    payment_status: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = Query(100, le=1000),
    offset: int = Query(0, ge=0)
):
    """List customer purchases with optional filters."""
    query = select(CustomerPurchase)

    if payment_status:
        query = query.where(CustomerPurchase.payment_status == payment_status)

    if date_from:
        from_dt = datetime.fromisoformat(date_from.replace('Z', '+00:00'))
        query = query.where(CustomerPurchase.purchase_date >= from_dt)

    if date_to:
        to_dt = datetime.fromisoformat(date_to.replace('Z', '+00:00'))
        query = query.where(CustomerPurchase.purchase_date <= to_dt)

    query = query.order_by(CustomerPurchase.purchase_date.desc()).limit(limit).offset(offset)
    return db.scalars(query).all()


@router.post("/customer-purchases", response_model=CustomerPurchaseOut, status_code=201)
def create_customer_purchase(
    data: CustomerPurchaseCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new customer purchase record."""
    product = db.get(Product, data.product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    purchase = CustomerPurchase(
        customer_name=data.customer_name,
        product_id=data.product_id,
        quantity=data.quantity,
        unit=data.unit,
        purchase_date=data.purchase_date,
        payment_status=data.payment_status,
        payment_method=data.payment_method,
        amount=data.amount,
        notes=data.notes,
        created_by_user_id=current_user.id
    )
    db.add(purchase)
    db.commit()
    db.refresh(purchase)
    return purchase


@router.get("/customer-purchases/{purchase_id}", response_model=CustomerPurchaseOut)
def get_customer_purchase(
    purchase_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user)
):
    """Get customer purchase details."""
    purchase = db.get(CustomerPurchase, purchase_id)
    if not purchase:
        raise HTTPException(status_code=404, detail="Purchase not found")
    return purchase


@router.put("/customer-purchases/{purchase_id}", response_model=CustomerPurchaseOut)
def update_customer_purchase(
    purchase_id: int,
    data: CustomerPurchaseUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update a customer purchase record."""
    purchase = db.get(CustomerPurchase, purchase_id)
    if not purchase:
        raise HTTPException(status_code=404, detail="Purchase not found")

    if data.customer_name is not None:
        purchase.customer_name = data.customer_name
    if data.product_id is not None:
        product = db.get(Product, data.product_id)
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
        purchase.product_id = data.product_id
    if data.quantity is not None:
        purchase.quantity = data.quantity
    if data.unit is not None:
        purchase.unit = data.unit
    if data.purchase_date is not None:
        purchase.purchase_date = data.purchase_date
    if data.payment_status is not None:
        purchase.payment_status = data.payment_status
    if data.payment_method is not None:
        purchase.payment_method = data.payment_method
    if data.amount is not None:
        purchase.amount = data.amount
    if data.notes is not None:
        purchase.notes = data.notes

    purchase.updated_at = utcnow()
    purchase.updated_by_user_id = current_user.id
    db.commit()
    db.refresh(purchase)
    return purchase


@router.delete("/customer-purchases/{purchase_id}", status_code=204)
def delete_customer_purchase(
    purchase_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete a customer purchase record."""
    purchase = db.get(CustomerPurchase, purchase_id)
    if not purchase:
        raise HTTPException(status_code=404, detail="Purchase not found")

    db.delete(purchase)
    db.commit()
