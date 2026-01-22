#!/usr/bin/env python3
"""Save Glovo session from persistent browser profile."""

import json
import os
import tempfile
import time
from pathlib import Path
from patchright.sync_api import sync_playwright

SESSION_FILE = Path('data/sessions/glovo_session.json')
PROFILE_DIR = Path('data/browser_profile')

# Clean up singleton locks
for f in PROFILE_DIR.glob('Singleton*'):
    f.unlink()

print('Extracting session from browser profile...')

with sync_playwright() as p:
    context = p.chromium.launch_persistent_context(
        user_data_dir=str(PROFILE_DIR),
        headless=True,
        args=['--no-sandbox'],
    )

    page = context.pages[0] if context.pages else context.new_page()
    page.goto('https://portal.glovoapp.com/dashboard', wait_until='domcontentloaded')

    time.sleep(3)

    # Check auth using simpler JS
    auth_check = """
    (function() {
        var persist = localStorage.getItem('persist:root');
        if (!persist) return {authenticated: false, reason: 'no persist'};
        try {
            var data = JSON.parse(persist);
            var auth = JSON.parse(data.authentication || '{}');
            return {
                authenticated: auth.isAuthenticated === true,
                email: auth.user ? auth.user.email : null,
                hasToken: !!auth.accessToken
            };
        } catch(e) {
            return {authenticated: false, reason: e.message};
        }
    })()
    """

    auth = page.evaluate(auth_check)

    print(f"Authenticated: {auth.get('authenticated')}")
    if auth.get('email'):
        print(f"Email: {auth.get('email')}")
    if auth.get('hasToken'):
        print("Has access token: Yes")

    # Save session atomically with secure permissions
    storage = context.storage_state()
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

    print(f"Session saved to: {SESSION_FILE}")
    print(f"Cookies: {len(storage.get('cookies', []))}")

    # Check origins
    for origin in storage.get('origins', []):
        if 'glovoapp' in origin.get('origin', ''):
            ls_count = len(origin.get('localStorage', []))
            print(f"LocalStorage items for {origin['origin']}: {ls_count}")

    context.close()

print("\nDone! Now verify with: python -c \"from bots.glovo_api import GlovoAPIClient; api = GlovoAPIClient('data/sessions/glovo_session.json'); print(api.get_session_info())\"")
