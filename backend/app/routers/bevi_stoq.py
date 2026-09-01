"""Bevi Stoq inventory management API routes."""
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from ..utils_bevi_stoq import are_units_compatible, validate_unit
from ..unit_converter import convert_to_base_unit, get_unit_dimension

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
            notes=data.notes,
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
    try:
        from ..unit_converter import convert_to_base_unit, are_units_compatible
        log.info(f"UPDATE PRODUCT: id={id}, data={data.model_dump()}, user={user.id}")

        prod = db.scalars(select(Product).where(Product.id == id).with_for_update()).first()
        if not prod:
            log.error(f"UPDATE PRODUCT: Product {id} not found")
            raise HTTPException(status_code=404, detail="Product not found")

        log.info(f"UPDATE PRODUCT: Before - name={prod.name}, unit={prod.default_unit}, category={prod.category_id}")
        old_unit = prod.default_unit
        old_quantity_in_base = None

        # CRITICAL: Handle quantity adjustment BEFORE changing unit
        if data.quantity is not None:
            log.info(f"UPDATE PRODUCT: Quantity provided={data.quantity}")

            # NEW unit: use data.default_unit if provided, otherwise use old unit
            new_unit = data.default_unit if data.default_unit is not None else prod.default_unit
            log.info(f"UPDATE PRODUCT: new_unit={new_unit}, old_unit={old_unit}")

            # Validate unit compatibility
            if not are_units_compatible(new_unit, old_unit):
                log.error(f"UPDATE PRODUCT: Unit mismatch - cannot convert {new_unit} to {old_unit}")
                raise HTTPException(status_code=400, detail=f"Cannot change from {old_unit} to {new_unit} - incompatible units")

            # Get current stock across all locations
            inventories_for_calc = db.scalars(select(Inventory).where(Inventory.product_id == id)).all()
            current_total_in_base = sum((inv.physical_stock - inv.reserved_stock) for inv in inventories_for_calc)
            log.info(f"UPDATE PRODUCT: Current total stock = {current_total_in_base} {old_unit}")

            # Convert new quantity to old unit (base unit) for comparison
            new_qty_in_base = convert_to_base_unit(data.quantity, new_unit, old_unit)
            log.info(f"UPDATE PRODUCT: New quantity {data.quantity} {new_unit} = {new_qty_in_base} {old_unit}")

            # Calculate difference
            qty_diff = new_qty_in_base - current_total_in_base
            log.info(f"UPDATE PRODUCT: Difference = {new_qty_in_base} - {current_total_in_base} = {qty_diff} {old_unit}")

            # Apply stock adjustment if needed
            if abs(qty_diff) > 0.000001:  # Use small epsilon for float comparison
                inventories_for_update = db.scalars(
                    select(Inventory).where(Inventory.product_id == id).order_by(Inventory.location_id).with_for_update()
                ).all()

                if qty_diff > 0:
                    # Add stock
                    remaining = qty_diff
                    for inv in inventories_for_update:
                        if remaining <= 0.000001: break
                        add_qty = min(remaining, qty_diff)
                        inv.physical_stock += add_qty
                        remaining -= add_qty
                        movement = StockMovement(
                            product_id=id, to_location_id=inv.location_id,
                            movement_type=StockMovementType.stock_added,
                            quantity=add_qty, unit=old_unit,
                            notes=f"Product edit adjustment: {data.quantity} {new_unit} (was in {old_unit})",
                            created_by_user_id=user.id
                        )
                        db.add(movement)
                        log.info(f"UPDATE PRODUCT: Stock added {add_qty} {old_unit} to location {inv.location_id}")
                else:
                    # Remove stock
                    remaining = abs(qty_diff)
                    for inv in inventories_for_update:
                        if remaining <= 0.000001: break
                        available = inv.physical_stock - inv.reserved_stock
                        if available > 0.000001:
                            remove_qty = min(available, remaining)
                            inv.physical_stock -= remove_qty
                            remaining -= remove_qty
                            movement = StockMovement(
                                product_id=id, from_location_id=inv.location_id,
                                movement_type=StockMovementType.stock_removed,
                                quantity=remove_qty, unit=old_unit,
                                notes=f"Product edit adjustment: {data.quantity} {new_unit} (was in {old_unit})",
                                created_by_user_id=user.id
                            )
                            db.add(movement)
                            log.info(f"UPDATE PRODUCT: Stock removed {remove_qty} {old_unit} from location {inv.location_id}")
            else:
                log.info(f"UPDATE PRODUCT: No stock adjustment needed (difference ≈ 0)")

        # Update other fields
        if data.name is not None:
            prod.name = data.name
            log.info(f"UPDATE PRODUCT: Updated name to '{prod.name}'")

        if data.category_id is not None:
            prod.category_id = data.category_id
            log.info(f"UPDATE PRODUCT: Updated category to {prod.category_id}")

        if data.default_unit is not None:
            prod.default_unit = data.default_unit
            log.info(f"UPDATE PRODUCT: Updated unit to '{prod.default_unit}'")

        if data.alert_quantity is not None:
            prod.alert_quantity = data.alert_quantity
            log.info(f"UPDATE PRODUCT: Updated alert_quantity to {prod.alert_quantity}")

        if data.notes is not None:
            prod.notes = data.notes
            log.info(f"UPDATE PRODUCT: Updated notes")

        if data.active is not None:
            prod.active = data.active
            log.info(f"UPDATE PRODUCT: Updated active to {prod.active}")

        prod.updated_by_user_id = user.id
        prod.updated_at = datetime.now(timezone.utc)

        log.info(f"UPDATE PRODUCT: Flushing changes")
        db.flush()
        log.info(f"UPDATE PRODUCT: Committing transaction")
        db.commit()
        log.info(f"UPDATE PRODUCT: Commit successful, refreshing")
        db.refresh(prod)
        log.info(f"UPDATE PRODUCT: SUCCESS - name={prod.name}, unit={prod.default_unit}")
        return prod
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        log.error(f"UPDATE PRODUCT: FAILED - {type(e).__name__}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error updating product: {str(e)}")

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

        # CRITICAL: Check if location_id column still exists and drop it if it does
        # This column conflicts with from_location_id/to_location_id and causes NOT NULL constraint violations
        try:
            from sqlalchemy import text, inspect
            inspector = inspect(db.connection().connection)
            cols = inspector.get_columns('bs_stock_movements', schema='bevigrow')
            col_names = {c['name'] for c in cols}

            if 'location_id' in col_names:
                log.warning("CRITICAL: Detected conflicting location_id column in bs_stock_movements table")
                log.warning("Attempting to drop location_id column to fix schema...")
                try:
                    db.connection().connection.execute(text("ALTER TABLE bevigrow.bs_stock_movements ALTER COLUMN location_id DROP NOT NULL"))
                    db.connection().connection.execute(text("ALTER TABLE bevigrow.bs_stock_movements DROP COLUMN location_id CASCADE"))
                    db.connection().connection.commit()
                    log.info("SUCCESS: Dropped conflicting location_id column")
                except Exception as e:
                    log.error(f"Failed to drop location_id column: {e}")
                    # Continue anyway - might have been dropped already
        except Exception as e:
            log.warning(f"Could not check for location_id column: {e}")
            # Continue - not critical if we can't verify

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
            from_inv.updated_by_user_id = user.id
            from_inv.updated_at = datetime.now(timezone.utc)
            log.info(f"CREATE STOCK MOVEMENT: Transfer from location {data.from_location_id}: {data.quantity} {data.unit}")

            to_inv.physical_stock += data.quantity
            to_inv.updated_by_user_id = user.id
            to_inv.updated_at = datetime.now(timezone.utc)
            log.info(f"CREATE STOCK MOVEMENT: Transfer to location {data.to_location_id}: {data.quantity} {data.unit}")

        elif data.to_location_id:
            # For simple stock additions, create or update inventory for the target location
            to_inv = db.scalar(select(Inventory).where(and_(Inventory.product_id == data.product_id, Inventory.location_id == data.to_location_id)).with_for_update())
            if not to_inv:
                log.info(f"CREATE STOCK MOVEMENT: Creating new inventory for product {data.product_id}, location {data.to_location_id}")
                to_inv = Inventory(product_id=data.product_id, location_id=data.to_location_id, physical_stock=0, reserved_stock=0, updated_by_user_id=user.id)
                db.add(to_inv)
                db.flush()
                to_inv = db.scalar(select(Inventory).where(and_(Inventory.product_id == data.product_id, Inventory.location_id == data.to_location_id)).with_for_update())

            old_stock = to_inv.physical_stock
            to_inv.physical_stock += data.quantity
            to_inv.updated_by_user_id = user.id
            to_inv.updated_at = datetime.now(timezone.utc)
            log.info(f"CREATE STOCK MOVEMENT: Updated inventory for product {data.product_id}, location {data.to_location_id}: {old_stock} → {to_inv.physical_stock} {data.unit}")

        movement = StockMovement(product_id=data.product_id, from_location_id=data.from_location_id, to_location_id=data.to_location_id, movement_type=StockMovementType(data.movement_type), quantity=data.quantity, unit=data.unit, reference_id=data.reference_id, notes=data.notes, created_by_user_id=user.id)
        db.add(movement)
        db.flush()
        log.info(f"CREATE STOCK MOVEMENT: Added stock movement record {movement.id}")
        db.commit()
        db.refresh(movement)
        db.refresh(to_inv) if data.to_location_id else None
        log.info(f"CREATE STOCK MOVEMENT: Success, created movement {movement.id}, inventory updated and committed")
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
    """Create customer purchase with UNIT-AWARE automatic inventory deduction.

    CRITICAL: This endpoint MUST subtract the purchased quantity from inventory.
    Uses row-level locking (SELECT FOR UPDATE) to prevent concurrent purchase race conditions.
    Validates sufficient stock CONSIDERING UNITS before creating purchase.
    All calculations use unit conversion to ensure accuracy.
    """
    from ..unit_converter import convert_to_base_unit, are_units_compatible
    log = logging.getLogger("bevigrow.bevi_stoq")

    try:
        log.info(f"CREATE PURCHASE: START - product_id={data.product_id}, qty={data.quantity}, unit={data.unit}")

        # Step 1: Get product to access base unit
        product = db.get(Product, data.product_id)
        if not product:
            log.error(f"CREATE PURCHASE: Product {data.product_id} not found")
            raise HTTPException(status_code=404, detail=f"Product {data.product_id} not found")

        log.info(f"CREATE PURCHASE: Found product - name={product.name}, base_unit={product.default_unit}")

        # Step 2: Validate quantity is positive
        if data.quantity <= 0:
            raise HTTPException(status_code=400, detail="Purchase quantity must be greater than 0")

        # Step 3: Validate units are compatible
        try:
            if not are_units_compatible(data.unit, product.default_unit):
                raise HTTPException(status_code=400, detail=f"Cannot purchase {data.unit} for product '{product.name}' which uses {product.default_unit}")
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"Invalid unit: {str(e)}")

        # Step 4: Convert purchase quantity to product's base unit
        try:
            purchase_qty_in_base_unit = convert_to_base_unit(data.quantity, data.unit, product.default_unit)
            log.info(f"CREATE PURCHASE: Converted {data.quantity} {data.unit} → {purchase_qty_in_base_unit} {product.default_unit}")
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"Unit conversion failed: {str(e)}")

        # Step 5: Check available stock with unit conversion
        inventories = db.scalars(select(Inventory).where(Inventory.product_id == data.product_id).with_for_update()).all()
        total_available = sum(inv.physical_stock - inv.reserved_stock for inv in inventories)
        log.info(f"CREATE PURCHASE: Total available stock = {total_available} {product.default_unit} across {len(inventories)} locations")

        if total_available < purchase_qty_in_base_unit:
            shortage = purchase_qty_in_base_unit - total_available
            log.error(f"CREATE PURCHASE: INSUFFICIENT STOCK - required={purchase_qty_in_base_unit}, available={total_available}, shortage={shortage}")
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient stock. Required: {purchase_qty_in_base_unit} {product.default_unit}, "
                       f"Available: {total_available} {product.default_unit}, Shortage: {shortage} {product.default_unit}"
            )

        # Step 6: Create purchase record (before deducting, so we have a reference for stock movements)
        purchase = CustomerPurchase(
            customer_name=data.customer_name, contact_id=data.contact_id, product_id=data.product_id,
            quantity=data.quantity, unit=data.unit,
            purchase_date=data.purchase_date, payment_status=PaymentStatus(data.payment_status),
            payment_method=data.payment_method, amount=data.amount, notes=data.notes,
            created_by_user_id=user.id
        )
        db.add(purchase)
        db.flush()
        log.info(f"CREATE PURCHASE: Created purchase record - id={purchase.id}")

        # Step 7: CRITICAL - Deduct from inventory across locations
        inventories_for_deduction = db.scalars(select(Inventory).where(Inventory.product_id == data.product_id).order_by(Inventory.location_id).with_for_update()).all()
        remaining_to_deduct = purchase_qty_in_base_unit
        total_deducted = 0
        deduction_count = 0

        log.info(f"CREATE PURCHASE: Starting deduction - need to deduct {purchase_qty_in_base_unit} {product.default_unit} from {len(inventories_for_deduction)} location(s)")

        for inv in inventories_for_deduction:
            if remaining_to_deduct <= 0.000001:  # Use epsilon for float comparison
                log.info(f"CREATE PURCHASE: Deduction complete - remaining={remaining_to_deduct}")
                break

            available = inv.physical_stock - inv.reserved_stock
            if available > 0.000001:
                deduct_qty = min(available, remaining_to_deduct)
                inv.physical_stock -= deduct_qty
                remaining_to_deduct -= deduct_qty
                total_deducted += deduct_qty
                deduction_count += 1

                log.info(f"CREATE PURCHASE: Deducted {deduct_qty} {product.default_unit} from location {inv.location_id} (available was {available}, now {inv.physical_stock})")

                # Create stock movement record
                movement = StockMovement(
                    product_id=data.product_id, from_location_id=inv.location_id,
                    movement_type=StockMovementType.stock_removed,
                    quantity=deduct_qty, unit=product.default_unit,
                    reference_id=purchase.id,
                    notes=f"Purchase: {data.quantity} {data.unit} to {data.customer_name}",
                    created_by_user_id=user.id
                )
                db.add(movement)

        log.info(f"CREATE PURCHASE: Deduction complete - total_deducted={total_deducted}, from {deduction_count} location(s)")

        if abs(total_deducted - purchase_qty_in_base_unit) > 0.000001:
            log.error(f"CREATE PURCHASE: CRITICAL - Deduction mismatch! Expected {purchase_qty_in_base_unit}, actually deducted {total_deducted}")
            db.rollback()
            raise HTTPException(status_code=500, detail="Purchase deduction failed - inventory mismatch")

        # Step 8: Commit transaction (THIS MUST HAPPEN FOR STOCK CHANGES TO PERSIST)
        log.info(f"CREATE PURCHASE: Flushing changes...")
        db.flush()
        log.info(f"CREATE PURCHASE: Committing transaction...")
        db.commit()
        log.info(f"CREATE PURCHASE: Commit successful")

        # Step 9: Refresh to get final state from database
        db.refresh(purchase)

        # Step 10: Verify deduction was persisted
        inventories_verify = db.scalars(select(Inventory).where(Inventory.product_id == data.product_id)).all()
        new_total = sum(inv.physical_stock - inv.reserved_stock for inv in inventories_verify)
        log.info(f"CREATE PURCHASE: Database verification - old_stock={total_available}, new_stock={new_total}, deducted={total_available - new_total}")

        if abs((total_available - new_total) - purchase_qty_in_base_unit) > 0.000001:
            log.error(f"CREATE PURCHASE: WARNING - Database deduction doesn't match! Expected reduction of {purchase_qty_in_base_unit}, got {total_available - new_total}")

        log.info(f"CREATE PURCHASE: SUCCESS - purchase {purchase.id} created and stock deducted")
        return purchase

    except HTTPException:
        log.error(f"CREATE PURCHASE: HTTPException raised")
        raise
    except Exception as e:
        log.error(f"CREATE PURCHASE: FAILED - {type(e).__name__}: {str(e)}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create purchase: {str(e)}")

