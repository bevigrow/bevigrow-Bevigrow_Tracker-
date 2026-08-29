"""Bevi Stoq inventory management API routes."""
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
    StockMovementType, RequirementStatus
)
from ..schemas_bevi_stoq import (
    CategoryCreate, CategoryOut, CategoryUpdate,
    ProductCreate, ProductOut, ProductDetailOut, ProductUpdate,
    LocationCreate, LocationOut, LocationUpdate,
    InventoryOut, InventoryLocationBreakdown,
    StockMovementOut, StockMovementCreate,
    StockTransferCreate, AddStockCreate,
    CustomerRequirementCreate, CustomerRequirementOut,
    RequirementAvailabilityCheck, RequirementItemOut,
    ComboCreate, ComboOut, ComboAvailabilityOut,
    DashboardOut, DashboardSummary, StockByCategory, StockByLocation,
    RecentMovement, SearchResultsOut, SearchResult
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
    current_user: User = Depends(get_current_user),
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
    categories = db.scalars(query).all()
    return categories


@router.post("/categories", response_model=CategoryOut, status_code=201)
def create_category(
    data: CategoryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create category."""
    category = Category(
        name=data.name,
        description=data.description,
        created_by_user_id=current_user.id
    )
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


@router.get("/categories/{category_id}", response_model=CategoryOut)
def get_category(
    category_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get category detail."""
    category = db.get(Category, category_id)
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    return category


@router.put("/categories/{category_id}", response_model=CategoryOut)
def update_category(
    category_id: int,
    data: CategoryUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update category."""
    category = db.get(Category, category_id)
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    if data.name is not None:
        category.name = data.name
    if data.description is not None:
        category.description = data.description

    category.updated_at = utcnow()
    db.commit()
    db.refresh(category)
    return category


@router.delete("/categories/{category_id}", status_code=204)
def delete_category(
    category_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Deactivate category."""
    category = db.get(Category, category_id)
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    # Check if products depend on it
    product_count = db.scalar(
        select(func.count(Product.id)).where(Product.category_id == category_id, Product.active == True)
    )
    if product_count > 0:
        raise HTTPException(status_code=400, detail="Cannot deactivate category with active products")

    category.active = False
    category.updated_at = utcnow()
    db.commit()


# ================================================================ PRODUCTS

@router.get("/products", response_model=list[ProductOut])
def list_products(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    category_id: int | None = None,
    active_only: bool = True,
    search: str | None = None,
    limit: int = Query(100, le=1000),
    offset: int = Query(0, ge=0)
):
    """List products."""
    query = select(Product)
    if active_only:
        query = query.where(Product.active == True)
    if category_id:
        query = query.where(Product.category_id == category_id)
    if search:
        query = query.where(Product.name.ilike(f"%{search}%"))

    query = query.limit(limit).offset(offset)
    products = db.scalars(query).all()
    return products


@router.post("/products", response_model=ProductOut, status_code=201)
def create_product(
    data: ProductCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create product."""
    # Validate input
    if not data.name or not data.name.strip():
        raise HTTPException(status_code=400, detail="Product name cannot be empty")

    # Check category exists
    category = db.get(Category, data.category_id)
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    # Check duplicate (case-insensitive, trimmed)
    product_name_normalized = data.name.strip()
    existing = db.scalar(
        select(Product).where(
            func.lower(func.trim(Product.name)) == func.lower(product_name_normalized),
            Product.category_id == data.category_id,
            Product.active == True
        )
    )
    if existing:
        log.warning(
            f"Duplicate product attempted: {product_name_normalized} in category {data.category_id} "
            f"by user {current_user.id}. Existing product: {existing.name} (ID: {existing.id})"
        )
        raise HTTPException(
            status_code=400,
            detail=f"Product '{existing.name}' already exists in this category"
        )

    product = Product(
        name=product_name_normalized,
        category_id=data.category_id,
        default_unit=data.default_unit,
        low_stock_alert_level=data.low_stock_alert_level,
        created_by_user_id=current_user.id
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    log.info(f"Product created: {product.name} (ID: {product.id}) in category {data.category_id}")
    return product


@router.get("/products/{product_id}", response_model=ProductDetailOut)
def get_product_detail(
    product_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get product detail with inventory totals."""
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    # Calculate totals
    physical_total = db.scalar(
        select(func.sum(Inventory.physical_stock)).where(Inventory.product_id == product_id)
    ) or 0
    reserved_total = db.scalar(
        select(func.sum(Inventory.reserved_stock)).where(Inventory.product_id == product_id)
    ) or 0
    available_total = physical_total - reserved_total

    status = get_product_status(available_total, product.low_stock_alert_level)

    return ProductDetailOut(
        id=product.id,
        name=product.name,
        category_id=product.category_id,
        default_unit=product.default_unit,
        low_stock_alert_level=product.low_stock_alert_level,
        active=product.active,
        created_at=product.created_at,
        created_by_user_id=product.created_by_user_id,
        updated_at=product.updated_at,
        total_physical_stock=physical_total,
        total_reserved_stock=reserved_total,
        total_available_stock=available_total,
        status=status
    )


@router.put("/products/{product_id}", response_model=ProductOut)
def update_product(
    product_id: int,
    data: ProductUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update product."""
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    # Check for duplicate if name or category is changing
    if data.name is not None or data.category_id is not None:
        new_name = data.name if data.name is not None else product.name
        new_category_id = data.category_id if data.category_id is not None else product.category_id

        # Only check if values actually changed
        if new_name != product.name or new_category_id != product.category_id:
            new_name_normalized = new_name.strip() if isinstance(new_name, str) else new_name
            existing = db.scalar(
                select(Product).where(
                    func.lower(func.trim(Product.name)) == func.lower(new_name_normalized),
                    Product.category_id == new_category_id,
                    Product.id != product_id,  # Exclude self
                    Product.active == True
                )
            )
            if existing:
                raise HTTPException(
                    status_code=400,
                    detail=f"Product '{existing.name}' already exists in this category"
                )

    if data.name is not None:
        product.name = data.name.strip()
    if data.category_id is not None:
        product.category_id = data.category_id
    if data.low_stock_alert_level is not None:
        product.low_stock_alert_level = data.low_stock_alert_level

    product.updated_at = utcnow()
    db.commit()
    db.refresh(product)
    log.info(f"Product updated: {product.name} (ID: {product.id})")
    return product


@router.delete("/products/{product_id}", status_code=204)
def delete_product(
    product_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Deactivate product."""
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    # Check if stock exists
    stock_count = db.scalar(
        select(func.count(Inventory.id)).where(
            Inventory.product_id == product_id,
            Inventory.physical_stock > 0
        )
    )
    if stock_count > 0:
        raise HTTPException(status_code=400, detail="Cannot delete product with existing stock")

    product.active = False
    product.updated_at = utcnow()
    db.commit()


# ================================================================ LOCATIONS

@router.get("/locations", response_model=list[LocationOut])
def list_locations(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    active_only: bool = True,
    search: str | None = None,
    limit: int = Query(100, le=1000),
    offset: int = Query(0, ge=0)
):
    """List locations."""
    query = select(Location)
    if active_only:
        query = query.where(Location.active == True)
    if search:
        query = query.where(Location.name.ilike(f"%{search}%"))

    query = query.limit(limit).offset(offset)
    locations = db.scalars(query).all()
    return locations


@router.post("/locations", response_model=LocationOut, status_code=201)
def create_location(
    data: LocationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create location."""
    location = Location(
        name=data.name,
        description=data.description,
        created_by_user_id=current_user.id
    )
    db.add(location)
    db.commit()
    db.refresh(location)
    return location


@router.get("/locations/{location_id}", response_model=LocationOut)
def get_location(
    location_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get location detail."""
    location = db.get(Location, location_id)
    if not location:
        raise HTTPException(status_code=404, detail="Location not found")
    return location


@router.put("/locations/{location_id}", response_model=LocationOut)
def update_location(
    location_id: int,
    data: LocationUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update location."""
    location = db.get(Location, location_id)
    if not location:
        raise HTTPException(status_code=404, detail="Location not found")

    if data.name is not None:
        location.name = data.name
    if data.description is not None:
        location.description = data.description

    location.updated_at = utcnow()
    db.commit()
    db.refresh(location)
    return location


@router.delete("/locations/{location_id}", status_code=204)
def delete_location(
    location_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Deactivate location."""
    location = db.get(Location, location_id)
    if not location:
        raise HTTPException(status_code=404, detail="Location not found")

    # Check if stock exists
    stock_count = db.scalar(
        select(func.count(Inventory.id)).where(
            Inventory.location_id == location_id,
            Inventory.physical_stock > 0
        )
    )
    if stock_count > 0:
        raise HTTPException(status_code=400, detail="Cannot delete location with existing stock")

    location.active = False
    location.updated_at = utcnow()
    db.commit()


# ================================================================ STOCK OPERATIONS

@router.post("/stock/add", response_model=InventoryOut, status_code=201)
def add_stock(
    data: AddStockCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Add stock to inventory."""
    # Verify product and location exist
    product = db.get(Product, data.product_id)
    location = db.get(Location, data.location_id)

    if not product or not location:
        raise HTTPException(status_code=404, detail="Product or location not found")

    # Get or create inventory
    inventory = db.scalar(
        select(Inventory).where(
            Inventory.product_id == data.product_id,
            Inventory.location_id == data.location_id
        )
    )

    if not inventory:
        inventory = Inventory(
            product_id=data.product_id,
            location_id=data.location_id,
            updated_by_user_id=current_user.id
        )
        db.add(inventory)

    # Add stock
    inventory.physical_stock += data.quantity
    inventory.updated_at = utcnow()
    inventory.updated_by_user_id = current_user.id

    # Create movement record
    movement = StockMovement(
        product_id=data.product_id,
        location_id=data.location_id,
        movement_type=StockMovementType.added,
        quantity=data.quantity,
        unit=data.unit,
        reference_id=None,
        notes=data.notes or f"Added: {data.reference}" if data.reference else None,
        created_by_user_id=current_user.id
    )
    db.add(movement)

    db.commit()
    db.refresh(inventory)

    available = inventory.physical_stock - inventory.reserved_stock
    return InventoryOut(
        product_id=inventory.product_id,
        location_id=inventory.location_id,
        physical_stock=inventory.physical_stock,
        reserved_stock=inventory.reserved_stock,
        available_stock=available,
        updated_at=inventory.updated_at
    )


@router.post("/stock/transfer", response_model=dict, status_code=201)
def transfer_stock(
    data: StockTransferCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Transfer stock between locations (atomic)."""
    if data.from_location_id == data.to_location_id:
        raise HTTPException(status_code=400, detail="Cannot transfer to same location")

    # Verify product and locations
    product = db.get(Product, data.product_id)
    from_loc = db.get(Location, data.from_location_id)
    to_loc = db.get(Location, data.to_location_id)

    if not product or not from_loc or not to_loc:
        raise HTTPException(status_code=404, detail="Product or location not found")

    # Get source inventory
    from_inventory = db.scalar(
        select(Inventory).where(
            Inventory.product_id == data.product_id,
            Inventory.location_id == data.from_location_id
        )
    )

    if not from_inventory or from_inventory.physical_stock < data.quantity:
        raise HTTPException(status_code=400, detail="Insufficient stock to transfer")

    # Get or create destination inventory
    to_inventory = db.scalar(
        select(Inventory).where(
            Inventory.product_id == data.product_id,
            Inventory.location_id == data.to_location_id
        )
    )

    if not to_inventory:
        to_inventory = Inventory(
            product_id=data.product_id,
            location_id=data.to_location_id,
            updated_by_user_id=current_user.id
        )
        db.add(to_inventory)

    # Execute transfer
    from_inventory.physical_stock -= data.quantity
    to_inventory.physical_stock += data.quantity
    from_inventory.updated_at = utcnow()
    to_inventory.updated_at = utcnow()
    from_inventory.updated_by_user_id = current_user.id
    to_inventory.updated_by_user_id = current_user.id

    # Create movement records
    out_movement = StockMovement(
        product_id=data.product_id,
        location_id=data.from_location_id,
        movement_type=StockMovementType.transfer_out,
        quantity=data.quantity,
        unit=data.unit,
        notes=data.notes or f"Transfer to {to_loc.name}",
        created_by_user_id=current_user.id
    )

    in_movement = StockMovement(
        product_id=data.product_id,
        location_id=data.to_location_id,
        movement_type=StockMovementType.transfer_in,
        quantity=data.quantity,
        unit=data.unit,
        notes=data.notes or f"Transfer from {from_loc.name}",
        created_by_user_id=current_user.id
    )

    db.add(out_movement)
    db.add(in_movement)
    db.commit()

    return {
        "status": "success",
        "from_location": from_loc.name,
        "to_location": to_loc.name,
        "quantity_transferred": data.quantity,
        "unit": data.unit
    }


@router.get("/stock", response_model=list[InventoryOut])
def get_stock(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    product_id: int | None = None,
    location_id: int | None = None,
    only_available: bool = False
):
    """Get current stock levels."""
    query = select(Inventory)

    if product_id:
        query = query.where(Inventory.product_id == product_id)
    if location_id:
        query = query.where(Inventory.location_id == location_id)
    if only_available:
        query = query.where(Inventory.physical_stock > 0)

    inventory_items = db.scalars(query).all()

    return [
        InventoryOut(
            product_id=inv.product_id,
            location_id=inv.location_id,
            physical_stock=inv.physical_stock,
            reserved_stock=inv.reserved_stock,
            available_stock=inv.physical_stock - inv.reserved_stock,
            updated_at=inv.updated_at
        )
        for inv in inventory_items
    ]


# ================================================================ STOCK MOVEMENTS

@router.get("/movements", response_model=list[StockMovementOut])
def get_movements(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    product_id: int | None = None,
    location_id: int | None = None,
    movement_type: str | None = None,
    limit: int = Query(100, le=1000),
    offset: int = Query(0, ge=0)
):
    """Get stock movement history."""
    query = select(StockMovement)

    if product_id:
        query = query.where(StockMovement.product_id == product_id)
    if location_id:
        query = query.where(StockMovement.location_id == location_id)
    if movement_type:
        query = query.where(StockMovement.movement_type == movement_type)

    query = query.order_by(StockMovement.created_at.desc())
    query = query.limit(limit).offset(offset)

    movements = db.scalars(query).all()
    return movements


# ================================================================ CUSTOMER REQUIREMENTS

@router.post("/requirements", response_model=CustomerRequirementOut, status_code=201)
def create_requirement(
    data: CustomerRequirementCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create customer requirement."""
    requirement = CustomerRequirement(
        customer_id=data.customer_id,
        customer_name=data.customer_name,
        status=RequirementStatus.pending,
        created_by_user_id=current_user.id
    )
    db.add(requirement)
    db.flush()

    # Add requirement items
    for item_data in data.items:
        product = db.get(Product, item_data.product_id)
        if not product:
            raise HTTPException(status_code=404, detail=f"Product {item_data.product_id} not found")

        item = RequirementItem(
            requirement_id=requirement.id,
            product_id=item_data.product_id,
            quantity_required=item_data.quantity_required,
            unit=item_data.unit
        )
        db.add(item)

    db.commit()
    db.refresh(requirement)

    # Load items
    requirement.items = db.scalars(
        select(RequirementItem).where(RequirementItem.requirement_id == requirement.id)
    ).all()

    return requirement


@router.get("/requirements", response_model=list[CustomerRequirementOut])
def get_requirements(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    status: str | None = None,
    customer_id: int | None = None,
    limit: int = Query(100, le=1000),
    offset: int = Query(0, ge=0)
):
    """Get customer requirements."""
    query = select(CustomerRequirement)

    if status:
        query = query.where(CustomerRequirement.status == status)
    if customer_id:
        query = query.where(CustomerRequirement.customer_id == customer_id)

    query = query.order_by(CustomerRequirement.created_at.desc())
    query = query.limit(limit).offset(offset)

    requirements = db.scalars(query).all()
    return requirements


@router.get("/requirements/{requirement_id}", response_model=CustomerRequirementOut)
def get_requirement(
    requirement_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get requirement detail."""
    requirement = db.get(CustomerRequirement, requirement_id)
    if not requirement:
        raise HTTPException(status_code=404, detail="Requirement not found")

    requirement.items = db.scalars(
        select(RequirementItem).where(RequirementItem.requirement_id == requirement_id)
    ).all()

    return requirement


@router.post("/requirements/{requirement_id}/reserve", response_model=CustomerRequirementOut)
def reserve_requirement(
    requirement_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Reserve stock for requirement."""
    requirement = db.get(CustomerRequirement, requirement_id)
    if not requirement:
        raise HTTPException(status_code=404, detail="Requirement not found")

    items = db.scalars(
        select(RequirementItem).where(RequirementItem.requirement_id == requirement_id)
    ).all()

    # Check availability
    for item in items:
        # Get total available stock
        available = db.scalar(
            select(func.sum(Inventory.physical_stock - Inventory.reserved_stock))
            .where(Inventory.product_id == item.product_id)
        ) or 0

        if available < item.quantity_required:
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient stock for product {item.product_id}"
            )

    # Reserve stock
    for item in items:
        # Reserve from inventory (could implement allocation logic here)
        inventory = db.scalar(
            select(Inventory).where(Inventory.product_id == item.product_id)
            .order_by(Inventory.physical_stock - Inventory.reserved_stock).desc()
        )

        if inventory:
            inventory.reserved_stock += item.quantity_required
            item.quantity_reserved = item.quantity_required
            inventory.updated_at = utcnow()

    requirement.status = RequirementStatus.reserved
    requirement.updated_at = utcnow()
    db.commit()
    db.refresh(requirement)

    return requirement


@router.post("/requirements/{requirement_id}/fulfill", response_model=CustomerRequirementOut)
def fulfill_requirement(
    requirement_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Fulfill customer requirement."""
    requirement = db.get(CustomerRequirement, requirement_id)
    if not requirement:
        raise HTTPException(status_code=404, detail="Requirement not found")

    items = db.scalars(
        select(RequirementItem).where(RequirementItem.requirement_id == requirement_id)
    ).all()

    # Fulfill items
    for item in items:
        # Deduct from inventory
        inventories = db.scalars(
            select(Inventory).where(Inventory.product_id == item.product_id)
        ).all()

        qty_to_fulfill = item.quantity_required
        for inventory in inventories:
            if qty_to_fulfill <= 0:
                break

            # Deduct physical stock and reserved stock
            deduct = min(inventory.physical_stock, qty_to_fulfill)
            inventory.physical_stock -= deduct
            inventory.reserved_stock -= min(inventory.reserved_stock, deduct)
            qty_to_fulfill -= deduct
            inventory.updated_at = utcnow()

            # Create movement
            movement = StockMovement(
                product_id=item.product_id,
                location_id=inventory.location_id,
                movement_type=StockMovementType.fulfilled,
                quantity=deduct,
                unit=item.unit,
                reference_id=requirement_id,
                notes=f"Fulfilled requirement #{requirement_id}",
                created_by_user_id=current_user.id
            )
            db.add(movement)

        item.quantity_fulfilled = item.quantity_required

    requirement.status = RequirementStatus.fulfilled
    requirement.updated_at = utcnow()
    db.commit()
    db.refresh(requirement)

    return requirement


@router.post("/requirements/{requirement_id}/cancel", response_model=CustomerRequirementOut)
def cancel_requirement(
    requirement_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Cancel requirement and release reserved stock."""
    requirement = db.get(CustomerRequirement, requirement_id)
    if not requirement:
        raise HTTPException(status_code=404, detail="Requirement not found")

    items = db.scalars(
        select(RequirementItem).where(RequirementItem.requirement_id == requirement_id)
    ).all()

    # Release reserved stock
    for item in items:
        inventories = db.scalars(
            select(Inventory).where(Inventory.product_id == item.product_id)
        ).all()

        for inventory in inventories:
            inventory.reserved_stock = max(0, inventory.reserved_stock - item.quantity_reserved)
            inventory.updated_at = utcnow()

    requirement.status = RequirementStatus.cancelled
    requirement.updated_at = utcnow()
    db.commit()
    db.refresh(requirement)

    return requirement


# ================================================================ COMBOS

@router.post("/combos", response_model=ComboOut, status_code=201)
def create_combo(
    data: ComboCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create combo."""
    combo = Combo(
        name=data.name,
        description=data.description,
        created_by_user_id=current_user.id
    )
    db.add(combo)
    db.flush()

    # Add items
    for item_data in data.items:
        product = db.get(Product, item_data.product_id)
        if not product:
            raise HTTPException(status_code=404, detail=f"Product {item_data.product_id} not found")

        item = ComboItem(
            combo_id=combo.id,
            product_id=item_data.product_id,
            quantity=item_data.quantity,
            unit=item_data.unit
        )
        db.add(item)

    db.commit()
    db.refresh(combo)
    combo.items = db.scalars(select(ComboItem).where(ComboItem.combo_id == combo.id)).all()

    return combo


@router.get("/combos", response_model=list[ComboOut])
def list_combos(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    active_only: bool = True,
    search: str | None = None,
    limit: int = Query(100, le=1000),
    offset: int = Query(0, ge=0)
):
    """List combos."""
    query = select(Combo)
    if active_only:
        query = query.where(Combo.active == True)
    if search:
        query = query.where(Combo.name.ilike(f"%{search}%"))

    query = query.limit(limit).offset(offset)
    combos = db.scalars(query).all()

    for combo in combos:
        combo.items = db.scalars(select(ComboItem).where(ComboItem.combo_id == combo.id)).all()

    return combos


@router.get("/combos/{combo_id}", response_model=ComboAvailabilityOut)
def get_combo_availability(
    combo_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get combo with availability check."""
    combo = db.get(Combo, combo_id)
    if not combo:
        raise HTTPException(status_code=404, detail="Combo not found")

    items = db.scalars(select(ComboItem).where(ComboItem.combo_id == combo_id)).all()

    items_info = []
    min_possible_combos = float('inf')

    for item in items:
        available = db.scalar(
            select(func.sum(Inventory.physical_stock - Inventory.reserved_stock))
            .where(Inventory.product_id == item.product_id)
        ) or 0

        possible = int(available / item.quantity) if item.quantity > 0 else 0
        min_possible_combos = min(min_possible_combos, possible)

        items_info.append({
            "product_id": item.product_id,
            "required_qty": item.quantity,
            "available_qty": available,
            "possible_combos": possible
        })

    if min_possible_combos == float('inf'):
        min_possible_combos = 0

    return ComboAvailabilityOut(
        combo_id=combo.id,
        name=combo.name,
        is_available=min_possible_combos > 0,
        items=items_info,
        maximum_possible_combos=int(min_possible_combos)
    )


# ================================================================ DASHBOARD

@router.get("/dashboard", response_model=DashboardOut)
def get_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get inventory dashboard."""
    # Summary counts
    low_stock_count = db.scalar(
        select(func.count(Product.id)).where(Product.active == True)
    ) or 0

    out_of_stock_count = db.scalar(
        select(func.count(func.distinct(Inventory.product_id)))
        .select_from(Inventory)
        .join(Product)
        .where(
            (Inventory.physical_stock <= 0),
            (Product.active == True)
        )
    ) or 0

    pending_reqs = db.scalar(
        select(func.count(CustomerRequirement.id))
        .where(CustomerRequirement.status == RequirementStatus.pending)
    ) or 0

    # Stock by category
    category_data = []
    categories = db.scalars(select(Category).where(Category.active == True)).all()
    for cat in categories:
        total = db.scalar(
            select(func.sum(Inventory.physical_stock))
            .join(Product)
            .where(Product.category_id == cat.id)
        ) or 0

        if total > 0:
            product_count = db.scalar(
                select(func.count(Product.id)).where(Product.category_id == cat.id)
            ) or 0
            category_data.append(StockByCategory(
                category_id=cat.id,
                category_name=cat.name,
                total_quantity=total,
                product_count=product_count
            ))

    # Stock by location
    location_data = []
    locations = db.scalars(select(Location).where(Location.active == True)).all()
    for loc in locations:
        total = db.scalar(
            select(func.sum(Inventory.physical_stock))
            .where(Inventory.location_id == loc.id)
        ) or 0

        if total > 0:
            product_count = db.scalar(
                select(func.count(func.distinct(Inventory.product_id)))
                .where(Inventory.location_id == loc.id)
            ) or 0
            location_data.append(StockByLocation(
                location_id=loc.id,
                location_name=loc.name,
                total_quantity=total,
                product_count=product_count
            ))

    # Recent movements
    movements = db.scalars(
        select(StockMovement)
        .order_by(StockMovement.created_at.desc())
        .limit(10)
    ).all()

    recent = []
    for mov in movements:
        product = db.get(Product, mov.product_id)
        location = db.get(Location, mov.location_id)
        user = db.get(User, mov.created_by_user_id) if mov.created_by_user_id else None

        recent.append(RecentMovement(
            id=mov.id,
            product_name=product.name if product else "Unknown",
            location_name=location.name if location else "Unknown",
            movement_type=mov.movement_type.value if mov.movement_type else "",
            quantity=mov.quantity,
            unit=mov.unit or "",
            created_at=mov.created_at,
            created_by_name=user.name if user else None
        ))

    total_stock = db.scalar(
        select(func.sum(Inventory.physical_stock))
        .select_from(Inventory)
    ) or 0

    return DashboardOut(
        summary=DashboardSummary(
            total_stock_value=total_stock,
            low_stock_count=low_stock_count,
            out_of_stock_count=out_of_stock_count,
            pending_requirements_count=pending_reqs
        ),
        stock_by_category=category_data,
        stock_by_location=location_data,
        recent_movements=recent
    )


# ================================================================ SEARCH

@router.get("/search", response_model=SearchResultsOut)
def search(
    q: str = Query(..., min_length=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Global search across products, categories, locations."""
    search_term = f"%{q}%"

    products = db.scalars(
        select(Product)
        .where(Product.active == True, Product.name.ilike(search_term))
        .limit(10)
    ).all()

    categories = db.scalars(
        select(Category)
        .where(Category.active == True, Category.name.ilike(search_term))
        .limit(10)
    ).all()

    locations = db.scalars(
        select(Location)
        .where(Location.active == True, Location.name.ilike(search_term))
        .limit(10)
    ).all()

    return SearchResultsOut(
        products=[SearchResult(type="product", id=p.id, name=p.name) for p in products],
        categories=[SearchResult(type="category", id=c.id, name=c.name) for c in categories],
        locations=[SearchResult(type="location", id=l.id, name=l.name) for l in locations]
    )
