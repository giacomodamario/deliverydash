#!/usr/bin/env python3
"""Manual login script for Deliveroo Partner Hub via VNC."""

import json
import os
import signal
import sys
import tempfile
from pathlib import Path

from patchright.sync_api import sync_playwright

from bots.stealth import get_random_viewport, get_random_user_agent


def save_session_atomic(context, session_file: Path):
    """Save session atomically with fsync."""
    session_file.parent.mkdir(parents=True, exist_ok=True)

    temp_fd, temp_path = tempfile.mkstemp(
        dir=session_file.parent,
        prefix='.session_',
        suffix='.tmp'
    )
    try:
        storage = context.storage_state()
        with os.fdopen(temp_fd, 'w') as f:
            json.dump(storage, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(temp_path, 0o600)
        os.replace(temp_path, str(session_file))
        print(f"Session saved to {session_file}")
    except Exception:
        if os.path.exists(temp_path):
            os.unlink(temp_path)
        raise


def main():
    session_file = Path("data/sessions/deliveroo_session.json")

    print("=" * 60)
    print("DELIVEROO MANUAL LOGIN")
    print("=" * 60)
    print()
    print("Connect via VNC to port 5901")
    print("1. Complete Cloudflare challenge if shown")
    print("2. Log in with your Deliveroo credentials")
    print("3. Wait until you see the Partner Hub dashboard")
    print("4. Press Ctrl+C here to save session and exit")
    print()
    print("=" * 60)

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            slow_mo=50,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-infobars',
                '--no-sandbox',
            ]
        )

        viewport = get_random_viewport()
        user_agent = get_random_user_agent()

        context = browser.new_context(
            accept_downloads=True,
            viewport=viewport,
            user_agent=user_agent,
            locale='en-GB',
            timezone_id='Europe/Rome',
            color_scheme='light',
        )
        page = context.new_page()

        # Handle Ctrl+C to save session
        def signal_handler(sig, frame):
            print("\nSaving session...")
            save_session_atomic(context, session_file)
            browser.close()
            sys.exit(0)

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        print("Navigating to Deliveroo Partner Hub...")
        page.goto("https://partner-hub.deliveroo.com/")

        print("Browser ready. Complete login in VNC, then Ctrl+C to save.")

        # Keep browser open until signal
        try:
            while True:
                page.wait_for_timeout(1000)
        except KeyboardInterrupt:
            signal_handler(None, None)


if __name__ == "__main__":
    main()
