"""Bevi Stoq inventory management API routes."""
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

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
    return db.scalars(select(Product).where(Product.active == True)).all()

@router.post("/products", response_model=ProductOut, status_code=201)
def create_product(data: ProductCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    prod = Product(name=data.name, category_id=data.category_id, default_unit=data.default_unit, low_stock_threshold=data.low_stock_threshold, created_by_user_id=user.id)
    db.add(prod)
    db.commit()
    db.refresh(prod)
    return prod

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
    if data.low_stock_threshold is not None: prod.low_stock_threshold = data.low_stock_threshold
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
    items = db.scalars(select(Inventory)).all()
    for item in items:
        item.available_stock = item.physical_stock - item.reserved_stock
    return items

@router.get("/inventory/{product_id}/{location_id}", response_model=InventoryOut)
def get_inventory(product_id: int, location_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    inv = db.scalar(select(Inventory).where(and_(Inventory.product_id == product_id, Inventory.location_id == location_id)))
    if not inv: raise HTTPException(status_code=404, detail="Inventory not found")
    inv.available_stock = inv.physical_stock - inv.reserved_stock
    return inv

# ================================================================ STOCK MOVEMENTS
@router.post("/stock-movements", response_model=StockMovementOut, status_code=201)
def create_stock_movement(data: StockMovementCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    movement = StockMovement(product_id=data.product_id, from_location_id=data.from_location_id, to_location_id=data.to_location_id, movement_type=StockMovementType(data.movement_type), quantity=data.quantity, unit=data.unit, reference_id=data.reference_id, notes=data.notes, created_by_user_id=user.id)
    db.add(movement)
    db.commit()
    db.refresh(movement)
    return movement

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

    movement = StockMovement(product_id=restock.product_id, to_location_id=restock.location_id, movement_type=StockMovementType.receipt, quantity=restock.quantity, unit=restock.unit, reference_id=restock.id, notes=f"Restock from {restock.supplier_name}", created_by_user_id=user.id)
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

# ================================================================ CUSTOMER PURCHASES
@router.post("/customer-purchases", response_model=CustomerPurchaseOut, status_code=201)
def create_purchase(data: CustomerPurchaseCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    purchase = CustomerPurchase(customer_name=data.customer_name, contact_id=data.contact_id, product_id=data.product_id, quantity=data.quantity, unit=data.unit, purchase_date=data.purchase_date, payment_status=PaymentStatus(data.payment_status), payment_method=data.payment_method, amount=data.amount, notes=data.notes, created_by_user_id=user.id)
    db.add(purchase)
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
    total_products = db.scalar(select(func.count(Product.id)).where(Product.active == True)) or 0
    total_locations = db.scalar(select(func.count(Location.id)).where(Location.active == True)) or 0
    total_categories = db.scalar(select(func.count(Category.id)).where(Category.active == True)) or 0

    low_stock_list = []
    out_of_stock_list = []

    products = db.scalars(select(Product).where(Product.active == True)).all()
    for prod in products:
        stmt = select(func.coalesce(func.sum(Inventory.physical_stock - Inventory.reserved_stock), 0)).where(Inventory.product_id == prod.id)
        available = db.scalar(stmt) or 0

        if available <= 0:
            out_of_stock_list.append(ProductStatus(product_id=prod.id, product_name=prod.name, status="OUT_OF_STOCK", current_stock=available, threshold=prod.low_stock_threshold))
        elif available <= prod.low_stock_threshold:
            low_stock_list.append(ProductStatus(product_id=prod.id, product_name=prod.name, status="LOW_STOCK", current_stock=available, threshold=prod.low_stock_threshold))

    recent = db.scalars(select(StockMovement).order_by(StockMovement.created_at.desc()).limit(10)).all()

    return DashboardOut(
        summary=DashboardSummary(total_products=total_products, low_stock_count=len(low_stock_list), out_of_stock_count=len(out_of_stock_list), total_locations=total_locations, total_categories=total_categories),
        low_stock_products=low_stock_list,
        out_of_stock_products=out_of_stock_list,
        recent_movements=[StockMovementOut.model_validate(m) for m in recent]
    )
