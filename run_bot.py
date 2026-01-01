#!/usr/bin/env python3
"""
Simple script to run the Deliveroo bot.

Usage:
    python run_bot.py                    # Quick sync (5 newest invoices)
    python run_bot.py --full             # Full sync (all invoices)
    python run_bot.py email password     # Run with inline credentials
"""

import sys
import argparse
import logging
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from config import settings
from bots import DeliverooBot


def main():
    # Parse arguments
    parser = argparse.ArgumentParser(description="Download Deliveroo invoices")
    parser.add_argument("--full", action="store_true", help="Full sync (all invoices)")
    parser.add_argument("email", nargs="?", help="Deliveroo email")
    parser.add_argument("password", nargs="?", help="Deliveroo password")
    args = parser.parse_args()

    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    # Get credentials
    if args.email and args.password:
        email = args.email
        password = args.password
    elif settings.deliveroo.email and settings.deliveroo.password:
        email = settings.deliveroo.email
        password = settings.deliveroo.password
    else:
        print("Usage: python run_bot.py [--full] [email password]")
        print("   or: Set DELIVEROO_EMAIL and DELIVEROO_PASSWORD in .env")
        sys.exit(1)

    max_invoices = 100 if args.full else 5
    sync_type = "FULL" if args.full else "QUICK"

    print(f"\n{'='*60}")
    print(f"DELIVEROO BOT ({sync_type} SYNC)")
    print(f"{'='*60}")
    print(f"Email: {email}")
    print(f"Max invoices: {max_invoices}")
    print(f"Downloads: {settings.downloads_dir / 'deliveroo'}")
    print(f"{'='*60}\n")

    # Ensure directories exist
    settings.ensure_directories()

    # Run the bot
    with DeliverooBot(
        email=email,
        password=password,
        headless=True,  # Set to False to debug
    ) as bot:
        invoices = bot.run_full_sync(max_invoices=max_invoices)

        print(f"\n{'='*60}")
        print(f"COMPLETE: Downloaded {len(invoices)} new invoice(s)")
        print(f"{'='*60}")

        for inv in invoices:
            print(f"  - {inv.file_path.name}")

        print(f"\nFiles saved to: {bot.downloads_dir}")


if __name__ == "__main__":
    main()
