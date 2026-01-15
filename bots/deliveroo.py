"""Deliveroo Partner Hub bot for downloading invoices."""

import re
import time
from datetime import datetime
from typing import List, Optional
from pathlib import Path
from urllib.parse import urlparse, parse_qs, urlencode

from patchright.sync_api import TimeoutError as PlaywrightTimeout

from .base import BaseBot, DownloadedInvoice


class DeliverooBot(BaseBot):
    """Bot for downloading invoices from Deliveroo Partner Hub."""

    PLATFORM_NAME = "deliveroo"
    LOGIN_URL = "https://partner-hub.deliveroo.com/"
    INVOICES_URL = "https://partner-hub.deliveroo.com/reports/invoices"

    # Selectors
    SELECTORS = {
        # Login page
        "email_input": 'input[type="email"], input[name="email"], #email',
        "password_input": 'input[type="password"], input[name="password"], #password',
        "login_button": 'button[type="submit"], button:has-text("Log in"), button:has-text("Sign in")',

        # Navigation
        "invoices_sidebar": 'a:has-text("Invoices"), a:has-text("Fatture"), nav a[href*="invoice"]',

        # Invoice table
        "invoice_table": 'table',
        "invoice_row": 'table tbody tr',

        # CSV download in Sintesi column
        "csv_link": 'a:has-text("CSV")',

        # Pagination
        "next_page": 'button:has-text("Next"), a:has-text("Next"), [aria-label="Next page"], button:has-text("Avanti")',
        "prev_page": 'button:has-text("Previous"), a:has-text("Previous"), button:has-text("Indietro")',
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.org_id = None  # Will be extracted from URL after login
        self.locations_cache = []  # Cache of discovered locations/branches

    def _wait_for_cloudflare(self, timeout_seconds: int = 60) -> bool:
        """
        Wait for Cloudflare challenge to auto-resolve.

        Patchright's stealth features usually pass after waiting.
        Returns True if challenge resolved, False otherwise.
        """
        challenge_indicators = [
            "Verify you are human",
            "Just a moment",
            "Checking your browser",
            "challenge-platform",
        ]

        self.logger.info(f"Waiting up to {timeout_seconds}s for Cloudflare to pass...")

        for attempt in range(timeout_seconds // 2):
            time.sleep(2)
            content = self.page.content()

            if not any(indicator in content for indicator in challenge_indicators):
                self.logger.info("Cloudflare challenge passed!")
                return True

            if attempt % 5 == 0:
                self.logger.info(f"Still waiting for Cloudflare... ({attempt * 2}s)")

        self.logger.warning("Cloudflare challenge did not resolve in time")
        return False

    def _extract_org_id(self):
        """Extract orgId from current URL."""
        try:
            parsed = urlparse(self.page.url)
            params = parse_qs(parsed.query)
            if 'orgId' in params:
                self.org_id = params['orgId'][0]
                self.logger.info(f"Extracted orgId: {self.org_id}")
        except Exception as e:
            self.logger.warning(f"Could not extract orgId: {e}")

    def _dismiss_popups(self):
        """Dismiss Deliveroo-specific popups (announcements, surveys, modals)."""
        self.logger.info("Checking for popups to dismiss...")

        # First: Handle DAC7 tax compliance popup (has no close button)
        try:
            dac7_visible = self.page.locator('text="DAC7 information required"').is_visible(timeout=1000)
            if dac7_visible:
                self.logger.info("Found DAC7 popup, pressing Escape to dismiss...")
                self.page.keyboard.press("Escape")
                time.sleep(0.5)
                # If still visible, try clicking outside
                if self.page.locator('text="DAC7 information required"').is_visible(timeout=500):
                    self.page.mouse.click(10, 10)
                    time.sleep(0.3)
        except Exception:
            pass

        # List of popup close actions to try
        popup_selectors = [
            # "What's new?" modal - X button in top right
            ('button[aria-label="Close"]', "What's new modal"),
            ('button[aria-label="Chiudi"]', "What's new modal (IT)"),
            ('[data-testid="modal-close"]', "Modal close button"),
            ('.modal-close', "Modal close"),

            # "We've renamed Hub" announcement - just close it
            ('button:has-text("Got it")', "Got it button"),
            ('button:has-text("Capito")', "Capito button"),
            ('button:has-text("OK")', "OK button"),
            ('button:has-text("Dismiss")', "Dismiss button"),

            # NPS survey popup (bottom of page)
            ('button:has-text("Close")', "Close button"),
            ('button:has-text("Chiudi")', "Chiudi button"),
            ('[aria-label="Close survey"]', "Survey close"),
            ('[data-testid="nps-close"]', "NPS close"),
            ('[data-testid="survey-close"]', "Survey close"),
            ('[class*="nps"] button[aria-label="Close"]', "NPS close button"),
            ('[class*="survey"] button[aria-label="Close"]', "Survey close button"),
            ('[class*="feedback"] button[aria-label="Close"]', "Feedback close"),
            ('button:has-text("No thanks")', "No thanks button"),
            ('button:has-text("No grazie")', "No grazie button"),
            ('button:has-text("Maybe later")', "Maybe later button"),
            ('button:has-text("Not now")', "Not now button"),
            ('button:has-text("Skip")', "Skip button"),

            # Generic modal/dialog close buttons
            ('[role="dialog"] button[aria-label="Close"]', "Dialog close"),
            ('.modal button:has-text("×")', "Modal X button"),
            ('button:has-text("×")', "X button"),
            ('button:has-text("✕")', "Close symbol"),

            # Bottom survey/feedback widget
            ('iframe[title*="survey"]', "Survey iframe - will try to close parent"),
            ('[class*="widget"] button:has-text("Close")', "Widget close"),

            # Medallia NPS survey (bottom popup)
            ('button:has-text("Close")', "Close button"),
            ('[aria-label="close"]', "aria close"),
        ]

        dismissed_count = 0
        for selector, description in popup_selectors:
            try:
                button = self.page.locator(selector).first
                if button.is_visible(timeout=500):
                    self.logger.info(f"Found popup: {description}, dismissing...")
                    button.click()
                    time.sleep(0.3)
                    dismissed_count += 1
            except Exception:
                continue

        if dismissed_count > 0:
            self.logger.info(f"Dismissed {dismissed_count} popup(s)")
        else:
            self.logger.info("No popups found")

    def _wait_for_page(self, timeout: int = 10000):
        """Wait for page to be ready (using domcontentloaded, not networkidle)."""
        try:
            self.page.wait_for_load_state("domcontentloaded", timeout=timeout)
            time.sleep(1)  # Extra wait for JS rendering
        except Exception:
            pass

    def _is_logged_in(self) -> bool:
        """Check if we're already logged in based on URL or page content."""
        current_url = self.page.url

        # First check: if URL contains "/login" → definitely NOT logged in
        if "/login" in current_url:
            return False

        # Check URL patterns that indicate logged-in state
        logged_in_patterns = ["/home", "/analytics", "/invoices", "/reports", "/dashboard"]
        if any(pattern in current_url for pattern in logged_in_patterns):
            return True

        # Check if sidebar with Invoices link is visible
        try:
            invoices_link = self.page.locator(self.SELECTORS["invoices_sidebar"]).first
            if invoices_link.is_visible(timeout=2000):
                return True
        except Exception:
            pass

        return False

    def _handle_cloudflare_interstitial(self) -> bool:
        """
        Handle Cloudflare interstitial challenge page.
        Returns True if challenge was handled, False if no challenge found.
        """
        page_content = self.page.content()

        # Check if we're on a Cloudflare challenge page
        challenge_indicators = [
            "Verify you are human",
            "Just a moment",
            "Checking your browser",
            "challenge-platform",
        ]
        if not any(indicator in page_content for indicator in challenge_indicators):
            return False

        self.logger.info("Cloudflare challenge detected, waiting for it to pass...")

        # Patchright's stealth mode usually passes Cloudflare after waiting
        # No need for CAPTCHA solvers - just wait
        return self._wait_for_cloudflare(timeout_seconds=90)

    def login(self) -> bool:
        """Log into Deliveroo Partner Hub."""
        self.logger.info(f"Navigating to {self.LOGIN_URL}")
        self.page.goto(self.LOGIN_URL)

        # Wait for page (use domcontentloaded to avoid timeout)
        self._wait_for_page()

        # Handle Cloudflare interstitial challenge if present
        if self._handle_cloudflare_interstitial():
            self._wait_for_page()

        # Dismiss cookie consent popup if present
        self.dismiss_cookie_consent()

        # Dismiss any Deliveroo-specific popups
        self._dismiss_popups()

        # Check if already logged in (from saved session)
        if self._is_logged_in():
            self.logger.info(f"Already logged in (URL: {self.page.url}), skipping login")
            self._extract_org_id()
            self.screenshot("01_already_logged_in")
            return True

        # Take a screenshot
        self.screenshot("01_login_page")

        try:
            # Try to find and fill email
            self.logger.info("Looking for email input...")
            email_input = self.page.locator(self.SELECTORS["email_input"]).first
            email_input.wait_for(timeout=10000)
            email_input.click()
            time.sleep(0.3)
            email_input.fill(self.email)
            self.logger.info("Email entered")

            # Look for password input
            self.logger.info("Looking for password input...")
            password_input = self.page.locator(self.SELECTORS["password_input"]).first
            password_input.wait_for(timeout=5000)
            password_input.click()
            time.sleep(0.3)
            password_input.fill(self.password)
            self.logger.info("Password entered")

            # Click login button
            self.logger.info("Clicking login button...")
            login_button = self.page.locator(self.SELECTORS["login_button"]).first
            login_button.click()

            # Wait for navigation after login
            self._wait_for_page()
            time.sleep(2)  # Extra wait for any redirects

            # Dismiss post-login popups
            self._dismiss_popups()

            current_url = self.page.url
            self.logger.info(f"Current URL after login: {current_url}")

            # Extract orgId from URL
            self._extract_org_id()

            self.screenshot("02_after_login")

            # Check if login was successful
            if self._is_logged_in():
                self.logger.info("Login successful!")
                return True

            # Check for error messages
            error_locator = self.page.locator('.error, .alert-danger, [role="alert"]')
            if error_locator.count() > 0:
                error_text = error_locator.first.text_content()
                self.logger.error(f"Login error: {error_text}")
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

    def _navigate_to_invoices(self) -> bool:
        """Navigate to the invoices page and select Synthesis tab."""
        self.logger.info("Navigating to invoices page...")

        # Dismiss any popups first
        self._dismiss_popups()

        # Try clicking the sidebar link first
        try:
            invoices_link = self.page.locator(self.SELECTORS["invoices_sidebar"]).first
            if invoices_link.is_visible(timeout=3000):
                self.logger.info("Found invoices link in sidebar, clicking...")
                invoices_link.click()
                self._wait_for_page()
                self._dismiss_popups()
                self._extract_org_id()  # Extract orgId from URL after navigation
                self.screenshot("03_invoices_page")
        except Exception as e:
            self.logger.info(f"Sidebar link not found: {e}")
            # Fall back to direct URL (with orgId if available)
            invoices_url = self.INVOICES_URL
            if self.org_id:
                invoices_url = f"{self.INVOICES_URL}?orgId={self.org_id}"

            self.logger.info(f"Navigating directly to {invoices_url}")
            self.page.goto(invoices_url)
            self._wait_for_page()
            self._dismiss_popups()
            self.screenshot("03_invoices_page")

        # Now click on "Synthesis" / "Statement" / "Sintesi" tab
        self.logger.info("Looking for Synthesis/Statement tab...")
        synthesis_selectors = [
            'button:has-text("Synthesis")',
            'button:has-text("Statement")',
            'button:has-text("Sintesi")',
            'a:has-text("Synthesis")',
            'a:has-text("Statement")',
            'a:has-text("Sintesi")',
            '[role="tab"]:has-text("Synthesis")',
            '[role="tab"]:has-text("Statement")',
            '[role="tab"]:has-text("Sintesi")',
            # Also try partial matches
            '*:has-text("Synthesis")',
            '*:has-text("Sintesi")',
        ]

        for selector in synthesis_selectors:
            try:
                tab = self.page.locator(selector).first
                if tab.is_visible(timeout=2000):
                    self.logger.info(f"Found Synthesis tab: {selector}")
                    tab.click()
                    self._wait_for_page()
                    time.sleep(1)  # Wait for tab content to load
                    self._dismiss_popups()
                    self.screenshot("03b_synthesis_tab")
                    break
            except Exception:
                continue

        # Check if we're on the invoices page
        if "invoice" in self.page.url.lower() or "reports" in self.page.url.lower():
            self.logger.info("Successfully navigated to invoices page")
            self._extract_org_id()  # Extract orgId if not already set
            return True

        self.logger.error("Failed to navigate to invoices page")
        return False

    def get_locations(self) -> List[dict]:
        """Get list of all locations/restaurants (branches) for the account.

        Deliveroo Partner Hub shows a "Filter Sites" modal when clicking the store selector.
        The modal contains radio buttons for each business/location.
        """
        if self.locations_cache:
            return self.locations_cache

        locations = []

        try:
            # First, force dismiss any blocking modals (DAC7, etc.)
            self._dismiss_popups()

            # Force remove any remaining modal overlays via JS
            try:
                self.page.evaluate("""
                    document.querySelectorAll('.ReactModalPortal').forEach(el => el.innerHTML = '');
                """)
                time.sleep(0.5)
            except Exception:
                pass

            # Click the store selector button using data-testid (most reliable)
            branch_trigger_selectors = [
                '[data-testid="pillButtonSiteSelection"]',
                'button:has-text("Poke House")',
                'button:has-text("store")',
            ]

            modal_opened = False
            for selector in branch_trigger_selectors:
                try:
                    trigger = self.page.locator(selector).first
                    if trigger.is_visible(timeout=2000):
                        trigger_text = trigger.text_content().strip()[:50]
                        self.logger.info(f"Found store selector: '{trigger_text}'")
                        # Use force=True to bypass any intercepting elements
                        trigger.click(force=True)
                        time.sleep(2)  # Wait for modal animation
                        modal_opened = True
                        break
                except Exception:
                    continue

            if modal_opened:
                # Look for the "Filter Sites" modal using data-testid
                modal_selectors = [
                    '[data-testid="siteSelectionModal"]',
                    '[class*="Modal"]:has-text("Businesses")',
                    '[class*="Modal"]:has-text("Filter Sites")',
                ]

                modal = None
                for selector in modal_selectors:
                    try:
                        m = self.page.locator(selector).first
                        if m.is_visible(timeout=2000):
                            modal = m
                            self.logger.info(f"Found Filter Sites modal")
                            break
                    except Exception:
                        continue

                if modal:
                    # Find all radio button options within the modal
                    # Each option is a clickable element with the business name
                    option_selectors = [
                        # Radio button labels (most common pattern)
                        'label:has(input[type="radio"])',
                        'label:has([role="radio"])',
                        # Material-UI style radio groups
                        '[class*="Radio"] label',
                        '[class*="FormControlLabel"]',
                        # Generic clickable items in the list
                        '[class*="ListItem"]:has([type="radio"])',
                        # Direct radio inputs with adjacent text
                        'input[type="radio"]',
                    ]

                    for option_selector in option_selectors:
                        try:
                            options = modal.locator(option_selector).all()
                            if options and len(options) >= 1:
                                self.logger.info(f"Found {len(options)} business options")
                                for i, option in enumerate(options):
                                    try:
                                        # Get the business name
                                        if option_selector == 'input[type="radio"]':
                                            # For radio inputs, get the label text
                                            name = option.evaluate("""el => {
                                                // Try to find associated label
                                                if (el.labels && el.labels[0]) return el.labels[0].textContent;
                                                // Try parent label
                                                let label = el.closest('label');
                                                if (label) return label.textContent;
                                                // Try next sibling
                                                let next = el.nextElementSibling;
                                                if (next) return next.textContent;
                                                // Try parent's text
                                                return el.parentElement?.textContent || '';
                                            }""")
                                        else:
                                            name = option.text_content()

                                        name = name.strip() if name else ""

                                        # Skip empty or control items
                                        if not name or name.lower() in ['', 'select', 'cancel', 'close', 'businesses:']:
                                            continue

                                        # Try to get value/id from the radio input
                                        branch_id = None
                                        try:
                                            if option_selector == 'input[type="radio"]':
                                                branch_id = option.get_attribute('value')
                                            else:
                                                radio_input = option.locator('input[type="radio"]').first
                                                branch_id = radio_input.get_attribute('value')
                                        except Exception:
                                            pass

                                        if not branch_id:
                                            branch_id = f"business_{i}"

                                        locations.append({
                                            "id": branch_id,
                                            "name": name,
                                            "index": i,
                                        })
                                        self.logger.info(f"  Business {len(locations)}: {name}")
                                    except Exception as e:
                                        self.logger.debug(f"Error extracting business: {e}")

                                if locations:
                                    break
                        except Exception:
                            continue

                # Close the modal
                try:
                    # Try Cancel button first
                    cancel_btn = self.page.locator('button:has-text("Cancel")').first
                    if cancel_btn.is_visible(timeout=500):
                        cancel_btn.click()
                    else:
                        # Fall back to Escape key or X button
                        close_btn = self.page.locator('[class*="Modal"] button:has-text("close"), [class*="Modal"] button[aria-label="Close"]').first
                        if close_btn.is_visible(timeout=500):
                            close_btn.click()
                        else:
                            self.page.keyboard.press("Escape")
                    time.sleep(0.5)
                except Exception:
                    pass

            # Fallback: URL-based detection if modal didn't work
            if not locations:
                self.logger.info("No businesses found in modal, trying URL-based detection...")

                current_url = self.page.url
                parsed = urlparse(current_url)
                params = parse_qs(parsed.query)

                branch_id = params.get('branchId', [None])[0]
                org_id = params.get('orgId', [None])[0]

                if branch_id:
                    branch_name = "Default Location"
                    try:
                        header_text = self.page.locator('header').first.text_content()
                        if header_text:
                            branch_name = header_text.split('\n')[0].strip()[:50] or "Default Location"
                    except Exception:
                        pass

                    locations.append({
                        "id": branch_id,
                        "name": branch_name,
                        "org_id": org_id,
                    })
                    self.logger.info(f"Detected from URL: {branch_name} (branchId: {branch_id})")

            if not locations:
                self.logger.warning("Could not detect businesses, using default")
                locations.append({"id": "default", "name": "Default Location"})

        except Exception as e:
            self.logger.error(f"Error getting locations: {e}")
            locations.append({"id": "default", "name": "Default Location"})

        self.locations_cache = locations
        return locations

    def _switch_to_branch(self, branch_id: str, branch_name: str = None) -> bool:
        """Switch to a specific business/location using the Filter Sites modal.

        Args:
            branch_id: The business/org ID to switch to
            branch_name: Optional business name for logging

        Returns:
            True if switch was successful, False otherwise
        """
        if branch_id == "default":
            return True  # No switch needed

        self.logger.info(f"Switching to business: {branch_name or branch_id}")

        try:
            # Navigate to main dashboard first - the store selector is not visible on all pages
            self.page.goto("https://partner-hub.deliveroo.com/")
            self._wait_for_page()
            self._dismiss_popups()

            # Open the store selector modal
            trigger_selectors = [
                'button:has-text("store")',
                'button:has-text("DISABLED")',
            ]

            modal_opened = False
            for selector in trigger_selectors:
                try:
                    trigger = self.page.locator(selector).first
                    if trigger.is_visible(timeout=2000):
                        trigger.click()
                        time.sleep(1.5)
                        modal_opened = True
                        break
                except Exception:
                    continue

            if not modal_opened:
                self.logger.warning("Could not open store selector modal")
                return False

            # Find and click the radio button for this business
            # Try by value attribute first (the business ID)
            radio_clicked = False

            try:
                radio = self.page.locator(f'input[type="radio"][value="{branch_id}"]').first
                if radio.is_visible(timeout=1000):
                    radio.click()
                    radio_clicked = True
                    self.logger.info(f"Clicked radio button with value={branch_id}")
            except Exception:
                pass

            # If not found by value, try by label text
            if not radio_clicked and branch_name:
                try:
                    # Find label containing the business name and click its radio
                    label = self.page.locator(f'label:has-text("{branch_name}")').first
                    if label.is_visible(timeout=1000):
                        label.click()
                        radio_clicked = True
                        self.logger.info(f"Clicked label for {branch_name}")
                except Exception:
                    pass

            if not radio_clicked:
                self.logger.warning(f"Could not find radio button for {branch_name or branch_id}")
                # Close modal and return
                self.page.keyboard.press("Escape")
                time.sleep(0.5)
                return False

            # Click the Select button to confirm selection
            time.sleep(0.5)
            apply_selectors = [
                'button:has-text("Select")',
                'button:has-text("Apply")',
                'button:has-text("Filter")',
                'button:has-text("Confirm")',
                'button[type="submit"]',
            ]

            applied = False
            for selector in apply_selectors:
                try:
                    btn = self.page.locator(selector).first
                    if btn.is_visible(timeout=500):
                        btn.click()
                        applied = True
                        self.logger.info("Applied business filter")
                        break
                except Exception:
                    continue

            if not applied:
                # If no apply button, the radio click might auto-apply
                # Try closing modal with Escape
                self.page.keyboard.press("Escape")

            self._wait_for_page()
            self._dismiss_popups()

            self.logger.info(f"Successfully switched to {branch_name or branch_id}")
            return True

        except Exception as e:
            self.logger.error(f"Error switching business: {e}")
            return False

    def _wait_for_invoices_to_load(self, timeout: int = 15) -> bool:
        """Wait for the invoice table to have data (not 'No items to display')."""
        self.logger.info("Waiting for invoices to load...")

        for attempt in range(timeout):
            # First dismiss any popups that might block
            self._dismiss_popups()

            # Check if "No items to display" is visible
            no_items = self.page.locator('text="No items to display"')
            if no_items.count() == 0:
                # Check if we have actual invoice rows
                csv_links = self.page.locator('a:has-text("CSV")').all()
                if csv_links:
                    self.logger.info(f"Invoices loaded! Found {len(csv_links)} CSV links")
                    return True

            time.sleep(1)
            self.logger.info(f"Waiting for invoices... (attempt {attempt + 1}/{timeout})")

        self.logger.warning("Invoices did not load within timeout")
        return False

    def _get_all_csv_links(self) -> list:
        """Get all CSV download links from the current page."""
        try:
            # Wait for invoices to load first
            self._wait_for_invoices_to_load()

            # Try multiple selectors to find CSV links
            csv_selectors = [
                'a:has-text("CSV")',
                'button:has-text("CSV")',
                '[href*=".csv"]',
                '[data-testid*="csv"]',
                'a[download*=".csv"]',
            ]

            for selector in csv_selectors:
                links = self.page.locator(selector).all()
                if links:
                    self.logger.info(f"Found {len(links)} CSV links using selector: {selector}")
                    return links

            self.logger.warning("No CSV links found on page")
            return []

        except Exception as e:
            self.logger.error(f"Error getting CSV links: {e}")
            return []

    def _extract_invoice_info_from_link(self, csv_link) -> dict:
        """Extract invoice information from the context around a CSV link."""
        info = {
            "invoice_number": None,
            "period": None,
            "due_date": None,
            "total": None,
        }

        try:
            # Deliveroo uses custom div-based table with classes like tcl__TableRow-*
            # Try multiple approaches to get the parent row
            text = csv_link.evaluate("""el => {
                // Approach 1: Look for Deliveroo's custom TableRow class
                let row = el.closest('div[class*="TableRow"]');
                if (row) return row.textContent;

                // Approach 2: Standard tr
                row = el.closest('tr');
                if (row) return row.textContent;

                // Approach 3: Any element with role="row"
                row = el.closest('[role="row"]');
                if (row) return row.textContent;

                // Approach 4: Walk up 4-5 levels to get broader context
                let current = el;
                for (let i = 0; i < 5 && current; i++) {
                    current = current.parentElement;
                }
                return current ? current.textContent : '';
            }""")

            if text:
                # Extract invoice number (various patterns: res-it-XXX, Fattura n° XXX, Invoice #XXX)
                invoice_match = re.search(r'(res-[a-z]{2}-\d+|(?:Fattura\s*n[°º]?\s*|Invoice\s*#?\s*)(\d+))', text, re.IGNORECASE)
                if invoice_match:
                    info["invoice_number"] = invoice_match.group(1) if invoice_match.group(1).startswith("res-") else invoice_match.group(2)

                # Extract date patterns (various formats used by Deliveroo)
                date_patterns = [
                    r'\d{1,2}/\d{1,2}/\d{4}',           # 14/01/2024
                    r'\d{1,2}-\d{1,2}-\d{4}',           # 14-01-2024
                    r'\d{1,2}\.\d{1,2}\.\d{4}',         # 14.01.2024
                    r'\d{4}-\d{2}-\d{2}',               # 2024-01-14
                    r'\d{1,2}\s+\w+\s+\d{4}',           # 14 January 2024
                    r'\w+\s+\d{1,2},?\s+\d{4}',         # January 14, 2024
                    r'\d{1,2}\s+\w{3}\s+\d{4}',         # 14 Jan 2024
                    r'\d{1,2}\s+\w{3}\s+\d{2}',         # 14 Jan 24
                ]
                combined_pattern = '|'.join(f'({p})' for p in date_patterns)
                date_matches = re.findall(combined_pattern, text, re.IGNORECASE)

                if date_matches:
                    # Flatten the tuple results and filter empty strings
                    flat_dates = [d for match in date_matches for d in match if d]
                    if flat_dates:
                        info["period"] = flat_dates[0]
                        if len(flat_dates) > 1:
                            info["due_date"] = flat_dates[1]
                        self.logger.debug(f"Extracted dates: {flat_dates} from row")

                # Extract amount
                amount_match = re.search(r'[€£$]\s*-?[\d.,]+', text)
                if amount_match:
                    info["total"] = amount_match.group(0)
            else:
                self.logger.debug("No text content found in invoice row")

        except Exception as e:
            self.logger.debug(f"Error extracting invoice info: {e}")

        return info

    def _download_csv(self, csv_link, index: int) -> Optional[Path]:
        """Download CSV using Playwright's request context (shares browser cookies)."""
        try:
            self.logger.info(f"Downloading CSV #{index+1}...")

            # Get the href URL
            href = csv_link.get_attribute("href") or ""
            self.logger.info(f"CSV URL: {href[:80]}...")

            # Extract invoice ID for filename
            invoice_id = None
            invoice_match = re.search(r'/invoices/(\d+)/', href)
            if invoice_match:
                invoice_id = invoice_match.group(1)

            # Make absolute URL
            if href.startswith("/"):
                full_url = f"https://partner-hub.deliveroo.com{href}"
            else:
                full_url = href

            # Use Playwright's request context which shares cookies with browser
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

                    # Verify it looks like CSV
                    if content and len(content) > 100:
                        lines = content.strip().split('\n')
                        if len(lines) >= 2 and ',' in lines[0]:
                            # Save the content
                            if invoice_id:
                                filename = f"deliveroo_statement_{invoice_id}.csv"
                            else:
                                filename = f"invoice_{index+1}.csv"

                            save_path = self.downloads_dir / filename

                            with open(save_path, "w", encoding="utf-8") as f:
                                f.write(content)

                            self.logger.info(f"Downloaded: {save_path.name} ({len(content)} bytes)")
                            return save_path
                        else:
                            self.logger.warning(f"Content doesn't look like CSV for #{index+1}")
                    else:
                        self.logger.warning(f"No/empty content for #{index+1}")
                else:
                    self.logger.warning(f"Request failed for #{index+1}: HTTP {response.status}")

            except Exception as e:
                self.logger.warning(f"Request context failed for #{index+1}: {e}")

            # Fallback: Try clicking the link with download attribute
            self.logger.info(f"Trying click-based download for #{index+1}...")
            try:
                # Set download attribute to force download
                csv_link.evaluate('el => el.setAttribute("download", "")')

                with self.page.expect_download(timeout=15000) as download_info:
                    csv_link.click()

                download = download_info.value

                if invoice_id:
                    filename = f"deliveroo_statement_{invoice_id}.csv"
                else:
                    filename = download.suggested_filename or f"invoice_{index+1}.csv"

                save_path = self.downloads_dir / filename
                download.save_as(save_path)

                self.logger.info(f"Downloaded via click: {save_path.name}")
                return save_path

            except PlaywrightTimeout:
                self.logger.warning(f"Click download also timed out for #{index+1}")

            return None

        except Exception as e:
            self.logger.error(f"Error downloading CSV #{index+1}: {e}")

        return None

    def _is_invoice_downloaded(self, invoice_info: dict) -> Optional[str]:
        """Check if an invoice is already downloaded by matching date in filename.

        Filenames are like: ROSTICCERIA_PALAZZI_SRL_20240311_statement.csv
        Returns the filename if found, None otherwise.
        """
        period = invoice_info.get("period")
        if not period:
            return None

        # Convert period (e.g. "11/03/2024") to YYYYMMDD format
        try:
            for fmt in ["%d/%m/%Y", "%d-%m-%Y", "%d %B %Y"]:
                try:
                    date_obj = datetime.strptime(period, fmt)
                    date_str = date_obj.strftime("%Y%m%d")
                    break
                except ValueError:
                    continue
            else:
                return None  # Could not parse date

            # Check if any file in downloads_dir contains that date
            for file_path in self.downloads_dir.glob(f"*{date_str}*.csv"):
                return file_path.name

        except Exception:
            pass

        return None

    def _has_next_page(self) -> bool:
        """Check if there's a next page of invoices."""
        try:
            next_button = self.page.locator(self.SELECTORS["next_page"]).first
            if next_button.is_visible(timeout=1000):
                is_disabled = next_button.get_attribute("disabled") is not None
                aria_disabled = next_button.get_attribute("aria-disabled") == "true"
                has_disabled_class = "disabled" in (next_button.get_attribute("class") or "")
                return not (is_disabled or aria_disabled or has_disabled_class)
        except Exception:
            pass
        return False

    def _go_to_next_page(self) -> bool:
        """Navigate to the next page of invoices."""
        try:
            next_button = self.page.locator(self.SELECTORS["next_page"]).first
            if next_button.is_visible(timeout=1000):
                self.logger.info("Clicking next page...")
                next_button.click()
                self._wait_for_page()
                time.sleep(1)
                return True
        except Exception as e:
            self.logger.error(f"Error navigating to next page: {e}")
        return False

    def _parse_invoice_date(self, date_str: str) -> Optional[datetime]:
        """Parse invoice date from various formats."""
        if not date_str:
            return None

        date_formats = [
            "%d/%m/%Y",
            "%d-%m-%Y",
            "%d %B %Y",
            "%d %b %Y",
            "%Y-%m-%d",
            "%d.%m.%Y",
        ]

        for fmt in date_formats:
            try:
                return datetime.strptime(date_str.strip(), fmt)
            except ValueError:
                continue

        return None

    def download_invoices(
        self,
        location_id: str = None,
        start_date: datetime = None,
        end_date: datetime = None,
        max_invoices: int = 5,
    ) -> List[DownloadedInvoice]:
        """Download invoices (CSV from Statement column).

        Args:
            location_id: Branch/location ID to download invoices for
            start_date: Only download invoices on or after this date
            end_date: Only download invoices on or before this date
            max_invoices: Max invoices to check (default 5, newest first).
                         Use higher value for initial full sync.
        """
        downloaded_invoices = []

        # Switch to specific branch if needed
        if location_id and location_id != "default":
            # Find branch name from cache
            branch_name = None
            for loc in self.locations_cache:
                if loc.get("id") == location_id:
                    branch_name = loc.get("name")
                    break
            self._switch_to_branch(location_id, branch_name)

        # Navigate to invoices section
        if not self._navigate_to_invoices():
            return []

        # Dismiss any popups (including NPS survey)
        self._dismiss_popups()

        # Log date filter if specified
        if start_date or end_date:
            date_range = []
            if start_date:
                date_range.append(f"from {start_date.strftime('%Y-%m-%d')}")
            if end_date:
                date_range.append(f"to {end_date.strftime('%Y-%m-%d')}")
            self.logger.info(f"Filtering invoices {' '.join(date_range)}")

        # Process first page only (newest invoices)
        self.logger.info("Processing invoices (newest first)...")
        self.screenshot("04_invoice_page")

        # Dismiss popups before processing
        self._dismiss_popups()

        # Find all CSV links on this page
        csv_links = self._get_all_csv_links()

        if not csv_links:
            self.logger.warning("No CSV links found on this page")
            self.screenshot("05_no_csv_links_found")
            return []

        # Only check first max_invoices (newest)
        csv_links = csv_links[:max_invoices]
        self.logger.info(f"Checking {len(csv_links)} newest invoices...")

        total_downloaded = 0
        total_skipped_date = 0
        consecutive_skips = 0

        for index, csv_link in enumerate(csv_links):
            # Extract invoice info for this link
            invoice_info = self._extract_invoice_info_from_link(csv_link)

            # Parse invoice date for filtering
            invoice_date = self._parse_invoice_date(invoice_info.get("period"))

            # Log date extraction result for first few invoices
            if index < 5:
                if invoice_date:
                    self.logger.info(f"Invoice #{index+1} date: {invoice_date.strftime('%Y-%m-%d')} (from: {invoice_info.get('period')})")
                else:
                    self.logger.info(f"Invoice #{index+1}: No date found (period: {invoice_info.get('period')})")

            # Apply date filter if specified
            if invoice_date:
                # Skip if invoice is after end_date
                if end_date and invoice_date.date() > end_date.date():
                    self.logger.debug(f"Skipping #{index+1}: {invoice_date.date()} is after end_date {end_date.date()}")
                    continue

                # Stop if invoice is before start_date (invoices are sorted newest first)
                if start_date and invoice_date.date() < start_date.date():
                    self.logger.info(f"Stopping: invoice #{index+1} ({invoice_date.date()}) is before start_date ({start_date.date()})")
                    total_skipped_date += 1
                    # If we've seen 2 consecutive invoices older than start_date, stop
                    if total_skipped_date >= 2:
                        self.logger.info("Found 2 invoices older than start_date, stopping")
                        break
                    continue
                else:
                    total_skipped_date = 0  # Reset counter

            # Skip if already downloaded (match by date in filename)
            existing_file = self._is_invoice_downloaded(invoice_info)
            if existing_file:
                self.logger.info(f"Skipping #{index+1}: {existing_file} (already exists)")
                consecutive_skips += 1
                # Stop early if 3 consecutive skips (all recent ones exist)
                if consecutive_skips >= 3:
                    self.logger.info("3 consecutive skips - all recent invoices exist")
                    break
                continue

            consecutive_skips = 0  # Reset on successful download
            file_path = self._download_csv(csv_link, index)

            if file_path:
                total_downloaded += 1

                # Use parsed date or fallback to now
                if not invoice_date:
                    invoice_date = datetime.now()

                downloaded_invoices.append(DownloadedInvoice(
                    platform=self.PLATFORM_NAME,
                    brand="Deliveroo",
                    location=location_id or "default",
                    invoice_id=invoice_info.get("invoice_number") or file_path.stem,
                    invoice_date=invoice_date,
                    file_path=file_path,
                    file_type="csv",
                ))

        self.logger.info(f"Downloaded {total_downloaded} new invoice(s)")
        return downloaded_invoices


# For testing/debugging
if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)

    from config import settings

    if not settings.deliveroo.email or not settings.deliveroo.password:
        print("Please set DELIVEROO_EMAIL and DELIVEROO_PASSWORD in .env file")
        exit(1)

    with DeliverooBot(
        email=settings.deliveroo.email,
        password=settings.deliveroo.password,
        headless=False,
    ) as bot:
        invoices = bot.run_full_sync()
        print(f"\nDownloaded {len(invoices)} invoices")
        for inv in invoices:
            print(f"  - {inv.file_path}")
