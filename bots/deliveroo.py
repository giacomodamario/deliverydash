"""Deliveroo Partner Hub bot for downloading invoices."""

import re
import time
from datetime import datetime
from typing import List, Optional
from pathlib import Path

from playwright.sync_api import TimeoutError as PlaywrightTimeout

from .base import BaseBot, DownloadedInvoice


class DeliverooBot(BaseBot):
    """Bot for downloading invoices from Deliveroo Partner Hub."""

    PLATFORM_NAME = "deliveroo"
    LOGIN_URL = "https://partner-hub.deliveroo.com/"

    # Selectors - these may need adjustment based on actual DOM
    SELECTORS = {
        # Login page
        "email_input": 'input[type="email"], input[name="email"], #email',
        "password_input": 'input[type="password"], input[name="password"], #password',
        "login_button": 'button[type="submit"], button:has-text("Log in"), button:has-text("Sign in")',

        # Navigation
        "invoices_link": 'a:has-text("Invoices"), a:has-text("Billing"), a[href*="invoice"], a[href*="billing"]',
        "location_selector": 'select[name="location"], select[name="restaurant"], [data-testid="location-selector"]',

        # Invoice list
        "invoice_row": 'tr[data-invoice-id], .invoice-row, table tbody tr',
        "invoice_download": 'a:has-text("Download"), button:has-text("Download"), a[href*=".csv"], a[href*=".pdf"]',
        "download_csv": 'a:has-text("CSV"), button:has-text("CSV"), a[href*=".csv"]',
        "download_all": 'button:has-text("Download all"), a:has-text("Export")',

        # Pagination
        "next_page": 'button:has-text("Next"), a:has-text("Next"), [aria-label="Next page"]',
        "pagination": '.pagination, nav[aria-label="pagination"]',
    }

    def login(self) -> bool:
        """Log into Deliveroo Partner Hub."""
        self.logger.info(f"Navigating to {self.LOGIN_URL}")
        self.page.goto(self.LOGIN_URL)

        # Wait for the page to load
        self.page.wait_for_load_state("networkidle")

        # Take a screenshot to see what we're dealing with
        self.screenshot("login_page")

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
            self.page.wait_for_load_state("networkidle")
            time.sleep(2)  # Extra wait for any redirects

            # Check if login was successful by looking for dashboard elements
            # or checking if we're no longer on the login page
            current_url = self.page.url
            self.logger.info(f"Current URL after login: {current_url}")

            self.screenshot("after_login")

            # Check for common post-login indicators
            if "login" not in current_url.lower() or "dashboard" in current_url.lower():
                self.logger.info("Login appears successful")
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
        """Navigate to the invoices/billing section."""
        self.logger.info("Navigating to invoices section...")

        try:
            # Try to find invoices link in navigation
            invoices_link = self.page.locator(self.SELECTORS["invoices_link"]).first
            invoices_link.wait_for(timeout=10000)
            invoices_link.click()

            self.page.wait_for_load_state("networkidle")
            self.screenshot("invoices_page")

            self.logger.info("Navigated to invoices page")
            return True

        except PlaywrightTimeout:
            self.logger.warning("Could not find invoices link, trying direct URL...")

            # Try common invoice URLs
            invoice_urls = [
                "https://partner-hub.deliveroo.com/invoices",
                "https://partner-hub.deliveroo.com/billing",
                "https://partner-hub.deliveroo.com/financials",
                "https://partner-hub.deliveroo.com/payments",
            ]

            for url in invoice_urls:
                try:
                    self.page.goto(url)
                    self.page.wait_for_load_state("networkidle")

                    # Check if we landed on a valid page (not 404)
                    if "404" not in self.page.title().lower():
                        self.logger.info(f"Found invoices at: {url}")
                        self.screenshot("invoices_page")
                        return True
                except Exception:
                    continue

            self.logger.error("Could not find invoices section")
            return False

    def get_locations(self) -> List[dict]:
        """Get list of all locations/restaurants for the account."""
        locations = []

        try:
            # Look for location selector dropdown
            location_selector = self.page.locator(self.SELECTORS["location_selector"])

            if location_selector.count() > 0:
                # Get all options from the dropdown
                options = location_selector.locator("option").all()

                for option in options:
                    value = option.get_attribute("value")
                    text = option.text_content().strip()

                    if value and value != "":
                        locations.append({
                            "id": value,
                            "name": text,
                        })

                self.logger.info(f"Found {len(locations)} locations in dropdown")
            else:
                # No location selector - might be single location account
                # or locations listed differently
                self.logger.info("No location dropdown found, assuming single location or different structure")

                # Try to extract from page content or URL
                locations.append({
                    "id": "default",
                    "name": "Default Location",
                })

        except Exception as e:
            self.logger.error(f"Error getting locations: {e}")
            locations.append({
                "id": "default",
                "name": "Default Location",
            })

        return locations

    def _select_location(self, location_id: str) -> bool:
        """Select a specific location in the UI."""
        if location_id == "default":
            return True

        try:
            location_selector = self.page.locator(self.SELECTORS["location_selector"])
            if location_selector.count() > 0:
                location_selector.select_option(value=location_id)
                self.page.wait_for_load_state("networkidle")
                time.sleep(1)
                return True
        except Exception as e:
            self.logger.error(f"Error selecting location {location_id}: {e}")

        return False

    def _get_invoice_rows(self) -> list:
        """Get all invoice rows from the current page."""
        rows = []

        try:
            row_locator = self.page.locator(self.SELECTORS["invoice_row"])
            count = row_locator.count()

            for i in range(count):
                row = row_locator.nth(i)
                rows.append(row)

        except Exception as e:
            self.logger.error(f"Error getting invoice rows: {e}")

        return rows

    def _extract_invoice_info(self, row) -> dict:
        """Extract invoice information from a table row."""
        info = {
            "id": None,
            "date": None,
            "amount": None,
            "status": None,
        }

        try:
            # Try to get invoice ID from data attribute
            info["id"] = row.get_attribute("data-invoice-id")

            # Get text content and try to parse
            text = row.text_content()

            # Try to find date pattern (DD/MM/YYYY or YYYY-MM-DD)
            date_match = re.search(r'(\d{2}/\d{2}/\d{4}|\d{4}-\d{2}-\d{2})', text)
            if date_match:
                info["date"] = date_match.group(1)

            # Try to find amount pattern
            amount_match = re.search(r'[€£$]\s*[\d,]+\.?\d*', text)
            if amount_match:
                info["amount"] = amount_match.group(0)

        except Exception as e:
            self.logger.debug(f"Error extracting invoice info: {e}")

        return info

    def _download_single_invoice(self, row, invoice_info: dict) -> Optional[Path]:
        """Download a single invoice from a row."""
        try:
            # Look for download link within the row
            download_link = row.locator(self.SELECTORS["invoice_download"]).first

            if download_link.count() == 0:
                download_link = row.locator(self.SELECTORS["download_csv"]).first

            if download_link.count() > 0:
                # Use the download handler
                with self.page.expect_download() as download_info:
                    download_link.click()

                download = download_info.value

                # Generate filename
                invoice_id = invoice_info.get("id") or datetime.now().strftime("%Y%m%d%H%M%S")
                invoice_date = invoice_info.get("date") or "unknown"
                filename = f"deliveroo_{invoice_date}_{invoice_id}{Path(download.suggested_filename).suffix}"

                save_path = self.downloads_dir / filename
                download.save_as(str(save_path))

                self.logger.info(f"Downloaded: {save_path}")
                return save_path

        except PlaywrightTimeout:
            self.logger.warning(f"Download timeout for invoice {invoice_info.get('id')}")
        except Exception as e:
            self.logger.error(f"Error downloading invoice: {e}")

        return None

    def _try_bulk_download(self) -> List[Path]:
        """Try to use bulk download feature if available."""
        downloaded = []

        try:
            download_all = self.page.locator(self.SELECTORS["download_all"]).first
            if download_all.count() > 0:
                self.logger.info("Found bulk download option, attempting...")

                with self.page.expect_download() as download_info:
                    download_all.click()

                download = download_info.value
                save_path = self.downloads_dir / download.suggested_filename
                download.save_as(str(save_path))

                self.logger.info(f"Bulk download saved: {save_path}")
                downloaded.append(save_path)

        except Exception as e:
            self.logger.debug(f"Bulk download not available: {e}")

        return downloaded

    def _has_next_page(self) -> bool:
        """Check if there's a next page of invoices."""
        try:
            next_button = self.page.locator(self.SELECTORS["next_page"]).first
            if next_button.count() > 0:
                # Check if it's disabled
                is_disabled = next_button.get_attribute("disabled") is not None
                aria_disabled = next_button.get_attribute("aria-disabled") == "true"
                return not (is_disabled or aria_disabled)
        except Exception:
            pass
        return False

    def _go_to_next_page(self) -> bool:
        """Navigate to the next page of invoices."""
        try:
            next_button = self.page.locator(self.SELECTORS["next_page"]).first
            if next_button.count() > 0:
                next_button.click()
                self.page.wait_for_load_state("networkidle")
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
        """Download invoices for a location within a date range."""
        downloaded_invoices = []

        # Navigate to invoices section
        if not self._navigate_to_invoices():
            return []

        # Select location if specified
        if location_id:
            self._select_location(location_id)

        # Try bulk download first
        bulk_files = self._try_bulk_download()
        if bulk_files:
            for file_path in bulk_files:
                downloaded_invoices.append(DownloadedInvoice(
                    platform=self.PLATFORM_NAME,
                    brand="Unknown",  # Will be parsed from file
                    location=location_id or "default",
                    invoice_id=file_path.stem,
                    invoice_date=datetime.now(),
                    file_path=file_path,
                    file_type=file_path.suffix.lstrip("."),
                ))
            return downloaded_invoices

        # Fall back to individual downloads
        page_num = 1
        while True:
            self.logger.info(f"Processing page {page_num}")
            self.screenshot(f"invoice_page_{page_num}")

            rows = self._get_invoice_rows()
            self.logger.info(f"Found {len(rows)} invoice rows on page {page_num}")

            for row in rows:
                invoice_info = self._extract_invoice_info(row)
                file_path = self._download_single_invoice(row, invoice_info)

                if file_path:
                    # Parse date if available
                    invoice_date = datetime.now()
                    if invoice_info.get("date"):
                        try:
                            # Try different date formats
                            for fmt in ["%d/%m/%Y", "%Y-%m-%d", "%m/%d/%Y"]:
                                try:
                                    invoice_date = datetime.strptime(invoice_info["date"], fmt)
                                    break
                                except ValueError:
                                    continue
                        except Exception:
                            pass

                    # Apply date filters
                    if start_date and invoice_date < start_date:
                        continue
                    if end_date and invoice_date > end_date:
                        continue

                    downloaded_invoices.append(DownloadedInvoice(
                        platform=self.PLATFORM_NAME,
                        brand="Unknown",
                        location=location_id or "default",
                        invoice_id=invoice_info.get("id") or file_path.stem,
                        invoice_date=invoice_date,
                        file_path=file_path,
                        file_type=file_path.suffix.lstrip("."),
                    ))

            # Check for more pages
            if self._has_next_page():
                self._go_to_next_page()
                page_num += 1
            else:
                break

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
