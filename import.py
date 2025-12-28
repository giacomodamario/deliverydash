#!/usr/bin/env python3
"""Import downloaded CSVs into SQLite database."""

import sqlite3
import re
from pathlib import Path
from datetime import datetime

from parsers.deliveroo import parse_deliveroo_invoice

DB_PATH = Path(__file__).parent / "data" / "dash.db"
DOWNLOADS_DIR = Path(__file__).parent / "data" / "downloads" / "deliveroo"


def slugify(text: str) -> str:
    """Convert text to URL-safe slug."""
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_]+', '-', text)
    return text


def extract_brand_from_filename(filename: str) -> str:
    """Extract brand name from filename like ROSTICCERIA_PALAZZI_SRL_20240311_statement.csv"""
    # Remove date and suffix
    name = re.sub(r'_\d{8}_statement\.csv$', '', filename, flags=re.IGNORECASE)
    name = re.sub(r'_statement\.csv$', '', name, flags=re.IGNORECASE)
    name = re.sub(r'\.csv$', '', name, flags=re.IGNORECASE)
    # Convert underscores to spaces and title case
    name = name.replace('_', ' ').title()
    return name


def get_or_create_brand(cursor, name: str) -> int:
    """Get existing brand or create new one."""
    slug = slugify(name)

    cursor.execute("SELECT id FROM brands WHERE slug = ?", (slug,))
    row = cursor.fetchone()

    if row:
        return row[0]

    cursor.execute(
        "INSERT INTO brands (name, slug) VALUES (?, ?)",
        (name, slug)
    )
    return cursor.lastrowid


def get_or_create_location(cursor, brand_id: int, name: str, platform: str, platform_id: str = None) -> int:
    """Get existing location or create new one."""
    cursor.execute(
        "SELECT id FROM locations WHERE brand_id = ? AND platform = ? AND name = ?",
        (brand_id, platform, name)
    )
    row = cursor.fetchone()

    if row:
        return row[0]

    cursor.execute(
        "INSERT INTO locations (brand_id, name, platform, platform_id) VALUES (?, ?, ?, ?)",
        (brand_id, name, platform, platform_id)
    )
    return cursor.lastrowid


def import_csv(filepath: Path, cursor) -> dict:
    """Import a single CSV file. Returns stats."""
    stats = {"orders": 0, "skipped": 0, "errors": []}

    # Check if already imported
    cursor.execute("SELECT id FROM imports WHERE filename = ?", (filepath.name,))
    if cursor.fetchone():
        stats["skipped"] = -1  # Signal already imported
        return stats

    # Parse the CSV
    result = parse_deliveroo_invoice(str(filepath))

    if result.errors:
        stats["errors"] = result.errors
        return stats

    # Extract brand from filename or restaurant name
    brand_name = extract_brand_from_filename(filepath.name)
    if result.restaurant_name:
        brand_name = result.restaurant_name

    brand_id = get_or_create_brand(cursor, brand_name)

    # Get or create location
    location_name = result.restaurant_name or brand_name
    location_id = get_or_create_location(cursor, brand_id, location_name, "deliveroo")

    # Insert orders
    for order in result.orders:
        try:
            cursor.execute("""
                INSERT OR IGNORE INTO orders (
                    location_id, platform, order_id, order_date,
                    gross_value, commission, commission_rate, vat,
                    net_payout, refund, promo_restaurant, promo_platform,
                    tips, adjustments, is_cash
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                location_id,
                "deliveroo",
                order.order_id,
                order.order_datetime.date() if order.order_datetime else None,
                order.gross_value,
                order.commission_amount,
                order.commission_rate,
                order.vat_amount,
                order.net_payout,
                order.refund_amount,
                order.promo_restaurant_funded,
                order.promo_platform_funded,
                order.tip_amount,
                order.cash_payment_adjustment,
                1 if order.is_cash_order else 0
            ))

            if cursor.rowcount > 0:
                stats["orders"] += 1
            else:
                stats["skipped"] += 1

        except Exception as e:
            stats["errors"].append(f"Order {order.order_id}: {e}")

    # Log import
    cursor.execute(
        "INSERT INTO imports (filename, platform, rows_imported) VALUES (?, ?, ?)",
        (filepath.name, "deliveroo", stats["orders"])
    )

    return stats


def main():
    """Import all CSVs from downloads directory."""
    print(f"Importing CSVs from {DOWNLOADS_DIR}")
    print(f"Database: {DB_PATH}")
    print("=" * 60)

    if not DOWNLOADS_DIR.exists():
        print(f"Error: Downloads directory not found: {DOWNLOADS_DIR}")
        return

    csv_files = list(DOWNLOADS_DIR.glob("*.csv"))

    if not csv_files:
        print("No CSV files found in downloads directory")
        return

    print(f"Found {len(csv_files)} CSV files\n")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    total_orders = 0
    total_skipped = 0
    total_errors = 0
    already_imported = 0

    for i, filepath in enumerate(sorted(csv_files), 1):
        print(f"[{i}/{len(csv_files)}] {filepath.name[:50]}...", end=" ")

        stats = import_csv(filepath, cursor)

        if stats["skipped"] == -1:
            print("SKIP (already imported)")
            already_imported += 1
        elif stats["errors"]:
            print(f"ERROR: {stats['errors'][0][:50]}")
            total_errors += 1
        else:
            print(f"OK ({stats['orders']} orders)")
            total_orders += stats["orders"]
            total_skipped += stats["skipped"]

    conn.commit()

    # Show summary
    print("\n" + "=" * 60)
    print("IMPORT COMPLETE")
    print("=" * 60)

    cursor.execute("SELECT COUNT(*) FROM brands")
    brands = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM locations")
    locations = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM orders")
    orders = cursor.fetchone()[0]

    print(f"Brands:    {brands}")
    print(f"Locations: {locations}")
    print(f"Orders:    {orders} total ({total_orders} new)")
    print(f"Skipped:   {already_imported} files (already imported)")
    print(f"Errors:    {total_errors}")

    conn.close()


if __name__ == "__main__":
    main()
