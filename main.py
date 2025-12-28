#!/usr/bin/env python3
"""
Delivery Platform Analytics Tool - CLI Entry Point

Usage:
    python main.py sync deliveroo     # Sync all Deliveroo invoices
    python main.py sync glovo         # Sync all Glovo invoices
    python main.py sync all           # Sync all platforms
    python main.py status             # Show sync status
    python main.py report             # Generate report
"""

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

from config import settings
from storage import Database


# Setup logging
def setup_logging(verbose: bool = False):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def cmd_sync(args):
    """Run invoice sync for specified platform(s)."""
    settings.ensure_directories()
    db = Database()

    platforms = []
    if args.platform == "all":
        platforms = ["deliveroo", "glovo", "justeat"]
    else:
        platforms = [args.platform]

    for platform in platforms:
        print(f"\n{'='*50}")
        print(f"Syncing {platform.upper()}")
        print(f"{'='*50}")

        if platform == "deliveroo":
            if not settings.deliveroo.email or not settings.deliveroo.password:
                print("ERROR: DELIVEROO_EMAIL and DELIVEROO_PASSWORD not set in .env")
                continue

            from bots import DeliverooBot

            with DeliverooBot(
                email=settings.deliveroo.email,
                password=settings.deliveroo.password,
                headless=args.headless,
            ) as bot:
                invoices = bot.run_full_sync()
                print(f"Downloaded {len(invoices)} invoices")

                # TODO: Parse and store invoices
                for inv in invoices:
                    print(f"  - {inv.file_path}")

        elif platform == "glovo":
            if not settings.glovo.email or not settings.glovo.password:
                print("ERROR: GLOVO_EMAIL and GLOVO_PASSWORD not set in .env")
                continue
            print("Glovo bot not yet implemented")

        elif platform == "justeat":
            if not settings.justeat.email or not settings.justeat.password:
                print("ERROR: JUSTEAT_EMAIL and JUSTEAT_PASSWORD not set in .env")
                continue
            print("Just Eat bot not yet implemented")


def cmd_status(args):
    """Show current sync status."""
    settings.ensure_directories()
    db = Database()

    print("\n" + "="*60)
    print("DELIVERY ANALYTICS - STATUS")
    print("="*60)

    # Database stats
    summary = db.get_summary()
    print(f"\nDatabase: {settings.database_path}")
    print(f"Total Invoices: {summary.get('total_invoices', 0)}")
    print(f"Date Range: {summary.get('earliest_date', 'N/A')} to {summary.get('latest_date', 'N/A')}")

    # Financial summary
    if summary.get('total_invoices', 0) > 0:
        print(f"\nFinancial Summary:")
        print(f"  Gross Sales: €{summary.get('total_gross_sales', 0):,.2f}")
        print(f"  Net Sales:   €{summary.get('total_net_sales', 0):,.2f}")
        print(f"  Commission:  €{summary.get('total_commission', 0):,.2f}")
        print(f"  Total Payout: €{summary.get('total_payout', 0):,.2f}")
        print(f"  Total Orders: {summary.get('total_orders', 0):,}")

    # Per-platform breakdown
    print("\nPer Platform:")
    for platform in ["deliveroo", "glovo", "justeat"]:
        plat_summary = db.get_summary(platform=platform)
        count = plat_summary.get('total_invoices', 0)
        if count > 0:
            print(f"  {platform.capitalize()}: {count} invoices, €{plat_summary.get('total_payout', 0):,.2f} payout")
        else:
            print(f"  {platform.capitalize()}: No data")

    # Locations
    locations = db.get_all_locations()
    print(f"\nLocations: {len(locations)}")
    for loc in locations[:10]:  # Show first 10
        print(f"  - [{loc.platform}] {loc.name or loc.external_id}")
    if len(locations) > 10:
        print(f"  ... and {len(locations) - 10} more")

    # Downloads directory
    print(f"\nDownloads Directory: {settings.downloads_dir}")
    for platform in ["deliveroo", "glovo", "justeat"]:
        plat_dir = settings.downloads_dir / platform
        if plat_dir.exists():
            files = list(plat_dir.glob("*"))
            print(f"  {platform}: {len(files)} files")


def cmd_report(args):
    """Generate a report."""
    settings.ensure_directories()
    db = Database()

    print("\nGenerating report...")
    print("Report generation not yet implemented")
    # TODO: Implement report generation


def cmd_parse(args):
    """Parse downloaded invoice files."""
    settings.ensure_directories()
    db = Database()

    print(f"\nParsing files in {args.path or settings.downloads_dir}")
    print("Parsing not yet fully implemented - waiting for parser code from Claude.ai session")
    # TODO: Implement parsing with the parsers from Claude.ai


def main():
    parser = argparse.ArgumentParser(
        description="Delivery Platform Analytics Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Sync command
    sync_parser = subparsers.add_parser("sync", help="Sync invoices from platform")
    sync_parser.add_argument(
        "platform",
        choices=["deliveroo", "glovo", "justeat", "all"],
        help="Platform to sync"
    )
    sync_parser.add_argument(
        "--headless",
        action="store_true",
        help="Run browser in headless mode"
    )
    sync_parser.set_defaults(func=cmd_sync)

    # Status command
    status_parser = subparsers.add_parser("status", help="Show sync status")
    status_parser.set_defaults(func=cmd_status)

    # Report command
    report_parser = subparsers.add_parser("report", help="Generate report")
    report_parser.add_argument(
        "--format",
        choices=["csv", "xlsx", "pdf"],
        default="xlsx",
        help="Output format"
    )
    report_parser.add_argument(
        "--output",
        "-o",
        type=Path,
        help="Output file path"
    )
    report_parser.set_defaults(func=cmd_report)

    # Parse command
    parse_parser = subparsers.add_parser("parse", help="Parse downloaded invoice files")
    parse_parser.add_argument(
        "--path",
        type=Path,
        help="Path to file or directory to parse"
    )
    parse_parser.set_defaults(func=cmd_parse)

    args = parser.parse_args()
    setup_logging(args.verbose)

    if args.command is None:
        parser.print_help()
        return 1

    try:
        return args.func(args)
    except KeyboardInterrupt:
        print("\nInterrupted by user")
        return 130
    except Exception as e:
        logging.error(f"Error: {e}")
        if args.verbose:
            raise
        return 1


if __name__ == "__main__":
    sys.exit(main() or 0)
