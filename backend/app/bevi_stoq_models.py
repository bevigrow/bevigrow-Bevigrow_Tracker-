"""Bevi Stoq inventory management models."""
from __future__ import annotations

import enum
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class StockMovementType(str, enum.Enum):
    """Types of stock movements in the inventory."""
    receipt = "receipt"
    transfer = "transfer"
    adjustment = "adjustment"
    fulfillment = "fulfillment"
    return_ = "return"


class RequirementStatus(str, enum.Enum):
    """Status of customer requirements."""
    pending = "pending"
    reserved = "reserved"
    fulfilled = "fulfilled"
    completed = "completed"
    cancelled = "cancelled"


class PaymentStatus(str, enum.Enum):
    """Payment status for customer purchases."""
    paid = "paid"
    pending = "pending"
    overdue = "overdue"


class RestockStatus(str, enum.Enum):
    """Status of restock orders."""
    pending = "pending"
    received = "received"
    cancelled = "cancelled"


# ================================================================ BEVI STOQ MODELS

class Category(Base):
    """Product category for inventory organization."""
    __tablename__ = "bs_categories"
    __table_args__ = {"schema": "bevigrow"}

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False, unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    updated_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))

    products: Mapped[list["Product"]] = relationship(back_populates="category", cascade="all, delete-orphan")


class Product(Base):
    """Inventory product with category and unit configuration."""
    __tablename__ = "bs_products"
    __table_args__ = {"schema": "bevigrow"}

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("bevigrow.bs_categories.id"), index=True)
    category: Mapped["Category"] = relationship(back_populates="products")

    default_unit: Mapped[str] = mapped_column(String(50), nullable=False)
    low_stock_threshold: Mapped[float] = mapped_column(Float, default=0)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    updated_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))

    inventory_items: Mapped[list["Inventory"]] = relationship(back_populates="product", cascade="all, delete-orphan")
    stock_movements: Mapped[list["StockMovement"]] = relationship(back_populates="product", cascade="all, delete-orphan")
    requirement_items: Mapped[list["RequirementItem"]] = relationship(back_populates="product")
    combo_items: Mapped[list["ComboItem"]] = relationship(back_populates="product")
    customer_purchases: Mapped[list["CustomerPurchase"]] = relationship(back_populates="product")
    restocks: Mapped[list["Restock"]] = relationship(back_populates="product", cascade="all, delete-orphan")


class Location(Base):
    """Storage location/warehouse for inventory."""
    __tablename__ = "bs_locations"
    __table_args__ = {"schema": "bevigrow"}

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False, unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    updated_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))

    inventory_items: Mapped[list["Inventory"]] = relationship(back_populates="location", cascade="all, delete-orphan")
    stock_movements_from: Mapped[list["StockMovement"]] = relationship(
        back_populates="from_location", foreign_keys="StockMovement.from_location_id"
    )
    stock_movements_to: Mapped[list["StockMovement"]] = relationship(
        back_populates="to_location", foreign_keys="StockMovement.to_location_id"
    )
    restocks: Mapped[list["Restock"]] = relationship(back_populates="location", cascade="all, delete-orphan")


class Inventory(Base):
    """Stock levels per product per location."""
    __tablename__ = "bs_inventory"
    __table_args__ = {"schema": "bevigrow"}

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("bevigrow.bs_products.id"), index=True)
    product: Mapped["Product"] = relationship(back_populates="inventory_items")

    location_id: Mapped[int] = mapped_column(ForeignKey("bevigrow.bs_locations.id"), index=True)
    location: Mapped["Location"] = relationship(back_populates="inventory_items")

    physical_stock: Mapped[float] = mapped_column(Float, default=0)
    reserved_stock: Mapped[float] = mapped_column(Float, default=0)

    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    updated_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))


class StockMovement(Base):
    """Immutable audit trail of all stock changes."""
    __tablename__ = "bs_stock_movements"
    __table_args__ = {"schema": "bevigrow"}

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("bevigrow.bs_products.id"), index=True)
    product: Mapped["Product"] = relationship(back_populates="stock_movements")

    from_location_id: Mapped[int | None] = mapped_column(ForeignKey("bevigrow.bs_locations.id"))
    from_location: Mapped["Location | None"] = relationship(
        back_populates="stock_movements_from", foreign_keys=[from_location_id]
    )

    to_location_id: Mapped[int | None] = mapped_column(ForeignKey("bevigrow.bs_locations.id"))
    to_location: Mapped["Location | None"] = relationship(
        back_populates="stock_movements_to", foreign_keys=[to_location_id]
    )

    movement_type: Mapped[StockMovementType] = mapped_column(
        Enum(StockMovementType, native_enum=False), index=True
    )
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str | None] = mapped_column(String(50))

    reference_id: Mapped[int | None] = mapped_column(Integer)
    notes: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))


