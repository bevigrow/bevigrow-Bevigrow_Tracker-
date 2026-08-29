#!/usr/bin/env python3
"""Audit Bevi Stoq database state - diagnose duplicate products."""

import os
import sys
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import Session

# Import models
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
        print("BEVI STOQ DATABASE AUDIT")
        print("=" * 80)

        # Count records
        product_count = db.scalar(select(func.count(Product.id)))
        category_count = db.scalar(select(func.count(Category.id)))

        print(f"\nTotal Products: {product_count}")
        print(f"Total Categories: {category_count}\n")

        # List all products
        print("-" * 80)
        print("ALL PRODUCTS (Active and Inactive)")
        print("-" * 80)

        products = db.scalars(select(Product)).all()
        for p in products:
            status = "✓ ACTIVE" if p.active else "✗ INACTIVE"
            print(f"[{p.id:3d}] {p.name:30s} | Category: {p.category_id:3d} | {status} | Unit: {p.default_unit}")

        # Check for duplicates (case-insensitive, same category, active)
        print("\n" + "-" * 80)
        print("DUPLICATE CHECK (Case-insensitive, same category, active only)")
        print("-" * 80)

        # Group by category and normalized name
        duplicates_found = False
        categories = db.scalars(select(Category)).all()

        for cat in categories:
            cat_products = db.scalars(
                select(Product).where(
                    Product.category_id == cat.id,
                    Product.active == True
                )
            ).all()

            # Check for duplicates within this category
            seen = {}
            for prod in cat_products:
                normalized = prod.name.lower().strip()
                if normalized in seen:
                    if not duplicates_found:
                        duplicates_found = True
                    print(f"❌ DUPLICATE in '{cat.name}':")
                    print(f"   - {seen[normalized].name} (ID: {seen[normalized].id})")
                    print(f"   - {prod.name} (ID: {prod.id})")
                else:
                    seen[normalized] = prod

        if not duplicates_found:
            print("✓ No duplicates found")

        # Check specific products
        print("\n" + "-" * 80)
        print("SPECIFIC PRODUCT SEARCHES")
        print("-" * 80)

        search_terms = ["Black Pepper", "Star Anise", "black pepper", "star anise"]
        for term in search_terms:
            results = db.scalars(
                select(Product).where(
                    func.lower(func.trim(Product.name)) == term.lower()
                )
            ).all()
            if results:
                print(f"✓ Found '{term}': {len(results)} record(s)")
                for p in results:
                    status = "ACTIVE" if p.active else "INACTIVE"
                    print(f"    - {p.name} (ID: {p.id}, {status})")
            else:
                print(f"✗ Not found: '{term}'")

        print("\n" + "=" * 80)
        print("END AUDIT")
        print("=" * 80)

if __name__ == "__main__":
    main()
