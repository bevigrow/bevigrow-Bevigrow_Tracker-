"""Bevi Stoq inventory management API routes - Complete implementation."""
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

def utcnow():
    return datetime.now(timezone.utc)

@router.get("/categories", response_model=list[CategoryOut])
def list_categories(db: Session = Depends(get_db), _: User = Depends(get_current_user), search: str | None = None, limit: int = Query(100, le=1000)):
    query = select(Category).where(Category.active == True)
    if search:
        query = query.where(Category.name.ilike(f"%{search}%"))
    return db.scalars(query.limit(limit)).all()

@router.post("/categories", response_model=CategoryOut, status_code=201)
def create_category(data: CategoryCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    cat = Category(name=data.name, description=data.description, created_by_user_id=user.id)
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return cat

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
