#!/usr/bin/env python3
"""
Deliveroo session keep-alive script.

Visits the Partner Hub to keep the session fresh and prevent expiry.
Run via cron every 12 hours to maintain session validity.

Unlike Glovo (which has 4-hour token expiry), Deliveroo sessions last longer
but still benefit from periodic refresh to avoid Cloudflare re-challenges.
"""

import json
import os
import sys
import logging
import tempfile
from pathlib import Path
from datetime import datetime

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

from bots.deliveroo import DeliverooBot

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("deliveroo.keepalive")


def get_session_age_hours(session_file: Path) -> float:
    """Get session file age in hours."""
    if not session_file.exists():
        return float('inf')
    age_seconds = datetime.now().timestamp() - session_file.stat().st_mtime
    return age_seconds / 3600


def main():
    session_file = Path("data/sessions/deliveroo_session.json")

    # Check if session exists
    if not session_file.exists():
        logger.error("No session file found - manual login required")
        print("ERROR: No session. Run: DISPLAY=:1 ./venv/bin/python deliveroo_manual_login.py")
        sys.exit(1)

    age_hours = get_session_age_hours(session_file)
    logger.info(f"Session age: {age_hours:.1f} hours")

    # Warn if session is old (> 48 hours)
    if age_hours > 48:
        logger.warning(f"Session is {age_hours:.1f} hours old - may need manual refresh")

    # Visit portal to refresh session
    logger.info("Refreshing session by visiting Partner Hub...")

    try:
        # Use empty credentials - session-based auth only
        with DeliverooBot(
            email='keepalive',
            password='keepalive',
            headless=True,
        ) as bot:
            if bot.login():
                logger.info("Session refreshed successfully")

                # Check new age (should be ~0 after save)
                new_age = get_session_age_hours(session_file)
                logger.info(f"Session refreshed (age: {new_age:.1f} hours)")
                print(f"OK: Deliveroo session refreshed")
            else:
                logger.error("Login failed - session may need manual refresh via VNC")
                print("ERROR: Login failed. Run: DISPLAY=:1 ./venv/bin/python deliveroo_manual_login.py")
                sys.exit(1)

    except Exception as e:
        logger.error(f"Keep-alive failed: {e}")
        print(f"ERROR: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
