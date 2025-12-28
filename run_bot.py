#!/usr/bin/env python3
"""
Simple script to run the Deliveroo bot.

Usage:
    python run_bot.py                    # Run with .env credentials
    python run_bot.py email password     # Run with inline credentials
"""

import sys
import logging
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from config import settings
from bots import DeliverooBot


def main():
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    # Get credentials
    if len(sys.argv) >= 3:
        email = sys.argv[1]
        password = sys.argv[2]
    elif settings.deliveroo.email and settings.deliveroo.password:
        email = settings.deliveroo.email
        password = settings.deliveroo.password
    else:
        print("Usage: python run_bot.py <email> <password>")
        print("   or: Set DELIVEROO_EMAIL and DELIVEROO_PASSWORD in .env")
        sys.exit(1)

    print(f"\n{'='*60}")
    print("DELIVEROO BOT")
    print(f"{'='*60}")
    print(f"Email: {email}")
    print(f"Downloads: {settings.downloads_dir / 'deliveroo'}")
    print(f"{'='*60}\n")

    # Ensure directories exist
    settings.ensure_directories()

    # Run the bot
    with DeliverooBot(
        email=email,
        password=password,
        headless=False,  # Non-headless for debugging - can see browser
    ) as bot:
        invoices = bot.run_full_sync()

        print(f"\n{'='*60}")
        print(f"COMPLETE: Downloaded {len(invoices)} invoices")
        print(f"{'='*60}")

        for inv in invoices:
            print(f"  - {inv.file_path.name}")

        print(f"\nFiles saved to: {bot.downloads_dir}")


if __name__ == "__main__":
    main()
