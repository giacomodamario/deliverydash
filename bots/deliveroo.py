"""Deliveroo Restaurant Hub bot for downloading invoices."""

import re
import time
from datetime import datetime
from typing import List, Optional
from pathlib import Path

from playwright.sync_api import TimeoutError as PlaywrightTimeout

from .base import BaseBot, DownloadedInvoice


class DeliverooBot(BaseBot):
    """Bot for downloading invoices from Deliveroo Restaurant Hub."""

    PLATFORM_NAME = "deliveroo"
    LOGIN_URL = "https://restaurant-hub.deliveroo.net/"
    INVOICES_URL = "https://restaurant-hub.deliveroo.net/invoices"

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

    def _dismiss_popups(self):
        """Dismiss Deliveroo-specific popups (announcements, surveys, modals)."""
        self.logger.info("Checking for popups to dismiss...")

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

            # NPS survey popup
            ('button:has-text("Close")', "Close button"),
            ('button:has-text("Chiudi")', "Chiudi button"),
            ('[aria-label="Close survey"]', "Survey close"),
            ('[data-testid="nps-close"]', "NPS close"),

            # Generic modal/dialog close buttons
            ('[role="dialog"] button[aria-label="Close"]', "Dialog close"),
            ('.modal button:has-text("×")', "Modal X button"),
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

    def login(self) -> bool:
        """Log into Deliveroo Restaurant Hub."""
        self.logger.info(f"Navigating to {self.LOGIN_URL}")
        self.page.goto(self.LOGIN_URL)

        # Wait for page (use domcontentloaded to avoid timeout)
        self._wait_for_page()

        # Dismiss cookie consent popup if present
        self.dismiss_cookie_consent()

        # Dismiss any Deliveroo-specific popups
        self._dismiss_popups()

        # Check if already logged in (from saved session)
        current_url = self.page.url
        if "/home" in current_url or "/analytics" in current_url or "/invoices" in current_url:
            self.logger.info(f"Already logged in (URL: {current_url}), skipping login")
            self.screenshot("01_already_logged_in")
            return True

        # Also check if sidebar with Invoices link is visible
        try:
            invoices_link = self.page.locator(self.SELECTORS["invoices_sidebar"]).first
            if invoices_link.is_visible(timeout=2000):
                self.logger.info("Already logged in (found Invoices link), skipping login")
                self.screenshot("01_already_logged_in")
                return True
        except Exception:
            pass

        # Take a screenshot
        self.screenshot("01_login_page")

        try:
            # Try to find and fill email
            self.logger.info("Looking for email input...")
            email_input = self.page.locator(self.SELECTORS["email_input"]).first
            email_input.wait_for(timeout=10000)
            email_input.fill(self.email)
            self.logger.info("Email entered")

            # Look for password input
            self.logger.info("Looking for password input...")
            password_input = self.page.locator(self.SELECTORS["password_input"]).first
            password_input.wait_for(timeout=5000)
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

            self.screenshot("02_after_login")

            # Check if login was successful
            if "login" not in current_url.lower() or "analytics" in current_url.lower() or "hub" in current_url.lower():
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
        """Navigate to the invoices page."""
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
                self.screenshot("03_invoices_page")
                return True
        except Exception as e:
            self.logger.info(f"Sidebar link not found: {e}")

        # Fall back to direct URL
        self.logger.info(f"Navigating directly to {self.INVOICES_URL}")
        self.page.goto(self.INVOICES_URL)
        self._wait_for_page()
        self._dismiss_popups()
        self.screenshot("03_invoices_page")

        # Check if we're on the invoices page
        if "invoice" in self.page.url.lower():
            self.logger.info("Successfully navigated to invoices page")
            return True

        self.logger.error("Failed to navigate to invoices page")
        return False

    def get_locations(self) -> List[dict]:
        """Get list of all locations/restaurants for the account."""
        # For now, return a default location
        # TODO: Implement location switching if account has multiple locations
        return [{"id": "default", "name": "Default Location"}]

    def _get_invoice_rows(self) -> list:
        """Get all invoice rows from the current page."""
        try:
            # Wait for table to be visible
            self.page.wait_for_selector(self.SELECTORS["invoice_table"], timeout=10000)
            time.sleep(1)  # Wait for table to fully render

            rows = self.page.locator(self.SELECTORS["invoice_row"]).all()
            self.logger.info(f"Found {len(rows)} invoice rows")
            return rows
        except Exception as e:
            self.logger.error(f"Error getting invoice rows: {e}")
            return []

    def _extract_invoice_info_from_row(self, row) -> dict:
        """Extract invoice information from a table row."""
        info = {
            "invoice_number": None,
            "period": None,
            "due_date": None,
            "total": None,
        }

        try:
            text = row.text_content()

            # Extract invoice number (Fattura n° XXXXX)
            invoice_match = re.search(r'(?:Fattura\s*n[°º]?\s*|Invoice\s*#?\s*)(\d+)', text, re.IGNORECASE)
            if invoice_match:
                info["invoice_number"] = invoice_match.group(1)

            # Extract date patterns
            date_matches = re.findall(r'\d{1,2}/\d{1,2}/\d{4}', text)
            if date_matches:
                info["period"] = date_matches[0]
                if len(date_matches) > 1:
                    info["due_date"] = date_matches[1]

            # Extract amount
            amount_match = re.search(r'[€£$]\s*-?[\d.,]+', text)
            if amount_match:
                info["total"] = amount_match.group(0)

        except Exception as e:
            self.logger.debug(f"Error extracting invoice info: {e}")

        return info

    def _download_csv_from_row(self, row, invoice_info: dict) -> Optional[Path]:
        """Download the CSV file from the Sintesi column of a row."""
        try:
            # Find CSV link in this row
            csv_link = row.locator(self.SELECTORS["csv_link"]).first

            if csv_link.is_visible(timeout=1000):
                invoice_num = invoice_info.get("invoice_number") or "unknown"
                period = invoice_info.get("period") or datetime.now().strftime("%Y%m%d")
                period_clean = period.replace("/", "-")

                self.logger.info(f"Downloading CSV for invoice {invoice_num}...")

                # Click and wait for download
                with self.page.expect_download(timeout=30000) as download_info:
                    csv_link.click()

                download = download_info.value

                # Generate filename
                filename = f"deliveroo_{period_clean}_{invoice_num}.csv"
                save_path = self.downloads_dir / filename

                # Handle duplicate filenames
                counter = 1
                while save_path.exists():
                    filename = f"deliveroo_{period_clean}_{invoice_num}_{counter}.csv"
                    save_path = self.downloads_dir / filename
                    counter += 1

                download.save_as(str(save_path))
                self.logger.info(f"Downloaded: {save_path.name}")
                return save_path

        except PlaywrightTimeout:
            self.logger.warning(f"Download timeout for invoice {invoice_info.get('invoice_number')}")
        except Exception as e:
            self.logger.error(f"Error downloading CSV: {e}")

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

    def download_invoices(
        self,
        location_id: str = None,
        start_date: datetime = None,
        end_date: datetime = None,
    ) -> List[DownloadedInvoice]:
        """Download all invoices (CSV from Sintesi column)."""
        downloaded_invoices = []

        # Navigate to invoices section
        if not self._navigate_to_invoices():
            return []

        # Process all pages
        page_num = 1
        total_downloaded = 0

        while True:
            self.logger.info(f"Processing invoice page {page_num}...")
            self.screenshot(f"04_invoice_page_{page_num}")

            rows = self._get_invoice_rows()

            if not rows:
                self.logger.warning("No invoice rows found on this page")
                break

            for row in rows:
                invoice_info = self._extract_invoice_info_from_row(row)
                file_path = self._download_csv_from_row(row, invoice_info)

                if file_path:
                    total_downloaded += 1

                    # Parse date for the record
                    invoice_date = datetime.now()
                    if invoice_info.get("period"):
                        try:
                            invoice_date = datetime.strptime(invoice_info["period"], "%d/%m/%Y")
                        except ValueError:
                            pass

                    downloaded_invoices.append(DownloadedInvoice(
                        platform=self.PLATFORM_NAME,
                        brand="Deliveroo",
                        location=location_id or "default",
                        invoice_id=invoice_info.get("invoice_number") or file_path.stem,
                        invoice_date=invoice_date,
                        file_path=file_path,
                        file_type="csv",
                    ))

            # Check for more pages
            if self._has_next_page():
                self._go_to_next_page()
                page_num += 1
            else:
                self.logger.info("No more pages")
                break

        self.logger.info(f"Downloaded {total_downloaded} invoice CSV files")
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
