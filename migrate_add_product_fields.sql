-- Migration: Add packaging_status and low_stock_threshold columns to bs_products
-- This fixes the "UndefinedColumn" error when the backend tries to query these fields

-- Connect to: your Neon PostgreSQL database
-- Schema: bevigrow
-- Table: bs_products

ALTER TABLE bevigrow.bs_products
ADD COLUMN IF NOT EXISTS packaging_status VARCHAR(50) DEFAULT 'unpacked' NOT NULL;

ALTER TABLE bevigrow.bs_products
ADD COLUMN IF NOT EXISTS low_stock_threshold FLOAT NULL;

-- Verify the columns were created
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_schema = 'bevigrow'
  AND table_name = 'bs_products'
  AND column_name IN ('packaging_status', 'low_stock_threshold')
ORDER BY column_name;
