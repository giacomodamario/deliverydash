#!/usr/bin/env python3
"""
Glovo login with persistent browser profile.

This keeps the browser open indefinitely. Log in via VNC, then:
1. After login, the script auto-detects and saves the session
2. Press Ctrl+C to close when done

Usage:
    DISPLAY=:1 python glovo_login_persistent.py
"""

import json
import os
import tempfile
import time
import signal
import sys
from pathlib import Path
from patchright.sync_api import sync_playwright

SESSION_FILE = Path('data/sessions/glovo_session.json')
PROFILE_DIR = Path('data/browser_profile')

# Ensure directories exist
SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
PROFILE_DIR.mkdir(parents=True, exist_ok=True)


def check_authenticated(page) -> dict:
    """Check if user is authenticated by examining localStorage."""
    try:
        result = page.evaluate("""() => {
            const persist = localStorage.getItem('persist:root');
            if (!persist) return {authenticated: false, reason: 'no persist:root'};

            try {
                const data = JSON.parse(persist);
                const auth = JSON.parse(data.authentication || '{}');
                return {
                    authenticated: auth.isAuthenticated === true,
                    hasToken: !!auth.accessToken,
                    user: auth.user ? auth.user.email : null,
                    reason: auth.isAuthenticated ? 'logged in' : 'not authenticated'
                };
            } catch(e) {
                return {authenticated: false, reason: 'parse error: ' + e.message};
            }
        }""")
        return result
    except Exception as e:
        return {'authenticated': False, 'reason': str(e)}


def save_session(context, page):
    """Save the browser session atomically with secure permissions."""
    print("\n>>> Saving session...")
    storage = context.storage_state()

    # Atomic write: write to temp file, fsync, then rename
    temp_fd, temp_path = tempfile.mkstemp(
        dir=SESSION_FILE.parent,
        prefix='.session_',
        suffix='.tmp'
    )
    try:
        with os.fdopen(temp_fd, 'w') as f:
            json.dump(storage, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(temp_path, 0o600)
        os.replace(temp_path, str(SESSION_FILE))
    except Exception:
        if os.path.exists(temp_path):
            os.unlink(temp_path)
        raise

    print(f">>> Session saved to: {SESSION_FILE}")

    # Verify
    auth_state = check_authenticated(page)
    if auth_state.get('authenticated'):
        print(f">>> Auth verified: {auth_state.get('user', 'unknown user')}")
        return True
    else:
        print(f">>> WARNING: {auth_state.get('reason')}")
        return False


def main():
    print("=" * 60)
    print("GLOVO LOGIN - PERSISTENT BROWSER")
    print("=" * 60)
    print()
    print("Instructions:")
    print("1. A browser will open on VNC display :1")
    print("2. Log in to Glovo (complete 2FA if needed)")
    print("3. Session auto-saves when login detected")
    print("4. Press Ctrl+C when done")
    print()
    print("=" * 60)

    with sync_playwright() as p:
        # Use persistent context - this saves cookies/storage to disk
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE_DIR),
            headless=False,
            viewport={'width': 1920, 'height': 1080},
            args=[
                '--no-sandbox',
                '--disable-blink-features=AutomationControlled',
            ],
            locale='en-GB',
            timezone_id='Europe/Rome',
        )

        page = context.pages[0] if context.pages else context.new_page()

        # Check if already logged in from previous session
        page.goto('https://portal.glovoapp.com/')
        time.sleep(3)

        auth_state = check_authenticated(page)
        if auth_state.get('authenticated'):
            print(f"\n>>> Already logged in as: {auth_state.get('user')}")
            save_session(context, page)
        else:
            print(f"\n>>> Not logged in. Please log in via VNC (port 5901)")
            print(f">>> Current URL: {page.url}")

        # Monitor for login
        print("\n>>> Monitoring for login (checking every 5s)...")
        last_url = page.url
        check_count = 0

        try:
            while True:
                time.sleep(5)
                check_count += 1

                current_url = page.url
                if current_url != last_url:
                    print(f">>> URL changed: {current_url}")
                    last_url = current_url

                auth_state = check_authenticated(page)

                if auth_state.get('authenticated'):
                    print(f"\n>>> LOGIN DETECTED!")
                    if save_session(context, page):
                        print(">>> Session saved successfully!")
                        print(">>> You can now close this or press Ctrl+C")
                        # Keep running so user can verify
                        while True:
                            time.sleep(60)
                            # Re-save periodically to catch token refreshes
                            save_session(context, page)

                # Progress every 30 seconds
                if check_count % 6 == 0:
                    print(f">>> Still waiting... ({check_count * 5}s, URL: {current_url[:50]}...)")

        except KeyboardInterrupt:
            print("\n>>> Ctrl+C received, saving final session...")
            save_session(context, page)
            print(">>> Browser closing...")

        context.close()

    print("\n>>> Done!")


if __name__ == '__main__':
    main()
