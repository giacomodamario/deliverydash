#!/usr/bin/env python3
"""
Run the Deliveroo bot with a visible browser for manual Cloudflare solving.

Usage:
    python run_manual.py

This will open a visible browser window. When Cloudflare challenge appears,
wait for it to resolve or interact with it manually. The session will be saved
for future automated runs.
"""

import sys
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%H:%M:%S'
)

from config import settings
from bots import DeliverooBot

def main():
    # Check credentials
    if not settings.deliveroo.email or not settings.deliveroo.password:
        print("ERROR: Please set DELIVEROO_EMAIL and DELIVEROO_PASSWORD in .env file")
        sys.exit(1)

    print("=" * 60)
    print("DELIVEROO BOT - MANUAL MODE (Visible Browser)")
    print("=" * 60)
    print(f"Email: {settings.deliveroo.email}")
    print()
    print("INSTRUCTIONS:")
    print("1. A browser window will open")
    print("2. If Cloudflare challenge appears, wait for it to resolve")
    print("3. If needed, interact with the challenge manually")
    print("4. The bot will then download invoices automatically")
    print("5. Session will be saved for future runs")
    print("=" * 60)
    print()

    input("Press Enter to start...")

    with DeliverooBot(
        email=settings.deliveroo.email,
        password=settings.deliveroo.password,
        headless=False,  # Visible browser!
        slow_mo=200,     # Slower for visibility
    ) as bot:
        invoices = bot.run_full_sync(max_invoices=10)

        print()
        print("=" * 60)
        print(f"COMPLETE: Downloaded {len(invoices)} invoice(s)")
        print("=" * 60)

        if invoices:
            for inv in invoices:
                print(f"  - {inv.file_path.name}")

        print()
        print(f"Session saved to: {bot.session_file}")
        print("Future runs should work automatically until the session expires.")

if __name__ == "__main__":
    main()
