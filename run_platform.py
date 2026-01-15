#!/usr/bin/env python3
"""
Unified script to run delivery platform bots.

Usage:
    python run_platform.py deliveroo              # Quick sync Deliveroo (5 newest invoices)
    python run_platform.py glovo --full           # Full sync Glovo (all invoices)
    python run_platform.py deliveroo --last-week  # Download last week's invoices
    python run_platform.py deliveroo --start-date 2024-01-01 --end-date 2024-01-31
    python run_platform.py deliveroo email pwd    # Run with inline credentials
"""

import sys
import argparse
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent))

from config import settings
from config.logging import setup_logging
from bots import DeliverooBot, GlovoBot

PLATFORM_BOTS = {
    "deliveroo": DeliverooBot,
    "glovo": GlovoBot,
}

PLATFORM_SETTINGS = {
    "deliveroo": lambda: settings.deliveroo,
    "glovo": lambda: settings.glovo,
}

PLATFORM_ENV_VARS = {
    "deliveroo": ("DELIVEROO_EMAIL", "DELIVEROO_PASSWORD"),
    "glovo": ("GLOVO_EMAIL", "GLOVO_PASSWORD"),
}


def get_credentials(platform: str, args):
    """Get credentials from args or settings."""
    if args.email and args.password:
        return args.email, args.password

    platform_creds = PLATFORM_SETTINGS[platform]()
    if platform_creds.email and platform_creds.password:
        return platform_creds.email, platform_creds.password

    return None, None


def parse_date(date_str: str) -> datetime:
    """Parse date string in YYYY-MM-DD format."""
    try:
        return datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        raise argparse.ArgumentTypeError(f"Invalid date format: {date_str}. Use YYYY-MM-DD.")


def main():
    parser = argparse.ArgumentParser(description="Download platform invoices")
    parser.add_argument(
        "platform",
        choices=list(PLATFORM_BOTS.keys()),
        help="Platform to sync"
    )
    parser.add_argument("--full", action="store_true", help="Full sync (all invoices)")
    parser.add_argument("--visible", action="store_true", help="Show browser window (for debugging)")
    parser.add_argument("--last-week", action="store_true", help="Download invoices from the last 7 days")
    parser.add_argument("--start-date", type=parse_date, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end-date", type=parse_date, help="End date (YYYY-MM-DD)")
    parser.add_argument("--max", type=int, help="Max invoices per location (default: 5, or 100 for --full)")
    parser.add_argument("email", nargs="?", help="Platform email")
    parser.add_argument("password", nargs="?", help="Platform password")
    args = parser.parse_args()

    setup_logging()

    platform = args.platform
    email, password = get_credentials(platform, args)

    if not email or not password:
        env_email, env_password = PLATFORM_ENV_VARS[platform]
        print(f"Usage: python run_platform.py {platform} [--full] [--last-week] [email password]")
        print(f"   or: Set {env_email} and {env_password} in .env")
        sys.exit(1)

    # Determine date range
    start_date = args.start_date
    end_date = args.end_date

    if args.last_week:
        # Calculate last week as Monday-Sunday
        today = datetime.now()
        # Get last Monday (if today is Monday, go back to previous Monday)
        days_since_monday = today.weekday()  # Monday=0, Sunday=6
        if days_since_monday == 0:
            # Today is Monday, go back to previous week
            last_monday = today - timedelta(days=7)
        else:
            # Go back to last Monday
            last_monday = today - timedelta(days=days_since_monday + 7)
        last_sunday = last_monday + timedelta(days=6)
        start_date = last_monday.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = last_sunday.replace(hour=23, minute=59, second=59, microsecond=0)

    if args.max:
        max_invoices = args.max
    elif args.full or args.last_week or start_date:
        max_invoices = 100
    else:
        max_invoices = 5
    sync_type = "FULL" if args.full else ("DATE RANGE" if start_date else "QUICK")
    headless = not args.visible

    print(f"\n{'='*60}")
    print(f"{platform.upper()} BOT ({sync_type} SYNC)")
    print(f"{'='*60}")
    print(f"Email: {email}")
    print(f"Max invoices: {max_invoices}")
    if start_date:
        print(f"Date range: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d') if end_date else 'now'}")
    print(f"Headless: {headless}")
    print(f"Downloads: {settings.downloads_dir / platform}")
    print(f"{'='*60}\n")

    settings.ensure_directories()

    bot_class = PLATFORM_BOTS[platform]
    with bot_class(
        email=email,
        password=password,
        headless=headless,
    ) as bot:
        invoices = bot.run_full_sync(
            max_invoices=max_invoices,
            start_date=start_date,
            end_date=end_date,
        )

        print(f"\n{'='*60}")
        print(f"COMPLETE: Downloaded {len(invoices)} new invoice(s)")
        print(f"{'='*60}")

        for inv in invoices:
            print(f"  - {inv.file_path.name}")

        print(f"\nFiles saved to: {bot.downloads_dir}")


if __name__ == "__main__":
    main()
