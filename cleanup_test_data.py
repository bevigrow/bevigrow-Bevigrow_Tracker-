#!/usr/bin/env python3
"""Clean up test data from Bevi Stoq database."""
import sys
from sqlalchemy import select, delete
from backend.app.database import SessionLocal
from backend.app.models import Product, Inventory, StockMovement, Category

def cleanup():
    """Delete old test data."""
    db = SessionLocal()
    try:
        # Find Star Anise product
        star_anise = db.scalar(
            select(Product).where(Product.name == "Star Anise")
        )

        if not star_anise:
            print("✅ No 'Star Anise' product found - already clean!")
            return

        print(f"🗑️  Found Star Anise (ID: {star_anise.id})")

        # Delete related inventory
        inv_count = db.query(Inventory).filter(
            Inventory.product_id == star_anise.id
        ).delete()
        print(f"🗑️  Deleted {inv_count} inventory records")

        # Delete related stock movements
        mov_count = db.query(StockMovement).filter(
            StockMovement.product_id == star_anise.id
        ).delete()
        print(f"🗑️  Deleted {mov_count} stock movements")

        # Delete the product
        db.delete(star_anise)
        print(f"🗑️  Deleted Star Anise product")

        db.commit()
        print("✅ Cleanup complete! Start fresh now.")

    except Exception as e:
        db.rollback()
        print(f"❌ Error: {e}")
        sys.exit(1)
    finally:
        db.close()

if __name__ == "__main__":
    cleanup()
