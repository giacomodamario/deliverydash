#!/usr/bin/env python3
"""
Automated sync wrapper for delivery-analytics.

This script orchestrates:
1. Running the bot to download new invoices
2. Importing downloaded CSVs into the database
3. Recording execution status
4. Sending notifications on success/failure

Usage:
    python sync.py                     # Quick sync (5 newest invoices)
    python sync.py --full              # Full sync (all invoices)
    python sync.py --platform glovo    # Sync specific platform (future)
"""

import sys
import time
import sqlite3
import logging
import argparse
import traceback
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent))

from config import settings
from config.logging import setup_logging
from bots import DeliverooBot, GlovoBot, GlovoAPIClient, GlovoSessionManager
from notifications import send_sync_success, send_sync_failure, send_reauth_needed
from utils import slugify

logger = logging.getLogger(__name__)


@dataclass
class SyncResult:
    """Result of a sync operation."""
    success: bool
    platform: str
    files_downloaded: int = 0
    orders_imported: int = 0
    duration_seconds: float = 0.0
    error_message: Optional[str] = None
    error_stage: Optional[str] = None


def get_or_create_brand(cursor, name: str) -> int:
    """Get existing brand or create new one."""
    slug = slugify(name)
    cursor.execute("SELECT id FROM brands WHERE slug = ?", (slug,))
    row = cursor.fetchone()
    if row:
        return row[0]
    cursor.execute("INSERT INTO brands (name, slug) VALUES (?, ?)", (name, slug))
    return cursor.lastrowid


def get_or_create_location(cursor, brand_id: int, name: str, platform: str) -> int:
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
        (brand_id, name, platform, None)
    )
    return cursor.lastrowid


