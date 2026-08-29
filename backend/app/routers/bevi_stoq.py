"""Bevi Stoq inventory management API routes."""
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from ..utils_bevi_stoq import are_units_compatible, validate_unit

log = logging.getLogger(__name__)

from ..database import get_db
from ..deps import get_current_user
from ..models import User
from ..bevi_stoq_models import (
    Category, Product, Location, Inventory, StockMovement,
    CustomerRequirement, RequirementItem, CustomerPurchase, Combo, ComboItem, Restock,
    StockMovementType, RequirementStatus, PaymentStatus, RestockStatus
)
from ..schemas_bevi_stoq import (
    CategoryCreate, CategoryUpdate, CategoryOut,
    ProductCreate, ProductUpdate, ProductOut,
    LocationCreate, LocationUpdate, LocationOut,
    InventoryOut,
    StockMovementCreate, StockMovementOut,
    RestockCreate, RestockUpdate, RestockOut,
    RequirementCreate, RequirementOut, RequirementItemOut,
    CustomerPurchaseCreate, CustomerPurchaseUpdate, CustomerPurchaseOut,
    ComboCreate, ComboOut, ComboItemOut, ComboItemCreate,
    DashboardOut, DashboardSummary, ProductStatus
)
from pydantic import BaseModel

class StockReportItem(BaseModel):
    product_name: str
    category_name: str
    physical_stock: float
    reserved_stock: float
    available_stock: float
    unit: str
    alert_quantity: float | None
    status: str
    location: str

class InventoryReport(BaseModel):
    total_products: int
    total_stock_value: float
    out_of_stock_count: int
    items: list[StockReportItem]

class MovementReport(BaseModel):
    total_movements: int
    by_type: dict
    timeline: list[dict]

router = APIRouter(prefix="/api/bevi-stoq", tags=["bevi-stoq"])

