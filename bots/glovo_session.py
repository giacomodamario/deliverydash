"""Glovo session management for direct API access."""

import json
import base64
import time
import logging
import os
import tempfile
from pathlib import Path
from typing import Optional
from datetime import datetime


class GlovoSessionManager:
    """
    Manages Glovo Partner Portal session tokens.

    Handles loading, validating, and refreshing authentication tokens
    from the browser session file created by glovo_manual_login.py.
    """

    def __init__(self, session_file: Path):
        """
        Initialize session manager.

        Args:
            session_file: Path to the Playwright storage state JSON file.
        """
        self.session_file = Path(session_file)
        self.logger = logging.getLogger("glovo.session")
        self._session_data: Optional[dict] = None
        self._cookies: dict = {}
        self._load_session()

    def _load_session(self) -> bool:
        """Load session data from file."""
        if not self.session_file.exists():
            self.logger.warning(f"Session file not found: {self.session_file}")
            return False

        try:
            with open(self.session_file, 'r') as f:
                self._session_data = json.load(f)

            # Index cookies by name for easy access
            self._cookies = {}
            for cookie in self._session_data.get('cookies', []):
                self._cookies[cookie['name']] = cookie['value']

            self.logger.info(f"Session loaded with {len(self._cookies)} cookies")
            return True

        except Exception as e:
            self.logger.error(f"Error loading session: {e}")
            return False

    def reload(self) -> bool:
        """Reload session from file."""
        return self._load_session()

    def _atomic_json_write(self, path: Path, data: dict):
        """
        Write JSON data atomically with fsync to prevent corruption.

        Uses write-to-temp-then-rename pattern which is atomic on POSIX systems.
        Also sets restrictive permissions (600) on the file.
        """
        path = Path(path)
        temp_fd, temp_path = tempfile.mkstemp(
            dir=path.parent,
            prefix='.session_',
            suffix='.tmp'
        )
        try:
            with os.fdopen(temp_fd, 'w') as f:
                json.dump(data, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.chmod(temp_path, 0o600)
            os.replace(temp_path, str(path))
        except Exception:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            raise

    def get_access_token(self) -> Optional[str]:
        """Get the access token for API authentication."""
        return self._cookies.get('accessToken')

    def get_refresh_token(self) -> Optional[str]:
        """Get the refresh token for token renewal."""
        return self._cookies.get('refreshToken')

    def get_device_token(self) -> Optional[str]:
        """Get the device token."""
        return self._cookies.get('deviceToken')

    def get_device_uuid(self) -> Optional[str]:
        """Extract device UUID from deviceToken JWT."""
        device_token = self.get_device_token()
        if not device_token:
            return None

        try:
            payload = self._decode_jwt_payload(device_token)
            return payload.get('sub')
        except Exception:
            return None

    def _decode_jwt_payload(self, token: str) -> dict:
        """
        Decode JWT payload without verification.

        Args:
            token: JWT token string.

        Returns:
            Decoded payload dictionary.
        """
        parts = token.split('.')
        if len(parts) < 2:
            raise ValueError("Invalid JWT format")

        payload = parts[1]
        # Add padding if needed
        padding = 4 - len(payload) % 4
        if padding != 4:
            payload += '=' * padding

        decoded = base64.urlsafe_b64decode(payload)
        return json.loads(decoded)

    def get_token_expiry_minutes(self) -> float:
        """
        Get the number of minutes until the access token expires.

        Returns:
            Minutes until expiry, or -1 if cannot be determined.
        """
        access_token = self.get_access_token()
        if not access_token:
            self.logger.warning("No access token found")
            return -1

        try:
            payload = self._decode_jwt_payload(access_token)
            exp = payload.get('exp')

            if exp:
                remaining = (exp - time.time()) / 60
                return remaining

            return -1

        except Exception as e:
            self.logger.warning(f"Could not decode token expiry: {e}")
            return -1

    def get_token_expiry_time(self) -> Optional[datetime]:
        """Get the expiry time of the access token."""
        access_token = self.get_access_token()
        if not access_token:
            return None

        try:
            payload = self._decode_jwt_payload(access_token)
            exp = payload.get('exp')
            if exp:
                return datetime.fromtimestamp(exp)
            return None
        except Exception:
            return None

    def is_token_expiring(self, min_minutes: int = 30) -> bool:
        """
        Check if the access token is expiring soon.

        Args:
            min_minutes: Consider expiring if less than this many minutes remain.

        Returns:
            True if token is expiring or already expired.
        """
        minutes = self.get_token_expiry_minutes()
        if minutes < 0:
            return True  # Can't determine = assume expiring
        return minutes < min_minutes

    def is_token_expired(self) -> bool:
        """Check if the access token has expired."""
        minutes = self.get_token_expiry_minutes()
        return minutes <= 0

    def is_session_valid(self) -> bool:
        """
        Check if the session appears to be valid for API use.

        Returns:
            True if session has required tokens and is not expired.
        """
        # Check required tokens exist
        if not self.get_access_token():
            self.logger.warning("Session invalid: no access token")
            return False

        if not self.get_device_token():
            self.logger.warning("Session invalid: no device token")
            return False

        # Check token hasn't expired
        if self.is_token_expired():
            self.logger.warning("Session invalid: token expired")
            return False

        return True

    def get_selected_vendors(self) -> list:
        """
        Get list of selected vendor/store IDs from session.

        Returns:
            List of vendor ID strings (e.g., ["GV_IT;890642", "GV_IT;890086"]).
        """
        selected = self._cookies.get('selectedVendors')
        if not selected:
            return []

        try:
            # URL decode and parse JSON
            import urllib.parse
            decoded = urllib.parse.unquote(selected)
            data = json.loads(decoded)
            return data.get('selectedVendorIds', [])
        except Exception as e:
            self.logger.warning(f"Could not parse selectedVendors: {e}")
            return []

    def get_current_vendor(self) -> Optional[str]:
        """Get the currently selected vendor ID."""
        selected = self._cookies.get('selectedVendors')
        if not selected:
            return None

        try:
            import urllib.parse
            decoded = urllib.parse.unquote(selected)
            data = json.loads(decoded)
            return data.get('currentVendorId')
        except Exception:
            return None

    def get_is_authenticated(self) -> bool:
        """
        Check if session shows authenticated state in localStorage.

        Returns:
            True if isAuthenticated flag is True in session.
        """
        if not self._session_data:
            return False

        try:
            for origin in self._session_data.get('origins', []):
                if 'portal.glovoapp.com' in origin.get('origin', ''):
                    for item in origin.get('localStorage', []):
                        if item.get('name') == 'persist:root':
                            persist_data = json.loads(item.get('value', '{}'))
                            auth_str = persist_data.get('authentication', '{}')
                            auth_data = json.loads(auth_str)
                            return auth_data.get('isAuthenticated', False)
        except Exception as e:
            self.logger.warning(f"Could not check authentication state: {e}")

        return False

    def get_session_info(self) -> dict:
        """
        Get summary info about the current session.

        Returns:
            Dictionary with session status information.
        """
        expiry_minutes = self.get_token_expiry_minutes()
        expiry_time = self.get_token_expiry_time()

        return {
            'valid': self.is_session_valid(),
            'authenticated': self.get_is_authenticated(),
            'has_access_token': bool(self.get_access_token()),
            'has_refresh_token': bool(self.get_refresh_token()),
            'has_device_token': bool(self.get_device_token()),
            'token_expiry_minutes': expiry_minutes,
            'token_expiry_time': expiry_time.isoformat() if expiry_time else None,
            'is_expiring': self.is_token_expiring(),
            'is_expired': self.is_token_expired(),
            'vendor_count': len(self.get_selected_vendors()),
            'current_vendor': self.get_current_vendor(),
        }

    def update_access_token(self, new_token: str) -> bool:
        """
        Update the access token in the session file.

        Args:
            new_token: New access token value.

        Returns:
            True if successfully updated.
        """
        if not self._session_data:
            return False

        try:
            # Update in memory
            self._cookies['accessToken'] = new_token

            # Update in session data
            for cookie in self._session_data.get('cookies', []):
                if cookie['name'] == 'accessToken':
                    cookie['value'] = new_token
                    break
            else:
                # Add if not exists
                self._session_data['cookies'].append({
                    'name': 'accessToken',
                    'value': new_token,
                    'domain': 'portal.glovoapp.com',
                    'path': '/',
                    'expires': -1,
                    'httpOnly': False,
                    'secure': True,
                    'sameSite': 'Strict'
                })

            # Save to file atomically with proper permissions
            self._atomic_json_write(self.session_file, self._session_data)

            self.logger.info("Access token updated successfully")
            return True

        except Exception as e:
            self.logger.error(f"Failed to update access token: {e}")
            return False

    def get_all_cookies_for_requests(self) -> dict:
        """
        Get cookies formatted for use with requests library.

        Returns:
            Dictionary of cookie name -> value.
        """
        return dict(self._cookies)


# Convenience function for quick session check
def check_glovo_session(session_file: Path) -> dict:
    """
    Quick check of Glovo session status.

    Args:
        session_file: Path to session JSON file.

    Returns:
        Session info dictionary.
    """
    manager = GlovoSessionManager(session_file)
    return manager.get_session_info()


if __name__ == "__main__":
    # Quick test
    import sys
    logging.basicConfig(level=logging.INFO)

    session_path = Path("data/sessions/glovo_session.json")
    if len(sys.argv) > 1:
        session_path = Path(sys.argv[1])

    info = check_glovo_session(session_path)
    print("\nGlovo Session Status:")
    print("-" * 40)
    for key, value in info.items():
        print(f"  {key}: {value}")
