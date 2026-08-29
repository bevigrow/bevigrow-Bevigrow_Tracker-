#!/usr/bin/env python3
"""Comprehensive cleanup of Bevi Stoq test data."""
import os
from sqlalchemy import select, text
from backend.app.database import SessionLocal, engine
from backend.app.models import (
    Product, Inventory, StockMovement,
    CustomerRequirement, RequirementItem
)

def cleanup_by_product_name(product_name: str):
    """Delete all data related to a product by name."""
    db = SessionLocal()
    try:
        print(f"\n🔍 Searching for '{product_name}'...")

        # Find product
        product = db.scalar(
            select(Product).where(Product.name == product_name)
        )

        if not product:
            print(f"ℹ️  No product '{product_name}' found")
            return True

        product_id = product.id
        print(f"✅ Found: {product_name} (ID: {product_id})")

        # Delete requirement items referencing this product
        req_items = db.query(RequirementItem).filter(
            RequirementItem.product_id == product_id
        ).all()
        for item in req_items:
            db.delete(item)
        if req_items:
            print(f"🗑️  Deleted {len(req_items)} requirement items")

        # Delete inventory
        invs = db.query(Inventory).filter(
            Inventory.product_id == product_id
        ).all()
        for inv in invs:
            db.delete(inv)
        if invs:
            print(f"🗑️  Deleted {len(invs)} inventory records")

        # Delete stock movements
        moves = db.query(StockMovement).filter(
            StockMovement.product_id == product_id
        ).all()
        for move in moves:
            db.delete(move)
        if moves:
            print(f"🗑️  Deleted {len(moves)} stock movements")

        # Delete product
        db.delete(product)
        print(f"🗑️  Deleted product '{product_name}'")

        db.commit()
        print(f"✅ Cleanup complete for '{product_name}'!")
        return True

    except Exception as e:
        db.rollback()
        print(f"❌ Error: {e}")
        return False
    finally:
        db.close()

def cleanup_all_test_data():
    """Delete all Bevi Stoq test products."""
    db = SessionLocal()
    try:
        print("\n🔥 Nuclear cleanup: Deleting ALL Bevi Stoq test data...")

        # Get all requirement items
        req_items = db.query(RequirementItem).all()
        for item in req_items:
            db.delete(item)
        if req_items:
            print(f"🗑️  Deleted {len(req_items)} requirement items")

        # Get all inventory
        invs = db.query(Inventory).all()
        for inv in invs:
            db.delete(inv)
        if invs:
            print(f"🗑️  Deleted {len(invs)} inventory records")

        # Get all stock movements
        moves = db.query(StockMovement).all()
        for move in moves:
            db.delete(move)
        if moves:
            print(f"🗑️  Deleted {len(moves)} stock movements")

        # Get all requirements
        reqs = db.query(CustomerRequirement).all()
        for req in reqs:
            db.delete(req)
        if reqs:
            print(f"🗑️  Deleted {len(reqs)} requirements")

        # Get all products
        prods = db.query(Product).all()
        for prod in prods:
            db.delete(prod)
        if prods:
            print(f"🗑️  Deleted {len(prods)} products")

        db.commit()
        print("✅ All test data deleted! Fresh start ready.")
        return True

    except Exception as e:
        db.rollback()
        print(f"❌ Error: {e}")
        return False
    finally:
        db.close()

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "all":
        cleanup_all_test_data()
    elif len(sys.argv) > 1:
        cleanup_by_product_name(sys.argv[1])
    else:
        # Default: cleanup Star Anise
        cleanup_by_product_name("Star Anise")
        cleanup_by_product_name("Organic Star Anise")
        cleanup_by_product_name("Star Anise Premium")