# ================================================================ CATEGORIES
@router.get("/categories", response_model=list[CategoryOut])
def list_categories(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return db.scalars(select(Category).where(Category.active == True)).all()

@router.post("/categories", response_model=CategoryOut, status_code=201)
def create_category(data: CategoryCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    cat = Category(name=data.name, description=data.description, created_by_user_id=user.id)
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return cat

@router.get("/categories/{id}", response_model=CategoryOut)
def get_category(id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    cat = db.get(Category, id)
    if not cat: raise HTTPException(status_code=404, detail="Category not found")
    return cat

@router.put("/categories/{id}", response_model=CategoryOut)
def update_category(id: int, data: CategoryUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    cat = db.get(Category, id)
    if not cat: raise HTTPException(status_code=404, detail="Category not found")
    if data.name: cat.name = data.name
    if data.description is not None: cat.description = data.description
    if data.active is not None: cat.active = data.active
    cat.updated_by_user_id = user.id
    db.commit()
    db.refresh(cat)
    return cat

@router.delete("/categories/{id}", status_code=204)
def delete_category(id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    cat = db.get(Category, id)
    if not cat: raise HTTPException(status_code=404, detail="Category not found")
    db.delete(cat)
    db.commit()

# ================================================================ LOCATIONS
@router.get("/locations", response_model=list[LocationOut])
def list_locations(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return db.scalars(select(Location).where(Location.active == True)).all()

@router.post("/locations", response_model=LocationOut, status_code=201)
def create_location(data: LocationCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    loc = Location(name=data.name, description=data.description, created_by_user_id=user.id)
    db.add(loc)
    db.commit()
    db.refresh(loc)
    return loc

@router.get("/locations/{id}", response_model=LocationOut)
def get_location(id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    loc = db.get(Location, id)
    if not loc: raise HTTPException(status_code=404, detail="Location not found")
    return loc

@router.put("/locations/{id}", response_model=LocationOut)
def update_location(id: int, data: LocationUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    loc = db.get(Location, id)
    if not loc: raise HTTPException(status_code=404, detail="Location not found")
    if data.name: loc.name = data.name
    if data.description is not None: loc.description = data.description
    if data.active is not None: loc.active = data.active
    loc.updated_by_user_id = user.id
    db.commit()
    db.refresh(loc)
    return loc

@router.delete("/locations/{id}", status_code=204)
def delete_location(id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    loc = db.get(Location, id)
    if not loc: raise HTTPException(status_code=404, detail="Location not found")
    db.delete(loc)
    db.commit()

# ================================================================ PRODUCTS
@router.get("/products", response_model=list[ProductOut])
def list_products(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    products = db.scalars(select(Product).where(Product.active == True)).all()
    log.info(f"LIST PRODUCTS: Retrieved {len(products)} active products")
    return products

@router.get("/debug/schema", tags=["debug"])
def debug_schema(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    """Debug endpoint to check database schema and state"""
    try:
        from sqlalchemy import text, inspect

        inspector = inspect(db.connection().connection)
        bs_products_cols = inspector.get_columns('bs_products', schema='bevigrow')
        bs_movements_cols = inspector.get_columns('bs_stock_movements', schema='bevigrow')

        product_count = db.scalar(select(func.count(Product.id)))
        movement_count = db.scalar(select(func.count(StockMovement.id)))
        location_count = db.scalar(select(func.count(Location.id)))

        # Check movement_type column size
        movement_type_col = next((c for c in bs_movements_cols if c['name'] == 'movement_type'), None)

        return {
            "status": "ok",
            "products_table_columns": [f"{c['name']} ({c['type']})" for c in bs_products_cols],
            "movements_table_columns": [f"{c['name']} ({c['type']})" for c in bs_movements_cols],
            "movement_type_info": f"{movement_type_col['name']} {movement_type_col['type']}" if movement_type_col else "NOT FOUND",
            "data_counts": {
                "products": product_count,
                "movements": movement_count,
                "locations": location_count
            }
        }
    except Exception as e:
        log.error(f"DEBUG SCHEMA ERROR: {e}", exc_info=True)
        return {"status": "error", "detail": str(e)}

@router.post("/products", response_model=ProductOut, status_code=201)
def create_product(data: ProductCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        # Normalize product name: trim whitespace
        product_name = data.name.strip()

        log.info(f"CREATE PRODUCT: Received request: name={product_name}, category_id={data.category_id}, unit={data.default_unit}, alert_quantity={data.alert_quantity}, user={user.id}")

        if not product_name:
            raise HTTPException(status_code=400, detail="Product name cannot be empty")

        # Validate category exists (if provided)
        if data.category_id is not None:
            category = db.get(Category, data.category_id)
            if not category:
                log.warning(f"CREATE PRODUCT: Invalid category_id {data.category_id}")
                raise HTTPException(status_code=400, detail=f"Category {data.category_id} not found")

        # Check for duplicate active product with same name (case-insensitive)
        # Only check active products; ignore soft-deleted ones
        existing_query = select(Product).where(
            and_(
                Product.name.ilike(product_name),
                Product.active == True
            )
        )

        # If category is specified, also match by category
        if data.category_id is not None:
            existing_query = existing_query.where(Product.category_id == data.category_id)

        existing = db.scalar(existing_query)

        if existing:
            log.warning(f"CREATE PRODUCT: Found duplicate: id={existing.id}, name='{existing.name}', category_id={existing.category_id}, active={existing.active}")
            if data.category_id is not None:
                raise HTTPException(status_code=400, detail=f"Product '{product_name}' already exists in this category")
            else:
                raise HTTPException(status_code=400, detail=f"Product '{product_name}' already exists")

        # Validate unit
        if not validate_unit(data.default_unit):
            log.warning(f"CREATE PRODUCT: Invalid unit '{data.default_unit}'")
            raise HTTPException(status_code=400, detail=f"Invalid unit '{data.default_unit}'")

        # Validate alert quantity (optional, but must be non-negative if provided)
        if data.alert_quantity is not None and data.alert_quantity < 0:
            log.warning(f"CREATE PRODUCT: Invalid alert_quantity {data.alert_quantity}")
            raise HTTPException(status_code=400, detail="Alert quantity must be non-negative")

        log.info(f"CREATE PRODUCT: Validation passed, creating product with user_id={user.id}")

        # Verify user exists
        from sqlalchemy import text
        user_check = db.scalar(select(func.count(User.id)).where(User.id == user.id))
        if user_check == 0:
            log.error(f"CREATE PRODUCT: User {user.id} not found in database")
            raise HTTPException(status_code=400, detail=f"Current user (id={user.id}) not found in database")

        prod = Product(
            name=product_name,
            category_id=data.category_id,
            default_unit=data.default_unit,
            alert_quantity=data.alert_quantity,
            created_by_user_id=user.id
        )
        log.info(f"CREATE PRODUCT: Product object created (not yet in DB)")
        db.add(prod)
        db.flush()
        log.info(f"CREATE PRODUCT: Flushed to session")
        db.commit()
        log.info(f"CREATE PRODUCT: Committed to database")
        db.refresh(prod)
        log.info(f"CREATE PRODUCT: Success, created product {prod.id} with name='{prod.name}'")
        return prod
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"CREATE PRODUCT: Unexpected error: {type(e).__name__}: {str(e)}", exc_info=True)
        import traceback
        log.error(f"CREATE PRODUCT: Full traceback:\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Error creating product: {str(e)}")

@router.post("/products/debug/echo", tags=["debug"])
def debug_echo(data: ProductCreate):
    """Debug endpoint: echo back the received payload"""
    log.info(f"DEBUG ECHO: Received payload: {data.model_dump()}")
    return {"received": data.model_dump(), "ok": True}

@router.get("/products/{id}", response_model=ProductOut)
def get_product(id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    prod = db.get(Product, id)
    if not prod: raise HTTPException(status_code=404, detail="Product not found")
    return prod

@router.put("/products/{id}", response_model=ProductOut)
def update_product(id: int, data: ProductUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    prod = db.get(Product, id)
    if not prod: raise HTTPException(status_code=404, detail="Product not found")
    if data.name: prod.name = data.name
    if data.category_id: prod.category_id = data.category_id
    if data.default_unit: prod.default_unit = data.default_unit
    if data.alert_quantity is not None: prod.alert_quantity = data.alert_quantity
    if data.active is not None: prod.active = data.active
    prod.updated_by_user_id = user.id
    db.commit()
    db.refresh(prod)
    return prod

@router.delete("/products/{id}", status_code=204)
def delete_product(id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    prod = db.get(Product, id)
    if not prod: raise HTTPException(status_code=404, detail="Product not found")
    db.delete(prod)
    db.commit()

# ================================================================ INVENTORY
@router.get("/inventory", response_model=list[InventoryOut])
def list_inventory(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    try:
        items = db.scalars(select(Inventory)).all()
        for item in items:
            item.available_stock = item.physical_stock - item.reserved_stock
        return items
    except Exception as e:
        log.error(f"Inventory list error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Inventory error: {str(e)}")

@router.get("/inventory/{product_id}/{location_id}", response_model=InventoryOut)
def get_inventory(product_id: int, location_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    inv = db.scalar(select(Inventory).where(and_(Inventory.product_id == product_id, Inventory.location_id == location_id)))
    if not inv: raise HTTPException(status_code=404, detail="Inventory not found")
    inv.available_stock = inv.physical_stock - inv.reserved_stock
    return inv

# ================================================================ STOCK MOVEMENTS
@router.post("/stock-movements", response_model=StockMovementOut, status_code=201)
def create_stock_movement(data: StockMovementCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        log.info(f"CREATE STOCK MOVEMENT: product_id={data.product_id}, type={data.movement_type}, quantity={data.quantity}, unit={data.unit}")

        # Validate product exists
        product = db.get(Product, data.product_id)
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")

        # Validate unit compatibility with product's unit
        if data.unit and not are_units_compatible(data.unit, product.default_unit):
            raise HTTPException(status_code=400, detail=f"Unit '{data.unit}' is not compatible with product unit '{product.default_unit}'")

        # Validate locations if specified
        if data.from_location_id:
            from_loc = db.get(Location, data.from_location_id)
            if not from_loc:
                raise HTTPException(status_code=404, detail="From location not found")

        if data.to_location_id:
            to_loc = db.get(Location, data.to_location_id)
            if not to_loc:
                raise HTTPException(status_code=404, detail="To location not found")

        # Validate quantity
        if data.quantity <= 0:
            raise HTTPException(status_code=400, detail="Quantity must be positive")

        # For transfers between locations, validate stock and update inventory
        if data.from_location_id and data.to_location_id and data.movement_type == StockMovementType.transfer.value:
            from_inv = db.scalar(select(Inventory).where(and_(Inventory.product_id == data.product_id, Inventory.location_id == data.from_location_id)).with_for_update())
            if not from_inv or from_inv.physical_stock < data.quantity:
                raise HTTPException(status_code=400, detail=f"Insufficient stock at source location. Required: {data.quantity}, Available: {from_inv.physical_stock if from_inv else 0}")

            to_inv = db.scalar(select(Inventory).where(and_(Inventory.product_id == data.product_id, Inventory.location_id == data.to_location_id)).with_for_update())
            if not to_inv:
                to_inv = Inventory(product_id=data.product_id, location_id=data.to_location_id, physical_stock=0, reserved_stock=0, updated_by_user_id=user.id)
                db.add(to_inv)
                db.flush()
                to_inv = db.scalar(select(Inventory).where(and_(Inventory.product_id == data.product_id, Inventory.location_id == data.to_location_id)).with_for_update())

            from_inv.physical_stock -= data.quantity
            to_inv.physical_stock += data.quantity
        elif data.to_location_id:
            # For simple stock additions, create or update inventory for the target location
            to_inv = db.scalar(select(Inventory).where(and_(Inventory.product_id == data.product_id, Inventory.location_id == data.to_location_id)).with_for_update())
            if not to_inv:
                to_inv = Inventory(product_id=data.product_id, location_id=data.to_location_id, physical_stock=0, reserved_stock=0, updated_by_user_id=user.id)
                db.add(to_inv)
                db.flush()
                to_inv = db.scalar(select(Inventory).where(and_(Inventory.product_id == data.product_id, Inventory.location_id == data.to_location_id)).with_for_update())
            to_inv.physical_stock += data.quantity

        movement = StockMovement(product_id=data.product_id, from_location_id=data.from_location_id, to_location_id=data.to_location_id, movement_type=StockMovementType(data.movement_type), quantity=data.quantity, unit=data.unit, reference_id=data.reference_id, notes=data.notes, created_by_user_id=user.id)
        db.add(movement)
        db.commit()
        db.refresh(movement)
        log.info(f"CREATE STOCK MOVEMENT: Success, created movement {movement.id}")
        return movement
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"CREATE STOCK MOVEMENT: Error: {type(e).__name__}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Stock movement error: {str(e)}")

@router.get("/stock-movements", response_model=list[StockMovementOut])
def list_stock_movements(db: Session = Depends(get_db), _: User = Depends(get_current_user), product_id: int | None = None, limit: int = Query(100, le=1000)):
    query = select(StockMovement)
    if product_id: query = query.where(StockMovement.product_id == product_id)
    return db.scalars(query.order_by(StockMovement.created_at.desc()).limit(limit)).all()

# ================================================================ RESTOCKS
@router.post("/restocks", response_model=RestockOut, status_code=201)
def create_restock(data: RestockCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    restock = Restock(product_id=data.product_id, location_id=data.location_id, quantity=data.quantity, unit=data.unit, restock_date=data.restock_date, supplier_name=data.supplier_name, cost_per_unit=data.cost_per_unit, total_cost=data.total_cost, reference_id=data.reference_id, notes=data.notes, created_by_user_id=user.id)
    db.add(restock)
    db.commit()
    db.refresh(restock)
    return restock

@router.get("/restocks", response_model=list[RestockOut])
def list_restocks(db: Session = Depends(get_db), _: User = Depends(get_current_user), status: str | None = None, limit: int = Query(100, le=1000)):
    query = select(Restock)
    if status: query = query.where(Restock.status == status)
    return db.scalars(query.order_by(Restock.created_at.desc()).limit(limit)).all()

@router.post("/restocks/{id}/receive", response_model=RestockOut)
def receive_restock(id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    restock = db.get(Restock, id)
    if not restock: raise HTTPException(status_code=404, detail="Restock not found")

    inv = db.scalar(select(Inventory).where(and_(Inventory.product_id == restock.product_id, Inventory.location_id == restock.location_id)))
    if not inv:
        inv = Inventory(product_id=restock.product_id, location_id=restock.location_id, physical_stock=0, reserved_stock=0, updated_by_user_id=user.id)
        db.add(inv)

    inv.physical_stock += restock.quantity
    inv.updated_by_user_id = user.id
    restock.status = RestockStatus.received
    restock.updated_by_user_id = user.id

    movement = StockMovement(product_id=restock.product_id, to_location_id=restock.location_id, movement_type=StockMovementType.stock_added, quantity=restock.quantity, unit=restock.unit, reference_id=restock.id, notes=f"Restock from {restock.supplier_name}", created_by_user_id=user.id)
    db.add(movement)
    db.commit()
    db.refresh(restock)
    return restock

@router.put("/restocks/{id}", response_model=RestockOut)
def update_restock(id: int, data: RestockUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    restock = db.get(Restock, id)
    if not restock: raise HTTPException(status_code=404, detail="Restock not found")
    if data.quantity: restock.quantity = data.quantity
    if data.supplier_name: restock.supplier_name = data.supplier_name
    if data.status: restock.status = data.status
    restock.updated_by_user_id = user.id
    db.commit()
    db.refresh(restock)
    return restock

# ================================================================ CUSTOMER REQUIREMENTS
@router.post("/customer-requirements", response_model=RequirementOut, status_code=201)
def create_requirement(data: RequirementCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    req = CustomerRequirement(customer_name=data.customer_name, contact_id=data.contact_id, created_by_user_id=user.id)
    db.add(req)
    db.flush()

    for item_data in data.items:
        item = RequirementItem(requirement_id=req.id, product_id=item_data.product_id, quantity_required=item_data.quantity_required)
        db.add(item)

    db.commit()
    db.refresh(req)
    return req

@router.get("/customer-requirements", response_model=list[RequirementOut])
def list_requirements(db: Session = Depends(get_db), _: User = Depends(get_current_user), status: str | None = None):
    query = select(CustomerRequirement)
    if status: query = query.where(CustomerRequirement.status == status)
    return db.scalars(query.order_by(CustomerRequirement.created_at.desc())).all()

@router.post("/customer-requirements/{id}/reserve", response_model=RequirementOut)
def reserve_requirement(id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Reserve stock for a customer requirement (allocates from any location with available stock).

    Uses row-level locking (SELECT FOR UPDATE) to prevent concurrent reservation race conditions.
    """
    req = db.get(CustomerRequirement, id)
    if not req: raise HTTPException(status_code=404, detail="Requirement not found")
    if req.status == RequirementStatus.reserved: raise HTTPException(status_code=400, detail="Already reserved")

    for item in req.items:
        inventories = db.scalars(select(Inventory).where(Inventory.product_id == item.product_id).order_by(Inventory.location_id).with_for_update()).all()
        total_available = sum(inv.physical_stock - inv.reserved_stock for inv in inventories)
        if total_available < item.quantity_required:
            raise HTTPException(status_code=400, detail=f"Insufficient stock for product {item.product_id}. Required: {item.quantity_required}, Available: {total_available}")

        remaining = item.quantity_required
        for inv in inventories:
            available = inv.physical_stock - inv.reserved_stock
            if available > 0 and remaining > 0:
                reserve_qty = min(available, remaining)
                inv.reserved_stock += reserve_qty
                remaining -= reserve_qty

        item.quantity_reserved = item.quantity_required

    req.status = RequirementStatus.reserved
    req.updated_by_user_id = user.id
    db.commit()
    db.refresh(req)
    return req

@router.post("/customer-requirements/{id}/fulfill", response_model=RequirementOut)
def fulfill_requirement(id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Fulfill a reserved requirement (deduct from inventory).

    Uses row-level locking (SELECT FOR UPDATE) to prevent concurrent fulfillment race conditions.
    """
    req = db.get(CustomerRequirement, id)
    if not req: raise HTTPException(status_code=404, detail="Requirement not found")
    if req.status != RequirementStatus.reserved: raise HTTPException(status_code=400, detail="Requirement must be reserved first")

    for item in req.items:
        inventories = db.scalars(select(Inventory).where(Inventory.product_id == item.product_id).with_for_update()).all()
        remaining = item.quantity_reserved
        for inv in inventories:
            if remaining <= 0: break
            if inv.reserved_stock > 0:
                deduct_qty = min(inv.reserved_stock, remaining)
                inv.physical_stock -= deduct_qty
                inv.reserved_stock -= deduct_qty
                remaining -= deduct_qty
                movement = StockMovement(product_id=item.product_id, from_location_id=inv.location_id, movement_type=StockMovementType.stock_removed, quantity=deduct_qty, unit=item.unit, reference_id=req.id, notes=f"Fulfillment for {req.customer_name}", created_by_user_id=user.id)
                db.add(movement)

        item.quantity_fulfilled = item.quantity_reserved

    req.status = RequirementStatus.fulfilled
    req.updated_by_user_id = user.id
    db.commit()
    db.refresh(req)
    return req

@router.post("/customer-requirements/{id}/cancel", response_model=RequirementOut)
def cancel_requirement(id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Cancel a requirement and release reserved stock."""
    req = db.get(CustomerRequirement, id)
    if not req: raise HTTPException(status_code=404, detail="Requirement not found")
    if req.status == RequirementStatus.cancelled: raise HTTPException(status_code=400, detail="Already cancelled")

    for item in req.items:
        if item.quantity_reserved > 0:
            inventories = db.scalars(select(Inventory).where(Inventory.product_id == item.product_id)).all()
            remaining = item.quantity_reserved
            for inv in inventories:
                if remaining <= 0: break
                if inv.reserved_stock > 0:
                    release_qty = min(inv.reserved_stock, remaining)
                    inv.reserved_stock -= release_qty
                    remaining -= release_qty
            item.quantity_reserved = 0

    req.status = RequirementStatus.cancelled
    req.updated_by_user_id = user.id
    db.commit()
    db.refresh(req)
    return req

# ================================================================ CUSTOMER PURCHASES
@router.post("/customer-purchases", response_model=CustomerPurchaseOut, status_code=201)
def create_purchase(data: CustomerPurchaseCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Create customer purchase with automatic inventory deduction.

    Uses row-level locking (SELECT FOR UPDATE) to prevent concurrent purchase race conditions.
    Validates sufficient stock before creating purchase to prevent partial fulfillment.
    """
    inventories = db.scalars(select(Inventory).where(Inventory.product_id == data.product_id).with_for_update()).all()
    total_available = sum(inv.physical_stock for inv in inventories)
    if total_available < data.quantity:
        raise HTTPException(status_code=400, detail=f"Insufficient stock. Required: {data.quantity}, Available: {total_available}, Shortage: {data.quantity - total_available}")

    purchase = CustomerPurchase(customer_name=data.customer_name, contact_id=data.contact_id, product_id=data.product_id, quantity=data.quantity, unit=data.unit, purchase_date=data.purchase_date, payment_status=PaymentStatus(data.payment_status), payment_method=data.payment_method, amount=data.amount, notes=data.notes, created_by_user_id=user.id)
    db.add(purchase)
    db.flush()

    inventories = db.scalars(select(Inventory).where(Inventory.product_id == data.product_id).order_by(Inventory.location_id).with_for_update()).all()
    remaining = data.quantity
    for inv in inventories:
        if remaining <= 0: break
        if inv.physical_stock > 0:
            deduct_qty = min(inv.physical_stock, remaining)
            inv.physical_stock -= deduct_qty
            remaining -= deduct_qty
            movement = StockMovement(product_id=data.product_id, from_location_id=inv.location_id, movement_type=StockMovementType.stock_removed, quantity=deduct_qty, unit=data.unit, reference_id=purchase.id, notes=f"Sale to {data.customer_name}", created_by_user_id=user.id)
            db.add(movement)

    db.commit()
    db.refresh(purchase)
    return purchase

@router.get("/customer-purchases", response_model=list[CustomerPurchaseOut])
def list_purchases(db: Session = Depends(get_db), _: User = Depends(get_current_user), payment_status: str | None = None, limit: int = Query(100, le=1000)):
    query = select(CustomerPurchase)
    if payment_status: query = query.where(CustomerPurchase.payment_status == payment_status)
    return db.scalars(query.order_by(CustomerPurchase.created_at.desc()).limit(limit)).all()

@router.put("/customer-purchases/{id}", response_model=CustomerPurchaseOut)
def update_purchase(id: int, data: CustomerPurchaseUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    purchase = db.get(CustomerPurchase, id)
    if not purchase: raise HTTPException(status_code=404, detail="Purchase not found")
    if data.payment_status: purchase.payment_status = PaymentStatus(data.payment_status)
    if data.amount: purchase.amount = data.amount
    purchase.updated_by_user_id = user.id
    db.commit()
    db.refresh(purchase)
    return purchase

# ================================================================ COMBOS
@router.post("/combos", response_model=ComboOut, status_code=201)
def create_combo(data: ComboCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    combo = Combo(name=data.name, description=data.description, created_by_user_id=user.id)
    db.add(combo)
    db.flush()

    for item_data in data.items:
        item = ComboItem(combo_id=combo.id, product_id=item_data.product_id, quantity=item_data.quantity, unit=item_data.unit)
        db.add(item)

    db.commit()
    db.refresh(combo)
    return combo

@router.get("/combos", response_model=list[ComboOut])
def list_combos(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return db.scalars(select(Combo).where(Combo.active == True)).all()

@router.get("/combos/{id}", response_model=ComboOut)
def get_combo(id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    combo = db.get(Combo, id)
    if not combo: raise HTTPException(status_code=404, detail="Combo not found")
    return combo

@router.put("/combos/{id}", response_model=ComboOut)
def update_combo(id: int, data: ComboCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    combo = db.get(Combo, id)
    if not combo: raise HTTPException(status_code=404, detail="Combo not found")
    combo.name = data.name
    combo.description = data.description
    combo.updated_by_user_id = user.id
    db.commit()
    db.refresh(combo)
    return combo

@router.delete("/combos/{id}", status_code=204)
def delete_combo(id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    combo = db.get(Combo, id)
    if not combo: raise HTTPException(status_code=404, detail="Combo not found")
    db.delete(combo)
    db.commit()

# ================================================================ DASHBOARD
@router.get("/dashboard", response_model=DashboardOut)
def get_dashboard(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    try:
        total_products = db.scalar(select(func.count(Product.id)).where(Product.active == True)) or 0
        total_locations = db.scalar(select(func.count(Location.id)).where(Location.active == True)) or 0
        total_categories = db.scalar(select(func.count(Category.id)).where(Category.active == True)) or 0

        out_of_stock_list = []

        stmt = (
            select(
                Product.id,
                Product.name,
                func.coalesce(func.sum(Inventory.physical_stock - Inventory.reserved_stock), 0).label("available")
            )
            .outerjoin(Inventory, Inventory.product_id == Product.id)
            .where(Product.active == True)
            .group_by(Product.id, Product.name)
        )

        for row in db.execute(stmt):
            available = row.available or 0
            # Only show OUT_OF_STOCK when stock is exactly 0 or below
            if available <= 0:
                out_of_stock_list.append(ProductStatus(product_id=row.id, product_name=row.name, status="OUT_OF_STOCK", current_stock=available, threshold=None))

        recent = db.scalars(select(StockMovement).order_by(StockMovement.created_at.desc()).limit(10)).all()

        return DashboardOut(
            summary=DashboardSummary(total_products=total_products, out_of_stock_count=len(out_of_stock_list), total_locations=total_locations, total_categories=total_categories),
            out_of_stock_products=out_of_stock_list,
            recent_movements=[StockMovementOut.model_validate(m) for m in recent]
        )
    except Exception as e:
        log.error(f"Dashboard error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Dashboard error: {str(e)}")

# ================================================================ ADVANCED REPORTS
@router.get("/reports/inventory", response_model=InventoryReport)
def inventory_report(db: Session = Depends(get_db), _: User = Depends(get_current_user), category_id: int | None = None, location_id: int | None = None):
    try:
        stmt = (
            select(
                Product.id,
                Product.name,
                Product.category_id,
                Product.default_unit,
                Product.alert_quantity,
                Category.name.label("category_name"),
                Inventory.id.label("inv_id"),
                Inventory.physical_stock,
                Inventory.reserved_stock,
                Inventory.location_id,
                Location.name.label("location_name"),
            )
            .outerjoin(Category, Category.id == Product.category_id)
            .outerjoin(Inventory, Inventory.product_id == Product.id)
            .outerjoin(Location, Location.id == Inventory.location_id)
            .where(Product.active == True)
        )

        if category_id:
            stmt = stmt.where(Product.category_id == category_id)
        if location_id:
            stmt = stmt.where(Inventory.location_id == location_id)

        items = []
        out_of_stock_count = 0
        products_seen = set()

        for row in db.execute(stmt):
            if row.inv_id is None:
                continue

            available = row.physical_stock - row.reserved_stock
            products_seen.add(row.id)

            # Only show OUT_OF_STOCK when stock is 0 or below
            if available <= 0:
                status = "OUT_OF_STOCK"
                out_of_stock_count += 1
            else:
                status = "NORMAL"

            items.append(StockReportItem(
                product_name=row.name,
                category_name=row.category_name or "Unknown",
                physical_stock=row.physical_stock,
                reserved_stock=row.reserved_stock,
                available_stock=available,
                unit=row.default_unit,
                alert_quantity=row.alert_quantity,
                status=status,
                location=row.location_name or "Unknown"
            ))

        return InventoryReport(
            total_products=len(products_seen),
            total_stock_value=0,
            out_of_stock_count=out_of_stock_count,
            items=items
        )
    except Exception as e:
        log.error(f"Inventory report error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Inventory report error: {str(e)}")

@router.get("/reports/movements", response_model=MovementReport)
def movements_report(db: Session = Depends(get_db), _: User = Depends(get_current_user), days: int = 30):
    from datetime import timedelta
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)

    movements = db.scalars(
        select(StockMovement)
        .where(StockMovement.created_at >= cutoff_date)
        .order_by(StockMovement.created_at.desc())
    ).all()

    by_type = {}
    for movement in movements:
        type_name = movement.movement_type.value
        by_type[type_name] = by_type.get(type_name, 0) + 1

    timeline = [
        {
            "date": m.created_at.isoformat(),
            "type": m.movement_type.value,
            "product_id": m.product_id,
            "quantity": m.quantity,
            "unit": m.unit
        }
        for m in movements[:50]
    ]

    return MovementReport(
        total_movements=len(movements),
        by_type=by_type,
        timeline=timeline
    )

@router.get("/reports/stock-by-category")
def stock_by_category(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    categories = db.scalars(select(Category).where(Category.active == True)).all()
    result = []

    for cat in categories:
        products = db.scalars(select(Product).where(and_(Product.category_id == cat.id, Product.active == True))).all()
        total_physical = 0
        total_available = 0

        for prod in products:
            phys = db.scalar(select(func.coalesce(func.sum(Inventory.physical_stock), 0)).where(Inventory.product_id == prod.id)) or 0
            avail = db.scalar(select(func.coalesce(func.sum(Inventory.physical_stock - Inventory.reserved_stock), 0)).where(Inventory.product_id == prod.id)) or 0
            total_physical += phys
            total_available += avail

        result.append({
            "category": cat.name,
            "product_count": len(products),
            "total_physical_stock": total_physical,
            "total_available_stock": total_available
        })

    return result

@router.get("/reports/stock-by-location")
def stock_by_location(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    locations = db.scalars(select(Location).where(Location.active == True)).all()
    result = []

    for loc in locations:
        inventories = db.scalars(select(Inventory).where(Inventory.location_id == loc.id)).all()
        total_physical = sum(inv.physical_stock for inv in inventories)
        total_available = sum(inv.physical_stock - inv.reserved_stock for inv in inventories)

        result.append({
            "location": loc.name,
            "item_count": len(inventories),
            "total_physical_stock": total_physical,
            "total_available_stock": total_available
        })

    return result
