#!/usr/bin/env python3
"""
Unified script to run delivery platform bots.

Usage:
    python run_platform.py deliveroo              # Quick sync Deliveroo (5 newest invoices)
    python run_platform.py glovo --full           # Full sync Glovo (all invoices)
    python run_platform.py deliveroo email pwd    # Run with inline credentials
"""

import sys
import argparse
from pathlib import Path

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


def main():
    parser = argparse.ArgumentParser(description="Download platform invoices")
    parser.add_argument(
        "platform",
        choices=list(PLATFORM_BOTS.keys()),
        help="Platform to sync"
    )
    parser.add_argument("--full", action="store_true", help="Full sync (all invoices)")
    parser.add_argument("--visible", action="store_true", help="Show browser window (for debugging)")
    parser.add_argument("email", nargs="?", help="Platform email")
    parser.add_argument("password", nargs="?", help="Platform password")
    args = parser.parse_args()

    setup_logging()

    platform = args.platform
    email, password = get_credentials(platform, args)

    if not email or not password:
        env_email, env_password = PLATFORM_ENV_VARS[platform]
        print(f"Usage: python run_platform.py {platform} [--full] [email password]")
        print(f"   or: Set {env_email} and {env_password} in .env")
        sys.exit(1)

    max_invoices = 100 if args.full else 5
    sync_type = "FULL" if args.full else "QUICK"
    headless = not args.visible

    print(f"\n{'='*60}")
    print(f"{platform.upper()} BOT ({sync_type} SYNC)")
    print(f"{'='*60}")
    print(f"Email: {email}")
    print(f"Max invoices: {max_invoices}")
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
        invoices = bot.run_full_sync(max_invoices=max_invoices)

        print(f"\n{'='*60}")
        print(f"COMPLETE: Downloaded {len(invoices)} new invoice(s)")
        print(f"{'='*60}")

        for inv in invoices:
            print(f"  - {inv.file_path.name}")

        print(f"\nFiles saved to: {bot.downloads_dir}")


if __name__ == "__main__":
    main()
