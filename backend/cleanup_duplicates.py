#!/usr/bin/env python3
"""Clean up duplicate products in Bevi Stoq - INACTIVE duplicates only."""

import os
import sys
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import Session

sys.path.insert(0, os.path.dirname(__file__))
from app.models import Category, Product

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://neondb_owner:npg_0RNHfZawD8br@ep-odd-scene-azpcdsof-pooler.c-3.ap-southeast-1.aws.neon.tech/neondb?sslmode=require"
)

engine = create_engine(DATABASE_URL)

def main():
    with Session(engine) as db:
        print("=" * 80)
        print("BEVI STOQ DUPLICATE CLEANUP (Inactive only)")
        print("=" * 80)

        deleted_count = 0
        categories = db.scalars(select(Category)).all()

        for cat in categories:
            all_products = db.scalars(
                select(Product).where(Product.category_id == cat.id)
            ).all()

            # Group by normalized name
            groups = {}
            for prod in all_products:
                normalized = prod.name.lower().strip()
                if normalized not in groups:
                    groups[normalized] = []
                groups[normalized].append(prod)

            # For each group with multiple products
            for normalized, prods in groups.items():
                if len(prods) > 1:
                    # Keep the active one (if exists), delete all others
                    active_prods = [p for p in prods if p.active]
                    if active_prods:
                        to_delete = [p for p in prods if not p.active]
                    else:
                        # All inactive - keep the most recent, delete others
                        sorted_prods = sorted(prods, key=lambda p: p.created_at or '', reverse=True)
                        to_delete = sorted_prods[1:]

                    for prod in to_delete:
                        print(f"Deleting: {prod.name} (ID: {prod.id}, status: {'ACTIVE' if prod.active else 'INACTIVE'})")
                        db.delete(prod)
                        deleted_count += 1

        db.commit()
        print(f"\nDeleted: {deleted_count} duplicate product(s)")
        print("=" * 80)

if __name__ == "__main__":
    main()
