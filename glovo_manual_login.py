#!/usr/bin/env python3
"""
Manual login script for Glovo.

Run this script on a machine with a display (your laptop/desktop).
It will open a browser for you to log in manually, then save the session.

Usage:
    python glovo_manual_login.py

After logging in, the session will be saved to: data/sessions/glovo_session.json
The script will then verify API access to confirm the session works.
"""

import json
import time
import random
import sys
from pathlib import Path
from datetime import datetime

try:
    from patchright.sync_api import sync_playwright
except ImportError:
    print("patchright not installed. Installing...")
    import subprocess
    subprocess.run(["pip", "install", "patchright"], check=True)
    from patchright.sync_api import sync_playwright


def get_random_user_agent() -> str:
    """Return a current Chrome user agent."""
    chrome_versions = ["130.0.0.0", "131.0.0.0", "129.0.0.0"]
    platforms = [
        "Windows NT 10.0; Win64; x64",
        "Macintosh; Intel Mac OS X 10_15_7",
    ]
    chrome_version = random.choice(chrome_versions)
    platform = random.choice(platforms)
    return f"Mozilla/5.0 ({platform}) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{chrome_version} Safari/537.36"


def verify_api_access(session_file: Path) -> dict:
    """
    Verify that the saved session can be used for API access.

    Returns:
        Dictionary with verification results.
    """
    try:
        # Import here to avoid circular imports
        from bots.glovo_session import GlovoSessionManager
        from bots.glovo_api import GlovoAPIClient

        print("\nVerifying API access...")

        # Check session
        session = GlovoSessionManager(session_file)
        info = session.get_session_info()

        result = {
            'session_valid': info['valid'],
            'authenticated': info['authenticated'],
            'token_expiry_minutes': info['token_expiry_minutes'],
            'vendor_count': info['vendor_count'],
            'api_working': False,
            'error': None,
        }

        if not info['valid']:
            result['error'] = "Session validation failed"
            return result

        # Test API access
        api = GlovoAPIClient(session_file)
        conn = api.test_connection()
        result['api_working'] = conn.get('auth_working', False)

        if not result['api_working']:
            result['error'] = conn.get('error', 'API test failed')

        # Get stores count
        stores = api.get_stores()
        result['stores_found'] = len(stores)

        return result

    except ImportError as e:
        return {
            'error': f"Import error: {e}. Run 'pip install -r requirements.txt' first.",
            'session_valid': False,
            'api_working': False,
        }
    except Exception as e:
        return {
            'error': str(e),
            'session_valid': False,
            'api_working': False,
        }


def main():
    print("=" * 60)
    print("GLOVO MANUAL LOGIN")
    print("=" * 60)
    print()
    print("A browser window will open.")
    print("Please log in to Glovo manually.")
    print("Complete any verification challenges (Press & Hold, 2FA, etc.)")
    print("After successful login, press ENTER in this terminal.")
    print()
    print("=" * 60)

    # Save to the standard location
    session_dir = Path("data/sessions")
    session_dir.mkdir(parents=True, exist_ok=True)
    session_file = session_dir / "glovo_session.json"

    user_agent = get_random_user_agent()
    print(f"\nUsing User-Agent: {user_agent}")

    with sync_playwright() as p:
        # Launch visible browser with stealth settings
        browser = p.chromium.launch(
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars",
                "--no-sandbox",
                "--disable-setuid-sandbox",
            ]
        )

        # Create context with settings matching the automated bot
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent=user_agent,
            locale="en-GB",
            timezone_id="Europe/Rome",
        )

        page = context.new_page()

        # Navigate to Glovo login
        print("Opening Glovo login page...")
        page.goto("https://portal.glovoapp.com/")

        print()
        print(">>> Please log in to Glovo in the browser window <<<")
        print(">>> Login will be detected automatically <<<")
        print()

        # Auto-detect login by checking localStorage for authentication
        max_wait = 300  # 5 minutes max
        poll_interval = 2
        waited = 0

        def is_authenticated():
            """Check localStorage for isAuthenticated flag."""
            try:
                result = page.evaluate("""() => {
                    const persist = localStorage.getItem('persist:root');
                    if (!persist) return false;
                    const data = JSON.parse(persist);
                    const auth = JSON.parse(data.authentication || '{}');
                    return auth.isAuthenticated === true && !!auth.accessToken;
                }""")
                return result
            except:
                return False

        print("Waiting for login... (checking every 2s, timeout: 5 min)")
        while waited < max_wait:
            if is_authenticated():
                print(f"\nLogin detected! (isAuthenticated=true)")
                break

            time.sleep(poll_interval)
            waited += poll_interval

            # Progress indicator every 10 seconds
            if waited % 10 == 0:
                print(f"  Still waiting... ({waited}s elapsed)")

        if waited >= max_wait:
            print("\nTimeout waiting for login. Saving session anyway...")

        current_url = page.url
        print(f"Final URL: {current_url}")

        # Save session state
        print()
        print("Saving session...")
        storage_state = context.storage_state()

        with open(session_file, "w") as f:
            json.dump(storage_state, f, indent=2)

        # Verify session has authentication
        print("\nVerifying session...")
        try:
            origins = storage_state.get("origins", [])
            for origin in origins:
                if "portal.glovoapp.com" in origin.get("origin", ""):
                    for item in origin.get("localStorage", []):
                        if item.get("name") == "persist:root":
                            persist_data = json.loads(item.get("value", "{}"))
                            auth_str = persist_data.get("authentication", "{}")
                            auth_data = json.loads(auth_str)
                            is_authenticated = auth_data.get("isAuthenticated", False)

                            if is_authenticated:
                                print("Session authentication: VERIFIED")
                            else:
                                print("WARNING: Session shows isAuthenticated=false")
                                print("You may not have fully logged in.")
        except Exception as e:
            print(f"Could not verify session: {e}")

        print()
        print(f"Session saved to: {session_file.absolute()}")

        browser.close()

        # Verify API access
        print()
        print("-" * 60)
        print("VERIFYING API ACCESS")
        print("-" * 60)

        verification = verify_api_access(session_file)

        print()
        if verification.get('session_valid'):
            print("  Session:     VALID")
        else:
            print("  Session:     INVALID")

        if verification.get('authenticated'):
            print("  Auth State:  AUTHENTICATED")
        else:
            print("  Auth State:  NOT AUTHENTICATED")

        expiry = verification.get('token_expiry_minutes', -1)
        if expiry > 0:
            hours = int(expiry // 60)
            mins = int(expiry % 60)
            print(f"  Token TTL:   {hours}h {mins}m remaining")
        else:
            print("  Token TTL:   UNKNOWN")

        stores = verification.get('stores_found', verification.get('vendor_count', 0))
        print(f"  Stores:      {stores} found")

        if verification.get('api_working'):
            print("  API Access:  WORKING")
        else:
            print(f"  API Access:  FAILED ({verification.get('error', 'unknown error')})")

        print()
        print("=" * 60)

        if verification.get('session_valid') and verification.get('authenticated'):
            print("SUCCESS! Session is ready for use.")
            print()
            print("You can now run syncs using the API client:")
            print("  python run_platform.py glovo")
            print()
            print("Or test the API client directly:")
            print("  python -m bots.glovo_api")
        else:
            print("WARNING: Session may not be fully configured.")
            print("Please try logging in again if sync fails.")

        print("=" * 60)
        print()


if __name__ == "__main__":
    main()