@router.get("/customer-purchases", response_model=list[CustomerPurchaseOut])
def list_purchases(db: Session = Depends(get_db), _: User = Depends(get_current_user), payment_status: str | None = None, limit: int = Query(100, le=1000)):
    query = select(CustomerPurchase)
    if payment_status: query = query.where(CustomerPurchase.payment_status == payment_status)
    return db.scalars(query.order_by(CustomerPurchase.created_at.desc()).limit(limit)).all()

@router.put("/customer-purchases/{id}", response_model=CustomerPurchaseOut)
def update_purchase(id: int, data: CustomerPurchaseUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Update purchase with UNIT-AWARE inventory reversal and reapplication.

    CRITICAL: When quantity changes, reverse OLD effect first, then apply NEW effect.
    Example: 250g→500g: restore 0.25kg, then deduct 0.5kg (final: +0.25kg)
    """
    log = logging.getLogger("bevigrow.bevi_stoq")

    try:
        purchase = db.get(CustomerPurchase, id)
        if not purchase:
            raise HTTPException(status_code=404, detail="Purchase not found")

        old_quantity = purchase.quantity
        old_unit = purchase.unit
        old_product_id = purchase.product_id

        log.info(f"UPDATE PURCHASE: id={id}, old_qty={old_quantity} {old_unit}, old_product={old_product_id}")

        # Update simple fields
        if data.customer_name is not None: purchase.customer_name = data.customer_name
        if data.contact_id is not None: purchase.contact_id = data.contact_id
        if data.product_id is not None: purchase.product_id = data.product_id
        if data.quantity is not None: purchase.quantity = data.quantity
        if data.unit is not None: purchase.unit = data.unit
        if data.purchase_date is not None: purchase.purchase_date = data.purchase_date
        if data.payment_status is not None:
            try:
                purchase.payment_status = PaymentStatus(data.payment_status)
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid payment status: {data.payment_status}")
        if data.payment_method is not None: purchase.payment_method = data.payment_method
        if data.amount is not None: purchase.amount = data.amount
        if data.notes is not None: purchase.notes = data.notes

        # Handle inventory adjustment if quantity OR unit changed
        quantity_changed = data.quantity is not None and data.quantity != old_quantity
        unit_changed = data.unit is not None and data.unit != old_unit

        if quantity_changed or unit_changed:
            product = db.get(Product, purchase.product_id)
            if not product:
                raise HTTPException(status_code=404, detail=f"Product {purchase.product_id} not found")

            if not are_units_compatible(old_unit, product.default_unit):
                raise HTTPException(status_code=400, detail=f"Old unit {old_unit} incompatible with product base unit {product.default_unit}")
            if not are_units_compatible(purchase.unit, product.default_unit):
                raise HTTPException(status_code=400, detail=f"New unit {purchase.unit} incompatible with product base unit {product.default_unit}")

            # Convert quantities to base unit
            old_qty_base = convert_to_base_unit(old_quantity, old_unit, product.default_unit)
            new_qty_base = convert_to_base_unit(purchase.quantity, purchase.unit, product.default_unit)

            log.info(f"UPDATE PURCHASE: old={old_quantity} {old_unit}→{old_qty_base} {product.default_unit}, new={purchase.quantity} {purchase.unit}→{new_qty_base} {product.default_unit}")

            # STEP 1: Reverse old purchase (restore old quantity)
            inventories = db.scalars(select(Inventory).where(Inventory.product_id == old_product_id).order_by(Inventory.location_id).with_for_update()).all()
            remaining_restore = old_qty_base
            for inv in inventories:
                if remaining_restore <= 0: break
                restore_qty = min(remaining_restore, old_qty_base)
                inv.physical_stock += restore_qty
                remaining_restore -= restore_qty
                movement = StockMovement(
                    product_id=old_product_id, from_location_id=inv.location_id,
                    movement_type=StockMovementType.stock_added,
                    quantity=restore_qty, unit=product.default_unit,
                    reference_id=purchase.id,
                    notes=f"Purchase update: reverse {old_quantity} {old_unit}",
                    created_by_user_id=user.id
                )
                db.add(movement)
            log.info(f"UPDATE PURCHASE: reversed {old_qty_base} {product.default_unit}")

            # STEP 2: Apply new purchase (deduct new quantity)
            inventories = db.scalars(select(Inventory).where(Inventory.product_id == purchase.product_id).with_for_update()).all()
            total_available = sum(inv.physical_stock - inv.reserved_stock for inv in inventories)
            if total_available < new_qty_base:
                shortage = new_qty_base - total_available
                raise HTTPException(status_code=400, detail=f"Insufficient stock for new purchase. Required: {new_qty_base} {product.default_unit}, Available: {total_available} {product.default_unit}, Shortage: {shortage} {product.default_unit}")

            inventories = db.scalars(select(Inventory).where(Inventory.product_id == purchase.product_id).order_by(Inventory.location_id).with_for_update()).all()
            remaining_deduct = new_qty_base
            for inv in inventories:
                if remaining_deduct <= 0: break
                available = inv.physical_stock - inv.reserved_stock
                if available > 0:
                    deduct_qty = min(available, remaining_deduct)
                    inv.physical_stock -= deduct_qty
                    remaining_deduct -= deduct_qty
                    movement = StockMovement(
                        product_id=purchase.product_id, from_location_id=inv.location_id,
                        movement_type=StockMovementType.stock_removed,
                        quantity=deduct_qty, unit=product.default_unit,
                        reference_id=purchase.id,
                        notes=f"Purchase update: {purchase.quantity} {purchase.unit}",
                        created_by_user_id=user.id
                    )
                    db.add(movement)
            log.info(f"UPDATE PURCHASE: applied {new_qty_base} {product.default_unit}")

        purchase.updated_by_user_id = user.id
        db.commit()
        db.refresh(purchase)
        log.info(f"UPDATE PURCHASE: purchase {id} updated successfully")
        return purchase

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        log.error(f"UPDATE PURCHASE: FAILED - {type(e).__name__}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to update purchase: {str(e)}")

@router.delete("/customer-purchases/{id}", status_code=204)
def delete_purchase(id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Delete a customer purchase and restore inventory with unit-aware calculation.

    CRITICAL: Must reverse the original deduction (add back the stock).
    """
    from ..unit_converter import convert_to_base_unit
    log = logging.getLogger("bevigrow.bevi_stoq")
    try:
        log.info(f"DELETE PURCHASE: START - id={id}")

        # Get the purchase with row-level locking
        purchase = db.scalars(select(CustomerPurchase).where(CustomerPurchase.id == id).with_for_update()).first()
        if not purchase:
            log.error(f"DELETE PURCHASE: Purchase {id} not found")
            raise HTTPException(status_code=404, detail="Purchase not found")

        log.info(f"DELETE PURCHASE: Found purchase - product_id={purchase.product_id}, qty={purchase.quantity}, unit={purchase.unit}")

        # Get product to verify and get base unit
        product = db.get(Product, purchase.product_id)
        if not product:
            log.error(f"DELETE PURCHASE: Product {purchase.product_id} not found")
            raise HTTPException(status_code=404, detail=f"Product {purchase.product_id} not found")

        # Convert purchase quantity to base unit
        try:
            purchase_qty_in_base = convert_to_base_unit(purchase.quantity, purchase.unit, product.default_unit)
            log.info(f"DELETE PURCHASE: Converted {purchase.quantity} {purchase.unit} → {purchase_qty_in_base} {product.default_unit}")
        except ValueError as e:
            log.error(f"DELETE PURCHASE: Unit conversion failed - {str(e)}")
            raise HTTPException(status_code=400, detail=f"Unit conversion failed: {str(e)}")

        # Restore inventory (reverse the deduction that happened when purchase was created)
        if purchase_qty_in_base > 0:
            inventories = db.scalars(select(Inventory).where(Inventory.product_id == purchase.product_id).order_by(Inventory.location_id).with_for_update()).all()
            remaining_to_restore = purchase_qty_in_base
            total_restored = 0

            log.info(f"DELETE PURCHASE: Restoring {purchase_qty_in_base} {product.default_unit} across {len(inventories)} locations")

            for inv in inventories:
                if remaining_to_restore <= 0.000001:
                    log.info(f"DELETE PURCHASE: Restoration complete")
                    break

                # Restore proportionally to where it was deducted (but we don't track that, so just restore from first location with capacity)
                restore_qty = min(remaining_to_restore, remaining_to_restore)  # Restore as much as remaining
                inv.physical_stock += restore_qty
                remaining_to_restore -= restore_qty
                total_restored += restore_qty

                log.info(f"DELETE PURCHASE: Restored {restore_qty} {product.default_unit} to location {inv.location_id} (new stock: {inv.physical_stock})")

                # Create stock movement record (to_location because adding stock)
                movement = StockMovement(
                    product_id=purchase.product_id,
                    to_location_id=inv.location_id,
                    movement_type=StockMovementType.stock_added,
                    quantity=restore_qty,
                    unit=product.default_unit,
                    reference_id=purchase.id,
                    notes=f"Purchase deleted: {purchase.customer_name}",
                    created_by_user_id=user.id
                )
                db.add(movement)
                break  # Restore all to first location (since we don't track which location it was deducted from)

        # Delete the purchase record
        log.info(f"DELETE PURCHASE: Deleting purchase record {id}")
        db.delete(purchase)
        log.info(f"DELETE PURCHASE: Committing transaction")
        db.commit()
        log.info(f"DELETE PURCHASE: SUCCESS - purchase {id} deleted and inventory restored")

    except HTTPException:
        raise
    except Exception as e:
        log.error(f"DELETE PURCHASE: FAILED - {type(e).__name__}: {str(e)}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete purchase: {str(e)}")

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
