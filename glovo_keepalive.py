#!/usr/bin/env python3
"""
Glovo session keep-alive script.

Visits the portal to trigger token refresh and save the updated session.
Run via cron every 2-3 hours to prevent session expiry.
"""

import sys
import logging
from pathlib import Path
from datetime import datetime

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

from bots.glovo import GlovoBot
from bots.glovo_session import GlovoSessionManager

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("glovo.keepalive")


def main():
    session_file = Path("data/sessions/glovo_session.json")

    # Check current session status
    session = GlovoSessionManager(session_file)
    info = session.get_session_info()

    logger.info(f"Current token expires in {info['token_expiry_minutes']:.0f} minutes")

    if info['is_expired']:
        logger.error("Session already expired - manual re-login required")
        print("ERROR: Session expired. Run: DISPLAY=:1 ./venv/bin/python glovo_manual_login.py")
        sys.exit(1)

    # Visit portal to refresh token
    logger.info("Refreshing session by visiting portal...")

    try:
        with GlovoBot(
            email='keepalive',
            password='keepalive',
            headless=True,
        ) as bot:
            if bot.login():
                logger.info("Session refreshed successfully")

                # Check new expiry
                session.reload()
                new_info = session.get_session_info()
                logger.info(f"New token expires in {new_info['token_expiry_minutes']:.0f} minutes")
                print(f"OK: Session valid for {new_info['token_expiry_minutes']:.0f} more minutes")
            else:
                logger.error("Login failed - session may need manual refresh")
                sys.exit(1)

    except Exception as e:
        logger.error(f"Keep-alive failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
