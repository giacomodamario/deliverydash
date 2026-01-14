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
        Handle Glovo's 'Press & hold' human verification.
        Returns True if handled or not present, False if failed.
        """
        # Check for the press & hold modal (multiple languages + raw translation keys)
        modal_indicators = [
            '*:has-text("Press and hold")',
            '*:has-text("Before we continue")',
            '*:has-text("Prima di continuare")',  # Italian
            '*:has-text("Tieni premuto")',        # Italian button text
            '*:has-text("Antes de continuar")',   # Spanish
            'button:has-text("Press & hold")',
            'button:has-text("Tieni premuto")',   # Italian
            # Raw translation keys (when localization fails)
            '*:has-text("global.captcha.perimeterx")',
            '*:has-text("captcha.perimeterx")',
            '#px-captcha',  # PerimeterX captcha container
        ]

        is_challenge = False
        for indicator in modal_indicators:
            try:
                element = self.page.locator(indicator).first
                if element.is_visible(timeout=2000):
                    is_challenge = True
                    break
            except Exception:
                continue

        if not is_challenge:
            return True  # No challenge present

        self.logger.info("'Press & hold' human verification detected, attempting to solve...")

        # Wait for the button to fully render (it may load asynchronously)
        # The button sometimes appears grey initially then becomes green with text
        self.logger.info("Waiting for hold button to render...")
        human_sleep(3.0, 0.5)  # Increased wait time for button to fully render

        try:
            # Find the press & hold button
            # The button text is EXACTLY "Tieni premuto" (IT) / "Press & hold" (EN)
            # NOT the instruction text "Tieni premuto per confermare che sei un essere umano"
            btn_selectors = [
                # EXACT text match for the button (NOT the instruction paragraph)
                # The button only has "Tieni premuto" text, the paragraph has longer text
                '[role="dialog"] button:text-is("Tieni premuto")',
                '[role="dialog"] button:text-is("Press & hold")',
                '[role="dialog"] button:text-is("Press & Hold")',
                '.MuiDialogContent-root button:text-is("Tieni premuto")',
                '.MuiDialogContent-root button:text-is("Press & hold")',
                # Button containing text (but shorter than instruction paragraph)
                '[role="dialog"] button:has-text("Tieni premuto"):not(:has-text("confermare"))',
                '[role="dialog"] button:has-text("Press & hold"):not(:has-text("confirm"))',
                # Generic button selectors excluding close button
                '.MuiDialogContent-root button:not(:has-text("Chiudi")):not(:has-text("Close"))',
                '[role="dialog"] button:not(:has-text("Chiudi")):not(:has-text("Close"))',
            ]

            found_btn = None
            for selector in btn_selectors:
                try:
                    locator = self.page.locator(selector).first
                    if locator.is_visible(timeout=1500):
                        btn_text = locator.text_content() or ""
                        # Make sure we don't get the "Chiudi" (close) button
                        if "chiudi" not in btn_text.lower() and "close" not in btn_text.lower():
                            self.logger.info(f"Found press & hold button: {selector} (text: {btn_text})")
                            found_btn = locator
                            break
                except Exception:
                    continue

            # If still not found, search ALL element types with the text
            # The hold button might be a div, span, or custom element - not necessarily a <button>
            if not found_btn:
                self.logger.info("Searching all element types for hold button text...")
                try:
                    # Find any element with exact text "Tieni premuto" or translation keys
                    hold_texts = [
                        'Tieni premuto', 'Press & hold', 'Press & Hold', 'Press and hold',
                        'global.captcha.perimeterx.button',  # Raw translation key
                    ]
                    for hold_text in hold_texts:
                        try:
                            elem = self.page.locator(f'[role="dialog"] *:text-is("{hold_text}")').first
                            if elem.is_visible(timeout=1000):
                                tag = elem.evaluate("el => el.tagName")
                                self.logger.info(f"Found hold element: <{tag}> with text '{hold_text}'")
                                found_btn = elem
                                break
                        except Exception:
                            continue
                except Exception as e:
                    self.logger.warning(f"Element search failed: {e}")

            # Try broader search - MuiDialog class instead of role="dialog"
            if not found_btn:
                self.logger.info("Searching MuiDialog for hold button...")
                try:
                    # Search in MUI dialog components
                    all_elements = self.page.locator('.MuiDialog-root *:visible, .MuiDialog-container *:visible').all()
                    self.logger.info(f"Found {len(all_elements)} elements in MuiDialog")
                    for elem in all_elements[:40]:  # Check first 40 elements
                        try:
                            text = (elem.text_content() or "").strip()
                            tag = elem.evaluate("el => el.tagName")
                            cls = elem.evaluate("el => el.className") or ""
                            # Log elements with short text or button classes
                            if (len(text) < 100 and text) or 'button' in cls.lower():
                                self.logger.info(f"  <{tag}> class='{cls[:50]}' text='{text[:40]}'")
                            # Look for exact match or button-like elements
                            if text.lower() in ['tieni premuto', 'press & hold', 'press and hold', 'mantener presionado', 'global.captcha.perimeterx.button']:
                                box = elem.bounding_box()
                                self.logger.info(f"Found element <{tag}> with exact text '{text}', box: {box}")
                                if box and box.get('width', 0) > 50 and box.get('height', 0) > 30:
                                    found_btn = elem
                                    break
                        except Exception:
                            continue
                except Exception as e:
                    self.logger.warning(f"MuiDialog search failed: {e}")

            # Try searching the entire page for elements with specific text
            if not found_btn:
                self.logger.info("Searching entire page for hold button text...")
                try:
                    # Direct locator for exact text anywhere on page
                    hold_elem = self.page.get_by_text("Tieni premuto", exact=True)
                    if hold_elem.is_visible(timeout=2000):
                        tag = hold_elem.evaluate("el => el.tagName")
                        box = hold_elem.bounding_box()
                        self.logger.info(f"Found by get_by_text: <{tag}> box={box}")
                        if box and box.get('width', 0) > 50:
                            found_btn = hold_elem
                except Exception as e:
                    self.logger.info(f"get_by_text search failed: {e}")

            # Fallback: Find the button area by looking for PerimeterX captcha container
            if not found_btn:
                self.logger.info("Looking for button area by position/size...")
                try:
                    # Try to find by px-captcha container first (works with translation keys)
                    px_captcha = self.page.locator('#px-captcha').first
                    px_box = px_captcha.bounding_box(timeout=3000)

                    if px_box:
                        # Click in the center of the px-captcha container
                        btn_x = px_box['x'] + px_box['width'] / 2
                        btn_y = px_box['y'] + px_box['height'] / 2
                        self.logger.info(f"Using px-captcha position: x={btn_x}, y={btn_y}")
                        self.logger.info(f"px-captcha box: {px_box}")
                        found_btn = {"x": btn_x, "y": btn_y, "calculated": True}
                    else:
                        # Fallback to paragraph + close button positioning
                        para_selectors = [
                            'p:has-text("Tieni premuto per confermare")',
                            '*:has-text("global.captcha.perimeterx.description")',
                            '.MuiDialogContent-root span',
                        ]
                        para_box = None
                        for sel in para_selectors:
                            try:
                                para = self.page.locator(sel).first
                                para_box = para.bounding_box(timeout=2000)
                                if para_box:
                                    break
                            except Exception:
                                continue

                        # Find the close button position
                        chiudi_selectors = [
                            'button:has-text("Chiudi")',
                            'button:has-text("Close")',
                            'button:has-text("global.captcha.perimeterx.close")',
                        ]
                        chiudi_box = None
                        for sel in chiudi_selectors:
                            try:
                                chiudi = self.page.locator(sel).first
                                chiudi_box = chiudi.bounding_box(timeout=2000)
                                if chiudi_box:
                                    break
                            except Exception:
                                continue

                        if para_box and chiudi_box:
                            btn_y = (para_box['y'] + para_box['height'] + chiudi_box['y']) / 2
                            btn_x = para_box['x'] + para_box['width'] / 2
                            self.logger.info(f"Calculated button position: x={btn_x}, y={btn_y}")
                            self.logger.info(f"Para box: {para_box}, Chiudi box: {chiudi_box}")
                            found_btn = {"x": btn_x, "y": btn_y, "calculated": True}
                except Exception as e:
                    self.logger.warning(f"Position calculation failed: {e}")

            if not found_btn:
                self.logger.warning("Could not find press & hold button")
                self.screenshot("press_hold_button_not_found")
                return False

            # Take screenshot before attempting hold
            self.screenshot("press_hold_before_action")

            # Simulate press and hold with human-like behavior
            self.logger.info("Performing human-like press & hold action...")

            import random

            # Get coordinates - either from bounding box or calculated position
            if isinstance(found_btn, dict) and found_btn.get("calculated"):
                # Use calculated position directly
                x = found_btn["x"] + random.gauss(0, 3)
                y = found_btn["y"] + random.gauss(0, 3)
                self.logger.info(f"Using calculated position: ({x:.0f}, {y:.0f})")
            else:
                # Get button bounding box
                box = found_btn.bounding_box()
                if not box:
                    self.logger.warning("Could not get button bounding box")
                    return False
                # Target slightly off-center (humans don't click exact center)
                x = box['x'] + box['width'] / 2 + random.gauss(0, 3)
                y = box['y'] + box['height'] / 2 + random.gauss(0, 3)
                self.logger.info(f"Using bounding box position: ({x:.0f}, {y:.0f})")

            # First, investigate what element is actually at this position
            self.logger.info(f"Investigating element at ({x:.0f}, {y:.0f})...")

            import time

            # Check for PerimeterX elements - this is their anti-bot system
            try:
                px_info = self.page.evaluate("""
                    (() => {
                        // Find all PerimeterX related elements
                        const pxElements = document.querySelectorAll('[class*="px-"]');
                        const results = [];
                        pxElements.forEach(el => {
                            results.push({
                                tag: el.tagName,
                                class: el.className,
                                rect: el.getBoundingClientRect(),
                                children: el.children.length,
                                innerHTML: el.innerHTML.substring(0, 300)
                            });
                        });

                        // Also look for PerimeterX iframes
                        const iframes = document.querySelectorAll('iframe[src*="px"], iframe[id*="px"]');
                        const iframeResults = [];
                        iframes.forEach(iframe => {
                            iframeResults.push({
                                id: iframe.id,
                                src: iframe.src,
                                rect: iframe.getBoundingClientRect()
                            });
                        });

                        return { pxElements: results, pxIframes: iframeResults };
                    })();
                """)
                self.logger.info(f"PerimeterX elements found: {len(px_info.get('pxElements', []))}")
                for px_el in px_info.get('pxElements', []):
                    self.logger.info(f"  PX element: {px_el['tag']} class='{px_el['class']}' rect={px_el['rect']}")
                for iframe in px_info.get('pxIframes', []):
                    self.logger.info(f"  PX iframe: id='{iframe['id']}' src='{iframe['src']}'")
            except Exception as e:
                self.logger.warning(f"PerimeterX investigation failed: {e}")

            try:
                # Get detailed info about element at position
                element_info = self.page.evaluate(f"""
                    (() => {{
                        const x = {x};
                        const y = {y};
                        const elem = document.elementFromPoint(x, y);
                        if (!elem) return {{ found: false }};

                        // Get computed styles
                        const styles = window.getComputedStyle(elem);

                        // Check for shadow root
                        let shadowInfo = null;
                        if (elem.shadowRoot) {{
                            shadowInfo = 'has shadowRoot';
                        }}

                        // Walk up to find any shadow hosts
                        let parent = elem;
                        let shadowHost = null;
                        while (parent) {{
                            if (parent.shadowRoot) {{
                                shadowHost = parent.tagName;
                                break;
                            }}
                            parent = parent.parentElement;
                        }}

                        return {{
                            found: true,
                            tagName: elem.tagName,
                            className: elem.className,
                            id: elem.id,
                            textContent: (elem.textContent || '').substring(0, 100),
                            innerHTML: (elem.innerHTML || '').substring(0, 200),
                            rect: elem.getBoundingClientRect(),
                            shadowInfo: shadowInfo,
                            shadowHost: shadowHost,
                            role: elem.getAttribute('role'),
                            ariaLabel: elem.getAttribute('aria-label'),
                            dataAttrs: Object.keys(elem.dataset || {{}}).join(', '),
                            cursor: styles.cursor,
                            pointerEvents: styles.pointerEvents
                        }};
                    }})();
                """)
                self.logger.info(f"Element at position: {element_info}")

                # Also check if there's a canvas or iframe
                canvas_check = self.page.evaluate(f"""
                    (() => {{
                        const x = {x};
                        const y = {y};
                        const elem = document.elementFromPoint(x, y);

                        // Check parents for canvas or iframe
                        let current = elem;
                        while (current) {{
                            if (current.tagName === 'CANVAS') return {{ type: 'canvas', elem: current.outerHTML.substring(0, 200) }};
                            if (current.tagName === 'IFRAME') return {{ type: 'iframe', src: current.src }};
                            current = current.parentElement;
                        }}
                        return {{ type: 'none' }};
                    }})();
                """)
                self.logger.info(f"Canvas/iframe check: {canvas_check}")

            except Exception as e:
                self.logger.warning(f"Element investigation failed: {e}")

            # The button is rendered by PerimeterX JS - try interacting with PX elements directly
            self.logger.info("Attempting to interact with PerimeterX elements...")

            hold_success = False
            try:
                # Try to click directly on the px-loading-area with force
                px_loading = self.page.locator('.px-loading-area, .px-inner-loading-area, #px-captcha').first
                if px_loading.is_visible(timeout=2000):
                    self.logger.info("Found PX loading area, attempting forced click with delay...")

                    # Get the bounding box of the PX element
                    px_box = px_loading.bounding_box()
                    if px_box:
                        # Calculate center of PX element
                        px_x = px_box['x'] + px_box['width'] / 2
                        px_y = px_box['y'] + px_box['height'] / 2
                        self.logger.info(f"PX element center: ({px_x:.0f}, {px_y:.0f})")

                        # Use dispatchEvent to trigger pointer events directly on the element
                        self.logger.info("Dispatching pointer events directly on PX element...")
                        self.page.evaluate(f"""
                            (async () => {{
                                const x = {px_x};
                                const y = {px_y};
                                const elem = document.elementFromPoint(x, y);
                                if (!elem) return;

                                console.log('Target element:', elem);

                                // Create and dispatch pointerdown event
                                const pointerDown = new PointerEvent('pointerdown', {{
                                    bubbles: true,
                                    cancelable: true,
                                    pointerId: 1,
                                    pointerType: 'mouse',
                                    isPrimary: true,
                                    clientX: x,
                                    clientY: y,
                                    screenX: x,
                                    screenY: y,
                                    pressure: 0.5,
                                    button: 0,
                                    buttons: 1
                                }});
                                elem.dispatchEvent(pointerDown);

                                // Also dispatch mousedown for compatibility
                                const mouseDown = new MouseEvent('mousedown', {{
                                    bubbles: true,
                                    cancelable: true,
                                    clientX: x,
                                    clientY: y,
                                    button: 0,
                                    buttons: 1
                                }});
                                elem.dispatchEvent(mouseDown);
                            }})();
                        """)

                        # Hold for duration
                        self.logger.info("Holding for 8 seconds...")
                        time.sleep(8.0)

                        # Release
                        self.page.evaluate(f"""
                            (async () => {{
                                const x = {px_x};
                                const y = {px_y};
                                const elem = document.elementFromPoint(x, y);
                                if (!elem) return;

                                // Dispatch pointerup
                                const pointerUp = new PointerEvent('pointerup', {{
                                    bubbles: true,
                                    cancelable: true,
                                    pointerId: 1,
                                    pointerType: 'mouse',
                                    isPrimary: true,
                                    clientX: x,
                                    clientY: y,
                                    pressure: 0,
                                    button: 0,
                                    buttons: 0
                                }});
                                elem.dispatchEvent(pointerUp);

                                // Also dispatch mouseup
                                const mouseUp = new MouseEvent('mouseup', {{
                                    bubbles: true,
                                    cancelable: true,
                                    clientX: x,
                                    clientY: y,
                                    button: 0,
                                    buttons: 0
                                }});
                                elem.dispatchEvent(mouseUp);
                            }})();
                        """)
                        self.logger.info("Pointer events dispatched")
                        hold_success = True

            except Exception as e:
                self.logger.warning(f"PerimeterX element interaction failed: {e}")

            # Try xdotool for real X11 input (most reliable for anti-bot bypass)
            import subprocess
            import os

            xdotool_success = False
            display = os.environ.get('DISPLAY')

            if display:
                self.logger.info(f"Attempting xdotool on DISPLAY={display}...")
                try:
                    # Get the browser window ID
                    result = subprocess.run(
                        ['xdotool', 'search', '--name', 'Chrom'],
                        capture_output=True, text=True, timeout=5
                    )
                    window_ids = result.stdout.strip().split('\n')
                    if window_ids and window_ids[0]:
                        window_id = window_ids[0]
                        self.logger.info(f"Found browser window: {window_id}")

                        # Get window position
                        pos_result = subprocess.run(
                            ['xdotool', 'getwindowgeometry', window_id],
                            capture_output=True, text=True, timeout=5
                        )
                        self.logger.info(f"Window geometry: {pos_result.stdout}")

                        # Calculate absolute screen position
                        # The viewport coordinates need to be adjusted for window position
                        abs_x = int(x)
                        abs_y = int(y)

                        # Move mouse to position
                        subprocess.run(['xdotool', 'mousemove', '--window', window_id, str(abs_x), str(abs_y)], timeout=5)
                        time.sleep(0.1)

                        # Mouse down
                        subprocess.run(['xdotool', 'mousedown', '1'], timeout=5)
                        self.logger.info(f"xdotool mousedown at ({abs_x}, {abs_y}), holding for 8 seconds...")

                        # Hold
                        time.sleep(8.0)

                        # Mouse up
                        subprocess.run(['xdotool', 'mouseup', '1'], timeout=5)
                        self.logger.info("xdotool mouse hold completed")
                        xdotool_success = True

                except Exception as e:
                    self.logger.warning(f"xdotool failed: {e}")

            # Fallback to CDP touch events if xdotool didn't work
            if not xdotool_success:
                self.logger.info("Attempting CDP touch events...")
                try:
                    cdp = self.page.context.new_cdp_session(self.page)

                    # Touch start at calculated position
                    cdp.send("Input.dispatchTouchEvent", {
                        "type": "touchStart",
                        "touchPoints": [{
                            "x": int(x),
                            "y": int(y),
                            "id": 1,
                            "radiusX": 10,
                            "radiusY": 10,
                            "force": 0.5
                        }]
                    })
                    self.logger.info(f"CDP touch start at ({x:.0f}, {y:.0f}), holding for 8 seconds...")

                    # Hold for 8 seconds
                    time.sleep(8.0)

                    # Touch end
                    cdp.send("Input.dispatchTouchEvent", {
                        "type": "touchEnd",
                        "touchPoints": []
                    })
                    self.logger.info("CDP touch hold completed")

                except Exception as e:
                    self.logger.warning(f"CDP touch events failed: {e}")
                    # Final fallback to standard click
                    self.page.mouse.click(x, y, delay=8000)

            # Wait for the challenge to process with randomized timing
            human_sleep(2.0, 0.3)

            # Wait for result with human-like timing
            human_sleep(2.0, 0.4)
            self._wait_for_page()

            # Check if modal is gone (check all language variants + translation keys)
            modal_gone = True
            modal_checks = [
                '*:has-text("Before we continue")',
                '*:has-text("Prima di continuare")',  # Italian
                '*:has-text("Antes de continuar")',   # Spanish
                '[role="dialog"]:has-text("Tieni premuto")',
                '[role="dialog"]:has-text("Press & hold")',
                # Translation key patterns
                '*:has-text("global.captcha.perimeterx")',
                '#px-captcha',  # PerimeterX container
            ]
            for check in modal_checks:
                try:
                    modal = self.page.locator(check).first
                    if modal.is_visible(timeout=1500):
                        modal_gone = False
                        self.logger.debug(f"Modal still visible: {check}")
                        break
                except Exception:
                    continue

            if modal_gone:
                self.logger.info("Press & hold challenge passed!")
                return True

            # Modal still visible - try clicking/holding again or wait longer
            self.logger.warning("Press & hold modal still visible, waiting longer...")
            human_sleep(3.0, 0.5)
            self._wait_for_page()

            # Check again
            for check in modal_checks:
                try:
                    modal = self.page.locator(check).first
                    if modal.is_visible(timeout=1500):
                        self.logger.warning("Press & hold may not have worked - modal still visible")
                        self.screenshot("press_hold_result")
                        return False  # Return False to indicate failure
                except Exception:
                    continue

            self.logger.info("Press & hold challenge passed after extended wait!")
            return True

        except Exception as e:
            self.logger.error(f"Error during press & hold: {e}")
            return False

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
        self.logger.info("Checking for popups to dismiss...")

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
                    self.logger.info(f"Found popup: {description}, dismissing...")
                    button.click()
                    human_sleep(0.3, 0.4)  # Randomized wait after dismissing
                    dismissed_count += 1
            except Exception:
                continue

        if dismissed_count > 0:
            self.logger.info(f"Dismissed {dismissed_count} popup(s)")
        else:
            self.logger.info("No popups found")

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
            self.logger.info("Looking for email input...")
            email_input = self.page.locator(self.SELECTORS["email_input"]).first
            email_input.wait_for(timeout=10000)

            # Click and type with human-like behavior
            human_type(self.page, self.SELECTORS["email_input"], self.email)
            self.logger.info("Email entered with human-like typing")

            # Brief pause before moving to password (humans look at screen)
            human_sleep(0.4, 0.4)

            # Look for password input
            self.logger.info("Looking for password input...")
            password_input = self.page.locator(self.SELECTORS["password_input"]).first
            password_input.wait_for(timeout=5000)

            # Type password with human-like behavior
            human_type(self.page, self.SELECTORS["password_input"], self.password)
            self.logger.info("Password entered with human-like typing")

            self.screenshot("02_credentials_entered")

            # Brief pause before clicking login (humans review before submitting)
            human_sleep(0.3, 0.3)

            # Click login button with human-like behavior
            self.logger.info("Clicking login button...")
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
                    self.logger.info(f"Found Order History link: {description}")
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
        self.logger.info("Looking for 'Scarica il report' button...")

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
                    self.logger.info(f"Found download button: {selector}")
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
                    self.logger.info(f"Selecting CSV format: {selector}")
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
                            self.logger.info(f"Clicking confirm: {selector}")
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
