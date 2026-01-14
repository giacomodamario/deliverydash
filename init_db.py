#!/usr/bin/env python3
"""Initialize the SQLite database with schema."""

import sqlite3

from config import settings

SCHEMA = """
-- Brands (restaurant groups/companies)
CREATE TABLE IF NOT EXISTS brands (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    slug TEXT NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Locations (individual restaurant locations)
CREATE TABLE IF NOT EXISTS locations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    brand_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    platform TEXT NOT NULL,  -- 'deliveroo', 'glovo', 'justeat'
    platform_id TEXT,        -- ID on the platform
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (brand_id) REFERENCES brands(id),
    UNIQUE(brand_id, platform, platform_id)
);

-- Orders (individual order transactions)
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    location_id INTEGER NOT NULL,
    platform TEXT NOT NULL,
    order_id TEXT NOT NULL,
    order_date DATE NOT NULL,
    gross_value REAL DEFAULT 0,
    commission REAL DEFAULT 0,
    commission_rate REAL DEFAULT 0,
    vat REAL DEFAULT 0,
    net_payout REAL DEFAULT 0,
    refund REAL DEFAULT 0,
    refund_reason TEXT,
    refund_fault TEXT,
    promo_restaurant REAL DEFAULT 0,
    promo_platform REAL DEFAULT 0,
    tips REAL DEFAULT 0,
    adjustments REAL DEFAULT 0,
    ad_fee REAL DEFAULT 0,
    discount_commission REAL DEFAULT 0,
    is_cash INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (location_id) REFERENCES locations(id),
    UNIQUE(platform, order_id)
);

-- Users (dashboard users)
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT DEFAULT 'viewer',  -- 'admin', 'manager', 'viewer'
    brand_id INTEGER,            -- NULL for admin (sees all)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (brand_id) REFERENCES brands(id)
);

-- Import log (track which files have been imported)
CREATE TABLE IF NOT EXISTS imports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename TEXT NOT NULL UNIQUE,
    platform TEXT NOT NULL,
    rows_imported INTEGER DEFAULT 0,
    imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Sync runs (track automated sync executions)
CREATE TABLE IF NOT EXISTS sync_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    platform TEXT NOT NULL,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    status TEXT NOT NULL,  -- 'success', 'failed'
    files_downloaded INTEGER DEFAULT 0,
    orders_imported INTEGER DEFAULT 0,
    duration_seconds REAL DEFAULT 0,
    error_message TEXT,
    error_stage TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_orders_location ON orders(location_id);
CREATE INDEX IF NOT EXISTS idx_orders_date ON orders(order_date);
CREATE INDEX IF NOT EXISTS idx_orders_platform ON orders(platform);
CREATE INDEX IF NOT EXISTS idx_locations_brand ON locations(brand_id);
CREATE INDEX IF NOT EXISTS idx_locations_platform ON locations(platform);
CREATE INDEX IF NOT EXISTS idx_sync_runs_platform ON sync_runs(platform);
CREATE INDEX IF NOT EXISTS idx_sync_runs_created ON sync_runs(created_at);
"""


def init_db():
    """Create database and tables."""
    db_path = settings.db_path
    db_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"Initializing database at {db_path}")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Execute schema
    cursor.executescript(SCHEMA)

    conn.commit()

    # Show tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = cursor.fetchall()

    print(f"Created {len(tables)} tables:")
    for table in tables:
        cursor.execute(f"SELECT COUNT(*) FROM {table[0]}")
        count = cursor.fetchone()[0]
        print(f"  - {table[0]} ({count} rows)")

    conn.close()
    print("\nDatabase initialized successfully!")


if __name__ == "__main__":
    init_db()
