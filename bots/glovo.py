"""Glovo Partner Portal bot for downloading invoices."""

import re
import time
from datetime import datetime
from typing import List, Optional
from pathlib import Path

from patchright.sync_api import TimeoutError as PlaywrightTimeout

from .base import BaseBot, DownloadedInvoice
from .stealth import (
    human_sleep,
    human_type,
    human_click,
    human_mouse_move,
    human_press_and_hold,
    random_scroll,
)


class GlovoBot(BaseBot):
    """Bot for downloading invoices from Glovo Partner Portal."""

    PLATFORM_NAME = "glovo"
    LOGIN_URL = "https://portal.glovoapp.com/"
    DASHBOARD_URL = "https://portal.glovoapp.com/dashboard"

    # Selectors
    SELECTORS = {
        # Login page
        "email_input": 'input[type="email"], input[name="email"], input[id*="email"], input[placeholder*="email" i]',
        "password_input": 'input[type="password"], input[name="password"], input[id*="password"]',
        "login_button": 'button[type="submit"], button:has-text("Log in"), button:has-text("Sign in"), button:has-text("Accedi"), button:has-text("Iniciar sesión")',

        # 2FA
        "otp_input": 'input[type="text"], input[name*="code"], input[name*="otp"], input[id*="code"], input[id*="otp"], input[placeholder*="code" i], input[inputmode="numeric"]',
        "otp_submit": 'button[type="submit"], button:has-text("Verify"), button:has-text("Verifica"), button:has-text("Confirm"), button:has-text("Conferma")',

        # Navigation - Order History
        "order_history": 'a:has-text("Storico degli ordini"), a:has-text("Order history"), a:has-text("Historial"), a[href*="order-history"], a[href*="orders"]',

        # Download report
        "download_report_btn": 'button:has-text("Scarica il report"), button:has-text("Download report"), button:has-text("Descargar"), button:has-text("Export")',
        "csv_format": 'input[value="csv"], label:has-text("CSV"), button:has-text("CSV"), [data-value="csv"]',
        "download_confirm": 'button:has-text("Scarica"), button:has-text("Download"), button:has-text("Confirm")',

        # Date range
        "date_from": 'input[name*="from"], input[name*="start"], input[id*="from"], input[id*="start"]',
        "date_to": 'input[name*="to"], input[name*="end"], input[id*="to"], input[id*="end"]',
    }

    def __init__(self, *args, otp_callback=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.store_id = None  # Will be extracted from URL/page if available
        self.otp_callback = otp_callback  # Function to get OTP code from user

    def check_session_health(self) -> dict:
        """
        Check if the saved session appears to be valid.

        Returns:
            dict with:
                - valid: bool - whether session appears usable
                - authenticated: bool - whether isAuthenticated is true in localStorage
                - age_days: float - age of session file in days
                - reason: str - explanation if invalid
        """
        import json

        result = {
            "valid": False,
            "authenticated": False,
            "age_days": self.get_session_age_days(),
            "reason": ""
        }

        if not self.session_file.exists():
            result["reason"] = "No session file found"
            return result

        try:
            with open(self.session_file, 'r') as f:
                session_data = json.load(f)

            # Check localStorage for authentication state
            origins = session_data.get("origins", [])
            for origin in origins:
                if "portal.glovoapp.com" in origin.get("origin", ""):
                    for item in origin.get("localStorage", []):
                        if item.get("name") == "persist:root":
                            persist_data = json.loads(item.get("value", "{}"))
                            auth_str = persist_data.get("authentication", "{}")
                            auth_data = json.loads(auth_str)

                            result["authenticated"] = auth_data.get("isAuthenticated", False)

                            if not result["authenticated"]:
                                result["reason"] = "Session shows isAuthenticated=false"
                                return result

            # Check if session is too old
            if result["age_days"] > 1:  # Sessions older than 1 day are suspect
                result["reason"] = f"Session is {result['age_days']:.1f} days old"
                result["valid"] = result["authenticated"]  # Still try if authenticated
                return result

            # Check for required cookies
            cookies = session_data.get("cookies", [])
            cookie_names = {c.get("name") for c in cookies}

            # Glovo requires these cookies
            required_cookies = ["__cf_bm"]  # Cloudflare bot management
            for cookie in required_cookies:
                if cookie not in cookie_names:
                    result["reason"] = f"Missing required cookie: {cookie}"
                    return result

            result["valid"] = result["authenticated"]
            if result["valid"]:
                result["reason"] = "Session appears valid"

            return result

        except Exception as e:
            result["reason"] = f"Error reading session: {e}"
            return result

    def get_token_expiry_minutes(self) -> float:
        """
        Get the number of minutes until the access token expires.

        Returns:
            Minutes until expiry, or -1 if cannot be determined.
        """
        import json
        import base64
        import time

        if not self.session_file.exists():
            return -1

        try:
            with open(self.session_file, 'r') as f:
                session_data = json.load(f)

            # Find accessToken cookie
            for cookie in session_data.get('cookies', []):
                if cookie.get('name') == 'accessToken':
                    token = cookie.get('value', '')
                    if not token:
                        return -1

                    # Decode JWT payload (without verification)
                    parts = token.split('.')
                    if len(parts) < 2:
                        return -1

                    payload = parts[1]
                    # Add padding if needed
                    payload += '=' * (4 - len(payload) % 4)
                    decoded = json.loads(base64.urlsafe_b64decode(payload))

                    exp = decoded.get('exp')
                    if exp:
                        remaining = (exp - time.time()) / 60
                        return remaining

            return -1
        except Exception as e:
            self.logger.warning(f"Could not check token expiry: {e}")
            return -1

    def refresh_token_if_needed(self, min_minutes: int = 30) -> bool:
        """
        Refresh the access token if it's expiring soon.

        This works by visiting the portal, which triggers the browser's
        built-in token refresh mechanism, then saving the new session.

        Args:
            min_minutes: Refresh if less than this many minutes remaining.

        Returns:
            True if refresh was performed or not needed, False if failed.
        """
        expiry_minutes = self.get_token_expiry_minutes()

        if expiry_minutes < 0:
            self.logger.warning("Could not determine token expiry")
            return True  # Continue anyway

        self.logger.info(f"Token expires in {expiry_minutes:.1f} minutes")

        if expiry_minutes > min_minutes:
            self.logger.info(f"Token has sufficient time remaining (>{min_minutes} min)")
            return True

        self.logger.info(f"Token expiring soon, triggering refresh...")

        try:
            # Visit the dashboard to trigger the auth daemon's refresh
            self.page.goto(self.DASHBOARD_URL, wait_until='domcontentloaded', timeout=30000)
            human_sleep(3.0, 0.5)  # Wait for auth refresh to complete

            # Check if we're still logged in
            if not self._is_logged_in():
                self.logger.warning("Session expired during refresh attempt")
                return False

            # Save the refreshed session
            self.save_session()

            # Verify the new token has more time
            new_expiry = self.get_token_expiry_minutes()
            if new_expiry > expiry_minutes:
                self.logger.info(f"Token refreshed! New expiry in {new_expiry:.1f} minutes")
                return True
            else:
                self.logger.warning("Token refresh may not have worked")
                return True  # Continue anyway

        except Exception as e:
            self.logger.error(f"Error during token refresh: {e}")
            return False

    def is_perimeterx_blocked(self, response_text: str = None) -> bool:
        """
        Check if a response indicates PerimeterX bot detection block.

        Args:
            response_text: Response body to check. If None, checks current page.

        Returns:
            True if PerimeterX block detected.
        """
        # For page checks, first see if we can find dashboard elements
        # If dashboard elements exist, we're not blocked
        if response_text is None:
            try:
                # Quick check for dashboard elements - if present, not blocked
                dashboard_indicators = [
                    '[data-testid="sidebar"]',
                    'nav[role="navigation"]',
                    '.navigation-menu',
                    'a[href*="dashboard"]',
                ]
                for selector in dashboard_indicators:
                    try:
                        if self.page.locator(selector).first.is_visible(timeout=500):
                            return False  # Dashboard visible = not blocked
                    except Exception:
                        continue

                response_text = self.page.content()
            except Exception:
                return False

        # PerimeterX BLOCK-specific indicators
        # These only appear in actual block responses, not normal pages
        px_block_signatures = [
            '"blockScript":',                    # Block response JSON field
            '"altBlockScript":',                 # Block response JSON field
            'Access to this page has been denied',
            'Please verify you are a human',
            'Human verification required',
            'Press & Hold',                      # Captcha challenge text
        ]

        for sig in px_block_signatures:
            if sig in response_text:
                self.logger.warning(f"PerimeterX block detected: found '{sig}'")
                return True

        # Check for JSON block response format (API calls return this structure)
        # Must have appId AND blockScript together (not just appId)
        if '"appId":"PX' in response_text and '"blockScript":' in response_text:
            self.logger.warning("PerimeterX block detected: JSON block response")
            return True

        return False

    def handle_perimeterx_block(self) -> bool:
        """
        Handle a PerimeterX block by re-authenticating.

        This clears the session and performs a fresh login to get
        new anti-bot cookies.

        Returns:
            True if successfully re-authenticated, False otherwise.
        """
        self.logger.warning("Handling PerimeterX block - attempting re-authentication...")

        try:
            # Take screenshot for debugging
            self.screenshot("perimeterx_block")

            # Clear current cookies to force fresh auth
            if self._context:
                self._context.clear_cookies()

            # Small delay before retry
            human_sleep(2.0, 0.5)

            # Attempt fresh login
            self.logger.info("Performing fresh login...")
            if self.login():
                self.logger.info("Re-authentication successful!")
                self.save_session()
                return True
            else:
                self.logger.error("Re-authentication failed")
                return False

        except Exception as e:
            self.logger.error(f"Error during PerimeterX recovery: {e}")
            return False

    def ensure_valid_session(self) -> bool:
        """
        Ensure we have a valid, non-blocked session before operations.

        This combines token refresh and PerimeterX detection into a
        single pre-flight check.

        Returns:
            True if session is ready for use, False otherwise.
        """
        # Step 1: Check and refresh token if needed
        if not self.refresh_token_if_needed(min_minutes=30):
            self.logger.warning("Token refresh failed, attempting re-login...")
            if not self.login():
                return False

        # Step 2: Make a test request to check for PerimeterX block
        try:
            self.page.goto(self.DASHBOARD_URL, wait_until='domcontentloaded', timeout=30000)
            human_sleep(2.0, 0.3)

            if self.is_perimeterx_blocked():
                self.logger.warning("PerimeterX block detected on dashboard")
                if not self.handle_perimeterx_block():
                    return False

            # Verify we're logged in
            if not self._is_logged_in():
                self.logger.warning("Not logged in, attempting login...")
                if not self.login():
                    return False

            self.logger.info("Session validated successfully")
            return True

        except Exception as e:
            self.logger.error(f"Error validating session: {e}")
            return False

    def _wait_for_page(self, timeout: int = 10000):
        """Wait for page to be ready with human-like timing."""
        try:
            self.page.wait_for_load_state("domcontentloaded", timeout=timeout)
            human_sleep(1.0, 0.4)  # Randomized extra wait for JS rendering
        except Exception:
            pass

    def _is_logged_in(self) -> bool:
        """Check if we're already logged in based on page content."""
        # First check if login form elements are visible - this means NOT logged in
        login_form_selectors = [
            'input[type="email"]',
            'input[type="password"]',
            'button:has-text("Log in")',
            'button:has-text("Sign in")',
            'button:has-text("Accedi")',
            ':has-text("Log in with your email")',
            ':has-text("Accedi con la tua email")',
        ]

        for selector in login_form_selectors:
            try:
                element = self.page.locator(selector).first
                if element.is_visible(timeout=1000):
                    self.logger.debug(f"Login form detected: {selector}")
                    return False
            except Exception:
                continue

        current_url = self.page.url

        # Check URL patterns that indicate NOT logged in
        if "/login" in current_url or "/auth" in current_url or "/signin" in current_url:
            return False

        # Check for navigation elements that only appear when logged in
        nav_selectors = [
            'nav a[href*="dashboard"]',
            'nav a[href*="orders"]',
            '[data-testid="user-menu"]',
            '.user-menu',
            '.sidebar',
            # Glovo-specific logged-in indicators
            '[data-testid="sidebar"]',
            'nav[role="navigation"]',
            '.navigation-menu',
        ]
        for selector in nav_selectors:
            try:
                element = self.page.locator(selector).first
                if element.is_visible(timeout=1500):
                    self.logger.debug(f"Logged-in indicator found: {selector}")
                    return True
            except Exception:
                continue

        # If we're on a dashboard-like URL but didn't find login forms,
        # assume logged in (fallback)
        logged_in_patterns = ["/dashboard", "/home", "/store", "/orders", "/invoice", "/billing", "/report"]
        if any(pattern in current_url for pattern in logged_in_patterns):
            self.logger.debug(f"Assuming logged in based on URL: {current_url}")
            return True

        return False

    def _handle_press_and_hold(self) -> bool:
        """
        Check for PerimeterX 'Press & hold' captcha.

        This captcha cannot be bypassed programmatically - it detects all
        automation attempts. If detected, manual re-login is required.

        Returns True if no captcha present, False if captcha blocks us.
        """
        captcha_indicators = [
            '#px-captcha',
            '*:has-text("Press and hold")',
            '*:has-text("Prima di continuare")',
            '*:has-text("Tieni premuto")',
            '*:has-text("global.captcha.perimeterx")',
        ]

        for indicator in captcha_indicators:
            try:
                if self.page.locator(indicator).first.is_visible(timeout=2000):
                    self.logger.error(
                        "PerimeterX captcha detected. Cannot bypass automatically. "
                        "Run manual login: DISPLAY=:1 ./venv/bin/python glovo_manual_login.py"
                    )
                    return False
            except Exception:
                continue

        return True

    def _handle_2fa(self) -> bool:
        """
        Handle 2FA/OTP verification if present.
        Returns True if 2FA was handled or not needed, False if failed.
        """
        # Check if we're on a 2FA page
        otp_indicators = [
            'input[inputmode="numeric"]',
            'input[name*="code"]',
            'input[name*="otp"]',
            '*:has-text("verification code")',
            '*:has-text("codice di verifica")',
            '*:has-text("código de verificación")',
        ]

        is_2fa_page = False
        for indicator in otp_indicators:
            try:
                element = self.page.locator(indicator).first
                if element.is_visible(timeout=2000):
                    is_2fa_page = True
                    break
            except Exception:
                continue

        if not is_2fa_page:
            return True  # No 2FA needed

        self.logger.info("2FA verification detected!")
        self.screenshot("2fa_page")

        # Get OTP code
        otp_code = None

        if self.otp_callback:
            # Use callback if provided
            otp_code = self.otp_callback()
        else:
            # Prompt user in console
            self.logger.info("Please enter the 2FA code sent to your email...")
            print("\n" + "=" * 50)
            print("2FA VERIFICATION REQUIRED")
            print("Check your email for the verification code")
            print("=" * 50)
            otp_code = input("Enter 2FA code: ").strip()

        if not otp_code:
            self.logger.error("No 2FA code provided")
            return False

        # Enter the OTP code
        try:
            otp_input = self.page.locator(self.SELECTORS["otp_input"]).first
            otp_input.wait_for(timeout=5000)
            otp_input.click()
            human_sleep(0.3, 0.3)
            otp_input.fill(otp_code)
            self.logger.info("2FA code entered")

            # Try to find and click submit button
            human_sleep(0.5, 0.3)

            # Some forms auto-submit, wait a moment
            self._wait_for_page()

            # If still on 2FA page, try clicking submit
            try:
                submit_btn = self.page.locator(self.SELECTORS["otp_submit"]).first
                if submit_btn.is_visible(timeout=2000):
                    submit_btn.click()
                    self._wait_for_page()
            except Exception:
                pass

            human_sleep(2.0, 0.4)  # Wait for redirect

            # Check if we passed 2FA
            if self._is_logged_in():
                self.logger.info("2FA verification successful!")
                return True

            self.logger.error("2FA verification may have failed")
            self.screenshot("2fa_result")
            return True  # Continue anyway, let login check handle it

        except Exception as e:
            self.logger.error(f"Error during 2FA: {e}")
            return False

    def _dismiss_popups(self):
        """Dismiss Glovo-specific popups (announcements, modals, etc.)."""
        self.logger.debug("Checking for popups...")

        popup_selectors = [
            # Generic close buttons
            ('button[aria-label="Close"]', "Close button"),
            ('button[aria-label="Chiudi"]', "Close button (IT)"),
            ('button[aria-label="Cerrar"]', "Close button (ES)"),
            ('[data-testid="modal-close"]', "Modal close"),
            ('.modal-close', "Modal close class"),

            # OK/Got it buttons
            ('button:has-text("Got it")', "Got it"),
            ('button:has-text("OK")', "OK button"),
            ('button:has-text("Capito")', "Capito"),
            ('button:has-text("Entendido")', "Entendido"),
            ('button:has-text("Accept")', "Accept"),
            ('button:has-text("Accetta")', "Accetta"),

            # Skip/Later buttons
            ('button:has-text("Skip")', "Skip"),
            ('button:has-text("Later")', "Later"),
            ('button:has-text("Not now")', "Not now"),
            ('button:has-text("Maybe later")', "Maybe later"),

            # Generic dialog close
            ('[role="dialog"] button:has-text("×")', "Dialog X"),
            ('button:has-text("×")', "X button"),
            ('button:has-text("✕")', "Close symbol"),
        ]

        dismissed_count = 0
        for selector, description in popup_selectors:
            try:
                button = self.page.locator(selector).first
                if button.is_visible(timeout=500):
                    self.logger.debug(f"Dismissing popup: {description}")
                    button.click()
                    human_sleep(0.3, 0.4)  # Randomized wait after dismissing
                    dismissed_count += 1
            except Exception:
                continue

        if dismissed_count > 0:
            self.logger.debug(f"Dismissed {dismissed_count} popup(s)")
        else:
            self.logger.debug("No popups found")

    def login(self) -> bool:
        """Log into Glovo Partner Portal with human-like behavior."""
        # Check token expiry and refresh if needed
        expiry_minutes = self.get_token_expiry_minutes()
        if expiry_minutes > 0:
            self.logger.info(f"Access token expires in {expiry_minutes:.1f} minutes")
            if expiry_minutes < 30:
                self.logger.warning("Token expiring soon - will refresh after login check")

        # Check session health first
        health = self.check_session_health()
        self.logger.info(f"Session health: authenticated={health['authenticated']}, "
                        f"age={health['age_days']:.1f} days, reason={health['reason']}")

        if not health['authenticated']:
            self.logger.warning("Session is not authenticated - will need fresh login")

        # First try navigating to dashboard to check if session is valid
        self.logger.info("Checking if session is valid by navigating to dashboard...")
        self.page.goto(self.DASHBOARD_URL)
        self._wait_for_page()
        human_sleep(2.0, 0.4)

        # Check for PerimeterX block
        if self.is_perimeterx_blocked():
            self.logger.warning("PerimeterX block detected - session cookies may be stale")
            # Clear cookies and continue to fresh login
            if self._context:
                self._context.clear_cookies()
            human_sleep(1.0, 0.3)

        # Check if we're logged in (session worked)
        elif self._is_logged_in():
            self.logger.info(f"Session valid! Already logged in (URL: {self.page.url})")

            # Refresh token if expiring soon (browser visit triggers auth daemon refresh)
            if expiry_minutes > 0 and expiry_minutes < 30:
                self.logger.info("Triggering token refresh...")
                human_sleep(3.0, 0.5)  # Wait for auth daemon to refresh
                self.save_session()
                new_expiry = self.get_token_expiry_minutes()
                self.logger.info(f"Token refresh complete - new expiry in {new_expiry:.1f} minutes")

            self.screenshot("01_already_logged_in")
            return True

        # Session not valid, need to log in
        self.logger.info(f"Session not valid, navigating to {self.LOGIN_URL}")
        self.page.goto(self.LOGIN_URL)

        # Wait for page to load
        self._wait_for_page()

        # Dismiss cookie consent popup if present
        self.dismiss_cookie_consent()

        # Dismiss any popups
        self._dismiss_popups()

        # Check again if already logged in
        if self._is_logged_in():
            self.logger.info(f"Already logged in (URL: {self.page.url}), skipping login")
            self.screenshot("01_already_logged_in")
            return True

        # Take screenshot of login page
        self.screenshot("01_login_page")

        try:
            # Random scroll to appear more human (looking at the page)
            random_scroll(self.page, "down", 50)
            human_sleep(0.5, 0.3)

            # Try to find and fill email with human-like typing
            self.logger.debug("Looking for email input...")
            email_input = self.page.locator(self.SELECTORS["email_input"]).first
            email_input.wait_for(timeout=10000)

            # Click and type with human-like behavior
            human_type(self.page, self.SELECTORS["email_input"], self.email)
            self.logger.debug("Email entered")

            # Brief pause before moving to password (humans look at screen)
            human_sleep(0.4, 0.4)

            # Look for password input
            self.logger.debug("Looking for password input...")
            password_input = self.page.locator(self.SELECTORS["password_input"]).first
            password_input.wait_for(timeout=5000)

            # Type password with human-like behavior
            human_type(self.page, self.SELECTORS["password_input"], self.password)
            self.logger.debug("Password entered")

            self.screenshot("02_credentials_entered")

            # Brief pause before clicking login (humans review before submitting)
            human_sleep(0.3, 0.3)

            # Click login button with human-like behavior
            self.logger.debug("Clicking login button...")
            login_button = self.page.locator(self.SELECTORS["login_button"]).first
            box = login_button.bounding_box()
            if box:
                human_click(self.page, box['x'] + box['width']/2, box['y'] + box['height']/2)
            else:
                login_button.click()

            # Wait for navigation after login
            self._wait_for_page()
            human_sleep(2.0, 0.4)  # Randomized wait for any redirects

            # Handle "Press & hold" human verification if present
            if not self._handle_press_and_hold():
                self.logger.error("Press & hold verification failed")
                return False

            # Wait for page to process after press & hold
            self._wait_for_page()
            human_sleep(5.0, 0.3)  # Randomized wait for login to complete

            # Handle 2FA if present
            if not self._handle_2fa():
                self.logger.error("2FA verification failed")
                return False

            # Dismiss post-login popups
            self._dismiss_popups()

            current_url = self.page.url
            self.logger.info(f"Current URL after login: {current_url}")

            self.screenshot("03_after_login")

            # Check if login was successful
            if self._is_logged_in():
                self.logger.info("Login successful!")
                return True

            # Check for error messages
            error_selectors = ['.error', '.alert-danger', '.alert-error', '[role="alert"]', '.error-message']
            for selector in error_selectors:
                error_locator = self.page.locator(selector)
                if error_locator.count() > 0:
                    error_text = error_locator.first.text_content()
                    self.logger.error(f"Login error: {error_text}")
                    return False

            # If we're still on login page, it likely failed
            if "/login" in current_url or "/auth" in current_url:
                self.logger.error("Login appears to have failed - still on login page")
                return False

            return True

        except PlaywrightTimeout as e:
            self.logger.error(f"Timeout during login: {e}")
            self.screenshot("login_timeout")
            return False
        except Exception as e:
            self.logger.error(f"Login failed: {e}")
            self.screenshot("login_error")
            return False

    def _navigate_to_order_history(self) -> bool:
        """Navigate to Storico degli ordini (Order History) section."""
        self.logger.info("Navigating to Order History (Storico degli ordini)...")

        # Dismiss any popups first
        self._dismiss_popups()

        # Try clicking Order History link
        order_history_selectors = [
            ('a:has-text("Storico degli ordini")', "Storico degli ordini (IT)"),
            ('a:has-text("Order history")', "Order history (EN)"),
            ('a:has-text("Historial de pedidos")', "Historial de pedidos (ES)"),
            ('a[href*="order-history"]', "order-history href"),
            ('a[href*="orders"]', "orders href"),
            ('nav a:has-text("Ordini")', "Ordini nav"),
            ('nav a:has-text("Orders")', "Orders nav"),
            ('[data-testid*="order"]', "order data-testid"),
        ]

        for selector, description in order_history_selectors:
            try:
                link = self.page.locator(selector).first
                if link.is_visible(timeout=3000):
                    self.logger.debug(f"Found Order History link: {description}")
                    link.click()
                    self._wait_for_page()
                    human_sleep(1.0, 0.3)

                    # Handle press & hold challenge if it appears
                    if not self._handle_press_and_hold():
                        self.logger.warning("Press & hold challenge failed during navigation")

                    self._dismiss_popups()
                    self.screenshot("04_order_history_page")
                    return True
            except Exception:
                continue

        # If no link found, try direct URL patterns
        direct_urls = [
            f"{self.DASHBOARD_URL}/order-history",
            f"{self.DASHBOARD_URL}/orders",
            f"{self.LOGIN_URL}order-history",
            f"{self.LOGIN_URL}orders",
            "https://portal.glovoapp.com/order-history",
            "https://portal.glovoapp.com/orders",
        ]

        for url in direct_urls:
            try:
                self.logger.info(f"Trying direct URL: {url}")
                self.page.goto(url)
                self._wait_for_page()

                # Handle press & hold challenge if it appears
                if not self._handle_press_and_hold():
                    self.logger.warning("Press & hold challenge failed during navigation")

                # Check if we landed on a valid page
                if not ("/login" in self.page.url or "/auth" in self.page.url):
                    self._dismiss_popups()
                    self.screenshot("04_order_history_page")
                    return True
            except Exception as e:
                self.logger.debug(f"Failed to navigate to {url}: {e}")
                continue

        self.logger.warning("Could not find Order History section")
        self.screenshot("04_no_order_history_found")
        return False

    def _download_report(self, start_date: datetime = None, end_date: datetime = None) -> Optional[Path]:
        """
        Click 'Scarica il report' and download CSV.

        Args:
            start_date: Start of date range (default: 7 days ago)
            end_date: End of date range (default: today)
        """
        self.logger.debug("Looking for download button...")

        # Find and click the download report button
        download_btn_selectors = [
            'button:has-text("Scarica il report")',
            'button:has-text("Download report")',
            'button:has-text("Descargar informe")',
            'button:has-text("Export")',
            'a:has-text("Scarica il report")',
            '[data-testid*="download"]',
            '[data-testid*="export"]',
        ]

        btn_clicked = False
        for selector in download_btn_selectors:
            try:
                btn = self.page.locator(selector).first
                if btn.is_visible(timeout=3000):
                    self.logger.debug(f"Found download button: {selector}")
                    btn.click()
                    self._wait_for_page()
                    human_sleep(1.0, 0.3)
                    btn_clicked = True
                    break
            except Exception:
                continue

        if not btn_clicked:
            self.logger.warning("Could not find 'Scarica il report' button")
            self.screenshot("05_no_download_button")
            return None

        self.screenshot("05_download_dialog")

        # Select CSV format
        csv_selectors = [
            'input[value="csv"]',
            'label:has-text("CSV")',
            'button:has-text("CSV")',
            '[data-value="csv"]',
            'input[type="radio"]:near(:text("CSV"))',
            '*:has-text("File.csv")',
        ]

        for selector in csv_selectors:
            try:
                csv_option = self.page.locator(selector).first
                if csv_option.is_visible(timeout=2000):
                    self.logger.debug(f"Selecting CSV format")
                    csv_option.click()
                    human_sleep(0.5, 0.3)
                    break
            except Exception:
                continue

        # Set date range if inputs are visible
        if start_date or end_date:
            try:
                if start_date:
                    from_input = self.page.locator(self.SELECTORS["date_from"]).first
                    if from_input.is_visible(timeout=2000):
                        from_input.fill(start_date.strftime("%d/%m/%Y"))

                if end_date:
                    to_input = self.page.locator(self.SELECTORS["date_to"]).first
                    if to_input.is_visible(timeout=2000):
                        to_input.fill(end_date.strftime("%d/%m/%Y"))
            except Exception as e:
                self.logger.debug(f"Could not set date range: {e}")

        self.screenshot("06_before_download")

        # Click confirm/download button
        confirm_selectors = [
            'button:has-text("Scarica")',
            'button:has-text("Download")',
            'button:has-text("Descargar")',
            'button:has-text("Confirm")',
            'button:has-text("Conferma")',
            'button[type="submit"]',
        ]

        try:
            # Wait for download
            with self.page.expect_download(timeout=30000) as download_info:
                # Try to click confirm button
                for selector in confirm_selectors:
                    try:
                        confirm_btn = self.page.locator(selector).first
                        if confirm_btn.is_visible(timeout=1000):
                            self.logger.debug(f"Clicking download confirm")
                            confirm_btn.click()
                            break
                    except Exception:
                        continue

            download = download_info.value

            # Generate filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"glovo_orders_{timestamp}.csv"

            save_path = self.downloads_dir / filename
            download.save_as(save_path)

            self.logger.info(f"Downloaded: {save_path.name}")
            return save_path

        except PlaywrightTimeout:
            self.logger.error("Download timed out")
            self.screenshot("07_download_timeout")
            return None
        except Exception as e:
            self.logger.error(f"Download failed: {e}")
            self.screenshot("07_download_error")
            return None

    def get_locations(self) -> List[dict]:
        """Get list of all locations/stores for the account."""
        # For now, return a default location
        # TODO: Implement location/store switching if account has multiple
        return [{"id": "default", "name": "Default Store"}]

    def _get_download_links(self) -> list:
        """Find all download links/buttons on the current page."""
        download_selectors = [
            'a:has-text("CSV")',
            'button:has-text("CSV")',
            'a:has-text("Download")',
            'button:has-text("Download")',
            'a:has-text("Export")',
            'button:has-text("Export")',
            'a:has-text("Scarica")',
            'button:has-text("Scarica")',
            'a[href*=".csv"]',
            'a[download]',
            '[data-testid*="download"]',
        ]

        for selector in download_selectors:
            try:
                links = self.page.locator(selector).all()
                if links:
                    self.logger.info(f"Found {len(links)} download links using: {selector}")
                    return links
            except Exception:
                continue

        return []

    def _extract_invoice_id(self, link) -> Optional[str]:
        """Extract invoice ID from link URL or surrounding context."""
        try:
            href = link.get_attribute("href") or ""

            # Try to find ID in URL
            id_patterns = [
                r'/invoice[s]?/(\d+)',
                r'/report[s]?/(\d+)',
                r'id=(\d+)',
                r'invoice_id=(\d+)',
            ]

            for pattern in id_patterns:
                match = re.search(pattern, href, re.IGNORECASE)
                if match:
                    return match.group(1)

            # Try to get from data attributes
            data_id = link.get_attribute("data-id") or link.get_attribute("data-invoice-id")
            if data_id:
                return data_id

        except Exception:
            pass

        return None

    def _download_file(self, link, index: int) -> Optional[Path]:
        """Download a file from a link."""
        try:
            self.logger.info(f"Downloading file #{index+1}...")

            invoice_id = self._extract_invoice_id(link)
            href = link.get_attribute("href") or ""

            # Try click-based download first
            try:
                # Set download attribute to force download
                link.evaluate('el => el.setAttribute("download", "")')

                with self.page.expect_download(timeout=30000) as download_info:
                    link.click()

                download = download_info.value

                # Determine filename
                if invoice_id:
                    filename = f"glovo_invoice_{invoice_id}.csv"
                else:
                    suggested = download.suggested_filename or f"glovo_export_{index+1}.csv"
                    filename = suggested if suggested.endswith('.csv') else f"{suggested}.csv"

                save_path = self.downloads_dir / filename
                download.save_as(save_path)

                self.logger.info(f"Downloaded: {save_path.name}")
                return save_path

            except PlaywrightTimeout:
                self.logger.warning(f"Click download timed out for #{index+1}")

            # Fallback: Try request context if we have a URL
            if href and href.startswith(("http", "/")):
                self.logger.info(f"Trying request-based download for #{index+1}...")

                if href.startswith("/"):
                    full_url = f"https://portal.glovoapp.com{href}"
                else:
                    full_url = href

                try:
                    response = self.page.context.request.get(
                        full_url,
                        headers={
                            'Accept': 'text/csv, application/csv, */*',
                            'Referer': self.page.url,
                        }
                    )

                    if response.status == 200:
                        content = response.text()

                        if content and len(content) > 50:
                            if invoice_id:
                                filename = f"glovo_invoice_{invoice_id}.csv"
                            else:
                                filename = f"glovo_export_{index+1}.csv"

                            save_path = self.downloads_dir / filename

                            with open(save_path, "w", encoding="utf-8") as f:
                                f.write(content)

                            self.logger.info(f"Downloaded via request: {save_path.name}")
                            return save_path
                    else:
                        self.logger.warning(f"Request failed: HTTP {response.status}")

                except Exception as e:
                    self.logger.warning(f"Request download failed: {e}")

            return None

        except Exception as e:
            self.logger.error(f"Error downloading file #{index+1}: {e}")
            return None

    def download_invoices(
        self,
        location_id: str = None,
        start_date: datetime = None,
        end_date: datetime = None,
        max_invoices: int = 5,
    ) -> List[DownloadedInvoice]:
        """Download order reports from Glovo Partner Portal.

        For Glovo, we navigate to 'Storico degli ordini' and use
        'Scarica il report' to download CSV exports.

        Args:
            location_id: Store/location ID (not used yet)
            start_date: Start of date range (default: 7 days ago)
            end_date: End of date range (default: today)
            max_invoices: Not used for Glovo (single report download)
        """
        downloaded_invoices = []

        # Set default date range (last 7 days) if not provided
        if not end_date:
            end_date = datetime.now()
        if not start_date:
            from datetime import timedelta
            start_date = end_date - timedelta(days=7)

        # Navigate to Order History section
        if not self._navigate_to_order_history():
            self.logger.error("Could not navigate to Order History section")
            return []

        # Dismiss any popups
        self._dismiss_popups()

        # Wait for page to fully load
        self._wait_for_page()
        human_sleep(2.0, 0.4)

        # Download the report
        file_path = self._download_report(start_date=start_date, end_date=end_date)

        if file_path:
            downloaded_invoices.append(DownloadedInvoice(
                platform=self.PLATFORM_NAME,
                brand="Glovo",
                location=location_id or "default",
                invoice_id=file_path.stem,
                invoice_date=datetime.now(),
                file_path=file_path,
                file_type="csv",
            ))
            self.logger.info(f"Downloaded 1 report: {file_path.name}")
        else:
            self.logger.warning("No report downloaded")

        return downloaded_invoices


# For testing/debugging
if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)

    from config import settings

    if not settings.glovo.email or not settings.glovo.password:
        print("Please set GLOVO_EMAIL and GLOVO_PASSWORD in .env file")
        exit(1)

    with GlovoBot(
        email=settings.glovo.email,
        password=settings.glovo.password,
        headless=False,  # Show browser for debugging
    ) as bot:
        invoices = bot.run_full_sync()
        print(f"\nDownloaded {len(invoices)} invoices")
        for inv in invoices:
            print(f"  - {inv.file_path}")