class Restock(Base):
    """Restock orders with supplier info and dates."""
    __tablename__ = "bs_restocks"
    __table_args__ = {"schema": "bevigrow"}

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("bevigrow.bs_products.id"), index=True)
    product: Mapped["Product"] = relationship(back_populates="restocks")

    location_id: Mapped[int] = mapped_column(ForeignKey("bevigrow.bs_locations.id"))
    location: Mapped["Location"] = relationship(back_populates="restocks")

    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str | None] = mapped_column(String(50))

    restock_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    supplier_name: Mapped[str | None] = mapped_column(String(200))
    cost_per_unit: Mapped[float | None] = mapped_column(Float)
    total_cost: Mapped[float | None] = mapped_column(Float)
    reference_id: Mapped[str | None] = mapped_column(String(100))
    notes: Mapped[str | None] = mapped_column(Text)

    status: Mapped[RestockStatus] = mapped_column(Enum(RestockStatus, native_enum=False), default=RestockStatus.pending)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    updated_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))


class CustomerRequirement(Base):
    """Customer's product requirement/order."""
    __tablename__ = "bs_customer_requirements"
    __table_args__ = {"schema": "bevigrow"}

    id: Mapped[int] = mapped_column(primary_key=True)
    contact_id: Mapped[int | None] = mapped_column(ForeignKey("bevigrow.contacts.id"))
    customer_name: Mapped[str] = mapped_column(String(200))

    status: Mapped[RequirementStatus] = mapped_column(
        Enum(RequirementStatus, native_enum=False), default=RequirementStatus.pending, index=True
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    updated_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))

    items: Mapped[list["RequirementItem"]] = relationship(back_populates="requirement", cascade="all, delete-orphan")


class RequirementItem(Base):
    """Individual product in a customer requirement."""
    __tablename__ = "bs_requirement_items"
    __table_args__ = {"schema": "bevigrow"}

    id: Mapped[int] = mapped_column(primary_key=True)
    requirement_id: Mapped[int] = mapped_column(ForeignKey("bevigrow.bs_customer_requirements.id"), index=True)
    requirement: Mapped["CustomerRequirement"] = relationship(back_populates="items")

    product_id: Mapped[int] = mapped_column(ForeignKey("bevigrow.bs_products.id"))
    product: Mapped["Product"] = relationship(back_populates="requirement_items")

    quantity_required: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str | None] = mapped_column(String(50))

    quantity_reserved: Mapped[float] = mapped_column(Float, default=0)
    quantity_fulfilled: Mapped[float] = mapped_column(Float, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class CustomerPurchase(Base):
    """Record of customer purchase transactions."""
    __tablename__ = "bs_customer_purchases"
    __table_args__ = {"schema": "bevigrow"}

    id: Mapped[int] = mapped_column(primary_key=True)
    contact_id: Mapped[int | None] = mapped_column(ForeignKey("bevigrow.contacts.id"))
    customer_name: Mapped[str] = mapped_column(String(200), nullable=False)

    product_id: Mapped[int] = mapped_column(ForeignKey("bevigrow.bs_products.id"), index=True)
    product: Mapped["Product"] = relationship(back_populates="customer_purchases")

    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str | None] = mapped_column(String(50))

    purchase_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    payment_status: Mapped[PaymentStatus] = mapped_column(
        Enum(PaymentStatus, native_enum=False), default=PaymentStatus.pending, index=True
    )
    payment_method: Mapped[str | None] = mapped_column(String(100))
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    updated_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))


class Combo(Base):
    """Bundled product set for quick ordering."""
    __tablename__ = "bs_combos"
    __table_args__ = {"schema": "bevigrow"}

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    updated_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))

    items: Mapped[list["ComboItem"]] = relationship(back_populates="combo", cascade="all, delete-orphan")


class ComboItem(Base):
    """Product in a combo bundle."""
    __tablename__ = "bs_combo_items"
    __table_args__ = {"schema": "bevigrow"}

    id: Mapped[int] = mapped_column(primary_key=True)
    combo_id: Mapped[int] = mapped_column(ForeignKey("bevigrow.bs_combos.id"), index=True)
    combo: Mapped["Combo"] = relationship(back_populates="items")

    product_id: Mapped[int] = mapped_column(ForeignKey("bevigrow.bs_products.id"))
    product: Mapped["Product"] = relationship(back_populates="combo_items")

    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str | None] = mapped_column(String(50))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
