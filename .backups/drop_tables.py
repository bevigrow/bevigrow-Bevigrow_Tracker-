#!/usr/bin/env python3
"""Drop all Bevi Stoq tables from Neon PostgreSQL."""

import os
from sqlalchemy import create_engine, text

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://neondb_owner:npg_0RNHfZawD8br@ep-odd-scene-azpcdsof-pooler.c-3.ap-southeast-1.aws.neon.tech/neondb?sslmode=require"
)

engine = create_engine(DATABASE_URL)

TABLES_TO_DROP = [
    "bs_combo_items",
    "bs_combos",
    "bs_requirement_items",
    "bs_customer_requirements",
    "bs_stock_movements",
    "bs_inventory",
    "bs_locations",
    "bs_products",
    "bs_categories",
]

with engine.connect() as conn:
    for table in TABLES_TO_DROP:
        try:
            conn.execute(text(f"DROP TABLE IF EXISTS {table} CASCADE;"))
            print(f"[OK] Dropped {table}")
        except Exception as e:
            print(f"[ERROR] Error dropping {table}: {e}")

    conn.commit()
    print("\n[SUCCESS] All Bevi Stoq tables dropped successfully")