def import_new_csvs(platform: str) -> tuple[int, int]:
    """
    Import any new CSV files for the given platform.

    Returns:
        Tuple of (files_imported, orders_imported)
    """
    # Import the appropriate parser
    if platform == "glovo":
        from parsers.glovo import parse_glovo_invoice as parse_invoice
    else:
        from parsers.deliveroo import parse_deliveroo_invoice as parse_invoice

    platform_dir = settings.downloads_dir / platform
    if not platform_dir.exists():
        logger.warning(f"Downloads directory not found: {platform_dir}")
        return 0, 0

    csv_files = list(platform_dir.glob("*.csv"))
    if not csv_files:
        logger.info(f"No CSV files found in {platform_dir}")
        return 0, 0

    conn = sqlite3.connect(settings.db_path)
    cursor = conn.cursor()

    files_imported = 0
    orders_imported = 0

    for filepath in sorted(csv_files):
        # Check if already imported
        cursor.execute("SELECT id FROM imports WHERE filename = ?", (filepath.name,))
        if cursor.fetchone():
            continue  # Skip already imported

        logger.info(f"Importing {filepath.name}...")

        try:
            result = parse_invoice(str(filepath))

            if result.errors:
                logger.warning(f"Parse errors in {filepath.name}: {result.errors}")
                continue

            if not result.orders:
                logger.warning(f"No orders found in {filepath.name}")
                continue

            # Get or create brand/location
            brand_name = result.restaurant_name or "Unknown"
            brand_id = get_or_create_brand(cursor, brand_name)
            location_id = get_or_create_location(cursor, brand_id, brand_name, platform)

            # Insert orders
            file_orders = 0
            for order in result.orders:
                cursor.execute("""
                    INSERT OR IGNORE INTO orders (
                        location_id, platform, order_id, order_date,
                        gross_value, commission, commission_rate, vat,
                        net_payout, refund, refund_reason, refund_fault,
                        promo_restaurant, promo_platform,
                        tips, adjustments, ad_fee, discount_commission, is_cash
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    location_id,
                    platform,
                    order.order_id,
                    order.order_datetime.date() if order.order_datetime else None,
                    order.gross_value,
                    order.commission_amount,
                    order.commission_rate,
                    order.vat_amount,
                    order.net_payout,
                    order.refund_amount,
                    order.refund_reason or None,
                    order.refund_fault or None,
                    order.promo_restaurant_funded,
                    order.promo_platform_funded,
                    0,  # tips
                    order.cash_payment_adjustment,
                    order.ad_fee,
                    order.discount_commission,
                    1 if order.is_cash_order else 0
                ))

                if cursor.rowcount > 0:
                    file_orders += 1

            # Log import
            cursor.execute(
                "INSERT INTO imports (filename, platform, rows_imported) VALUES (?, ?, ?)",
                (filepath.name, platform, file_orders)
            )

            files_imported += 1
            orders_imported += file_orders
            logger.info(f"  -> Imported {file_orders} orders")

        except Exception as e:
            logger.error(f"Error importing {filepath.name}: {e}")
            continue

    conn.commit()
    conn.close()

    return files_imported, orders_imported


def record_sync_run(result: SyncResult):
    """Record the sync execution in the database."""
    try:
        conn = sqlite3.connect(settings.db_path)
        cursor = conn.cursor()

        # Ensure sync_runs table exists
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sync_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                platform TEXT NOT NULL,
                started_at TIMESTAMP,
                completed_at TIMESTAMP,
                status TEXT NOT NULL,
                files_downloaded INTEGER DEFAULT 0,
                orders_imported INTEGER DEFAULT 0,
                duration_seconds REAL DEFAULT 0,
                error_message TEXT,
                error_stage TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            INSERT INTO sync_runs (
                platform, started_at, completed_at, status,
                files_downloaded, orders_imported, duration_seconds,
                error_message, error_stage
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            result.platform,
            datetime.now().isoformat(),
            datetime.now().isoformat(),
            "success" if result.success else "failed",
            result.files_downloaded,
            result.orders_imported,
            result.duration_seconds,
            result.error_message,
            result.error_stage
        ))

        conn.commit()
        conn.close()
        logger.info("Sync run recorded to database")
    except Exception as e:
        logger.error(f"Failed to record sync run: {e}")


def run_deliveroo_sync(max_invoices: int = 5) -> SyncResult:
    """Run a full Deliveroo sync: download + import."""
    start_time = time.time()
    result = SyncResult(success=False, platform="deliveroo")

    # Check credentials
    email = settings.deliveroo.email
    password = settings.deliveroo.password

    if not email or not password:
        result.error_message = "Deliveroo credentials not configured"
        result.error_stage = "credentials"
        logger.error(result.error_message)
        return result

    # Step 1: Run the bot to download invoices
    logger.info(f"Starting Deliveroo sync (max {max_invoices} invoices)...")
    try:
        settings.ensure_directories()

        with DeliverooBot(
            email=email,
            password=password,
            headless=True,
        ) as bot:
            invoices = bot.run_full_sync(max_invoices=max_invoices)
            result.files_downloaded = len(invoices)
            logger.info(f"Downloaded {result.files_downloaded} new invoice(s)")

    except Exception as e:
        result.error_message = str(e)
        result.error_stage = "download"
        result.duration_seconds = time.time() - start_time
        logger.error(f"Bot failed: {e}")
        logger.debug(traceback.format_exc())
        return result

    # Step 2: Import new CSVs
    logger.info("Importing new CSVs...")
    try:
        files_imported, orders_imported = import_new_csvs("deliveroo")
        result.orders_imported = orders_imported
        logger.info(f"Imported {files_imported} files, {orders_imported} orders")

    except Exception as e:
        result.error_message = str(e)
        result.error_stage = "import"
        result.duration_seconds = time.time() - start_time
        logger.error(f"Import failed: {e}")
        logger.debug(traceback.format_exc())
        return result

    # Success!
    result.success = True
    result.duration_seconds = time.time() - start_time
    logger.info(f"Sync completed successfully in {result.duration_seconds:.1f}s")

    return result


def run_glovo_sync_api(start_date: datetime = None, end_date: datetime = None) -> SyncResult:
    """
    Run Glovo sync using direct API (no browser).

    This is the preferred method - faster, no captcha issues.
    Requires a valid session created via glovo_manual_login.py.
    """
    from datetime import timedelta

    start_time = time.time()
    result = SyncResult(success=False, platform="glovo")

    session_file = settings.sessions_dir / "glovo_session.json"

    # Check session exists
    if not session_file.exists():
        result.error_message = "No Glovo session found. Run: python glovo_manual_login.py"
        result.error_stage = "session"
        logger.error(result.error_message)
        return result

    # Check session validity
    try:
        session = GlovoSessionManager(session_file)
        info = session.get_session_info()

        if not info['valid']:
            result.error_message = "Glovo session is invalid. Run: python glovo_manual_login.py"
            result.error_stage = "session"
            logger.error(result.error_message)
            # Send re-auth notification
            try:
                send_reauth_needed("glovo", "Session is invalid or expired")
            except Exception:
                pass
            return result

        if info['is_expiring']:
            logger.warning(f"Token expiring in {info['token_expiry_minutes']:.0f} minutes")

    except Exception as e:
        result.error_message = f"Session check failed: {e}"
        result.error_stage = "session"
        logger.error(result.error_message)
        return result

    # Set default date range
    if end_date is None:
        end_date = datetime.now()
    if start_date is None:
        start_date = end_date - timedelta(days=7)

    # Step 1: Fetch data via API
    logger.info(f"Starting Glovo API sync ({start_date.date()} to {end_date.date()})...")
    try:
        settings.ensure_directories()
        api = GlovoAPIClient(session_file, auto_refresh=True)

        # Test connection
        conn = api.test_connection()
        if not conn.get('session_valid'):
            result.error_message = "API connection failed - session invalid"
            result.error_stage = "api"
            send_reauth_needed("glovo", "API connection failed")
            return result

        # Get stores
        stores = api.get_stores()
        logger.info(f"Found {len(stores)} stores")

        # Fetch orders for each store
        total_orders = 0
        for store in stores:
            store_id = store.get('id', store.get('store_id'))
            logger.info(f"Fetching orders for store {store_id}...")

            try:
                orders = api.get_orders(store_id, start_date, end_date)
                total_orders += len(orders)
                logger.info(f"  -> Found {len(orders)} orders")

                # TODO: Save orders to CSV or directly to database
                # For now, just count them
                result.files_downloaded += 1  # Count as "downloaded" even though it's API

            except Exception as e:
                logger.warning(f"Failed to fetch orders for store {store_id}: {e}")
                continue

        logger.info(f"Total orders fetched: {total_orders}")

    except ValueError as e:
        # Auth errors - need re-auth
        result.error_message = str(e)
        result.error_stage = "api"
        result.duration_seconds = time.time() - start_time
        logger.error(f"API auth error: {e}")
        send_reauth_needed("glovo", str(e))
        return result

    except Exception as e:
        result.error_message = str(e)
        result.error_stage = "api"
        result.duration_seconds = time.time() - start_time
        logger.error(f"API failed: {e}")
        logger.debug(traceback.format_exc())
        return result

    # Step 2: Import any existing CSVs (from previous browser-based downloads)
    logger.info("Importing existing CSVs...")
    try:
        files_imported, orders_imported = import_new_csvs("glovo")
        result.orders_imported = orders_imported
        logger.info(f"Imported {files_imported} files, {orders_imported} orders")

    except Exception as e:
        # Non-fatal - API sync still succeeded
        logger.warning(f"CSV import failed (non-fatal): {e}")

    # Success!
    result.success = True
    result.duration_seconds = time.time() - start_time
    logger.info(f"API sync completed successfully in {result.duration_seconds:.1f}s")

    return result


def run_glovo_sync_browser(max_invoices: int = 5) -> SyncResult:
    """
    Run Glovo sync using browser automation (legacy method).

    Warning: This may fail due to PerimeterX captcha.
    Use run_glovo_sync_api() instead when possible.
    """
    start_time = time.time()
    result = SyncResult(success=False, platform="glovo")

    # Check credentials
    email = settings.glovo.email
    password = settings.glovo.password

    if not email or not password:
        result.error_message = "Glovo credentials not configured"
        result.error_stage = "credentials"
        logger.error(result.error_message)
        return result

    # Step 1: Run the bot to download invoices
    logger.info(f"Starting Glovo browser sync (max {max_invoices} invoices)...")
    logger.warning("Note: Browser sync may fail due to PerimeterX captcha")
    try:
        settings.ensure_directories()

        with GlovoBot(
            email=email,
            password=password,
            headless=True,
        ) as bot:
            invoices = bot.run_full_sync(max_invoices=max_invoices)
            result.files_downloaded = len(invoices)
            logger.info(f"Downloaded {result.files_downloaded} new invoice(s)")

    except Exception as e:
        result.error_message = str(e)
        result.error_stage = "download"
        result.duration_seconds = time.time() - start_time
        logger.error(f"Bot failed: {e}")
        logger.debug(traceback.format_exc())
        return result

    # Step 2: Import new CSVs
    logger.info("Importing new CSVs...")
    try:
        files_imported, orders_imported = import_new_csvs("glovo")
        result.orders_imported = orders_imported
        logger.info(f"Imported {files_imported} files, {orders_imported} orders")

    except Exception as e:
        result.error_message = str(e)
        result.error_stage = "import"
        result.duration_seconds = time.time() - start_time
        logger.error(f"Import failed: {e}")
        logger.debug(traceback.format_exc())
        return result

    # Success!
    result.success = True
    result.duration_seconds = time.time() - start_time
    logger.info(f"Sync completed successfully in {result.duration_seconds:.1f}s")

    return result


def run_glovo_sync(max_invoices: int = 5, use_api: bool = True) -> SyncResult:
    """
    Run a full Glovo sync.

    Args:
        max_invoices: Maximum invoices to download (browser mode only).
        use_api: If True, use direct API (recommended). If False, use browser.

    Returns:
        SyncResult with success status and statistics.
    """
    if use_api:
        # Try API first (faster, no captcha)
        logger.info("Attempting Glovo sync via API...")
        result = run_glovo_sync_api()

        if result.success:
            return result

        # If API failed due to session issues, don't fall back to browser
        if result.error_stage == "session":
            logger.error("API sync failed - manual re-authentication required")
            return result

        # For other API errors, could optionally fall back to browser
        logger.warning("API sync failed, session may need refresh")
        return result

    else:
        # Browser mode (legacy, may hit captcha)
        return run_glovo_sync_browser(max_invoices=max_invoices)


def main():
    """Main entry point for automated sync."""
    parser = argparse.ArgumentParser(description="Automated delivery analytics sync")
    parser.add_argument("--full", action="store_true", help="Full sync (all invoices)")
    parser.add_argument("--platform", default="deliveroo", choices=["deliveroo", "glovo"],
                        help="Platform to sync (default: deliveroo)")
    parser.add_argument("--no-notify", action="store_true", help="Disable notifications")
    args = parser.parse_args()

    # Setup logging
    setup_logging()

    logger.info("=" * 60)
    logger.info(f"AUTOMATED SYNC STARTING")
    logger.info(f"Platform: {args.platform}")
    logger.info(f"Mode: {'FULL' if args.full else 'QUICK'}")
    logger.info("=" * 60)

    # Run sync based on platform
    max_invoices = 100 if args.full else 5

    if args.platform == "deliveroo":
        result = run_deliveroo_sync(max_invoices=max_invoices)
    elif args.platform == "glovo":
        result = run_glovo_sync(max_invoices=max_invoices)
    else:
        logger.error(f"Platform {args.platform} not supported")
        result = SyncResult(
            success=False,
            platform=args.platform,
            error_message=f"Platform {args.platform} not supported",
            error_stage="init"
        )

    # Record to database
    record_sync_run(result)

    # Send notification
    if not args.no_notify:
        if result.success:
            send_sync_success(
                platform=result.platform,
                files_downloaded=result.files_downloaded,
                orders_imported=result.orders_imported,
                duration_seconds=result.duration_seconds
            )
        else:
            send_sync_failure(
                platform=result.platform,
                error_message=result.error_message or "Unknown error",
                stage=result.error_stage or "unknown"
            )

    # Log final status
    logger.info("=" * 60)
    if result.success:
        logger.info("SYNC COMPLETE")
        logger.info(f"Files downloaded: {result.files_downloaded}")
        logger.info(f"Orders imported: {result.orders_imported}")
        logger.info(f"Duration: {result.duration_seconds:.1f}s")
    else:
        logger.error("SYNC FAILED")
        logger.error(f"Stage: {result.error_stage}")
        logger.error(f"Error: {result.error_message}")
    logger.info("=" * 60)

    # Exit with appropriate code
    sys.exit(0 if result.success else 1)


if __name__ == "__main__":
    main()
