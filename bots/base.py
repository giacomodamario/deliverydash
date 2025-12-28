"""Base bot class with common functionality for all platform bots."""

import json
import logging
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, List
from datetime import datetime
from dataclasses import dataclass

from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page

from config import settings


@dataclass
class DownloadedInvoice:
    """Represents a downloaded invoice file."""
    platform: str
    brand: str
    location: str
    invoice_id: str
    invoice_date: datetime
    file_path: Path
    file_type: str  # 'csv', 'pdf', 'xlsx'


class BaseBot(ABC):
    """Base class for platform-specific invoice download bots."""

    PLATFORM_NAME: str = "base"
    LOGIN_URL: str = ""

    def __init__(
        self,
        email: str,
        password: str,
        headless: bool = None,
        slow_mo: int = None,
    ):
        self.email = email
        self.password = password
        self.headless = headless if headless is not None else settings.headless
        self.slow_mo = slow_mo if slow_mo is not None else settings.slow_mo

        self.logger = logging.getLogger(f"bot.{self.PLATFORM_NAME}")
        self.downloads_dir = settings.downloads_dir / self.PLATFORM_NAME
        self.session_file = settings.sessions_dir / f"{self.PLATFORM_NAME}_session.json"

        self._playwright = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None

        # Ensure directories exist
        self.downloads_dir.mkdir(parents=True, exist_ok=True)
        settings.sessions_dir.mkdir(parents=True, exist_ok=True)

    @property
    def page(self) -> Page:
        """Get the current page, raising an error if not initialized."""
        if self._page is None:
            raise RuntimeError("Browser not started. Call start() first.")
        return self._page

    def start(self, use_session: bool = True):
        """Start the browser and create a new page."""
        self.logger.info(f"Starting {self.PLATFORM_NAME} bot...")

        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(
            headless=self.headless,
            slow_mo=self.slow_mo,
        )

        # Try to load existing session
        storage_state = None
        if use_session and self.session_file.exists():
            try:
                self.logger.info("Loading saved session...")
                storage_state = str(self.session_file)
            except Exception as e:
                self.logger.warning(f"Could not load session: {e}")

        self._context = self._browser.new_context(
            accept_downloads=True,
            viewport={"width": 1920, "height": 1080},
            storage_state=storage_state,
        )
        self._page = self._context.new_page()

        # Set default timeout
        self._page.set_default_timeout(settings.timeout)

        self.logger.info("Browser started successfully")

    def save_session(self):
        """Save current session (cookies, localStorage) for reuse."""
        if self._context:
            try:
                self._context.storage_state(path=str(self.session_file))
                self.logger.info(f"Session saved to {self.session_file}")
            except Exception as e:
                self.logger.warning(f"Could not save session: {e}")

    def stop(self, save_session: bool = True):
        """Close the browser and cleanup."""
        self.logger.info(f"Stopping {self.PLATFORM_NAME} bot...")

        if save_session:
            self.save_session()

        if self._context:
            self._context.close()
        if self._browser:
            self._browser.close()
        if self._playwright:
            self._playwright.stop()

        self._page = None
        self._context = None
        self._browser = None
        self._playwright = None

        self.logger.info("Browser stopped")

    def __enter__(self):
        """Context manager entry."""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.stop()
        return False

    def screenshot(self, name: str = "screenshot"):
        """Take a screenshot for debugging."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = self.downloads_dir / f"{name}_{timestamp}.png"
        self.page.screenshot(path=str(path))
        self.logger.info(f"Screenshot saved: {path}")
        return path

    def wait_and_click(self, selector: str, timeout: int = None):
        """Wait for an element and click it."""
        self.page.wait_for_selector(selector, timeout=timeout)
        self.page.click(selector)

    def wait_and_fill(self, selector: str, value: str, timeout: int = None):
        """Wait for an element and fill it with a value."""
        self.page.wait_for_selector(selector, timeout=timeout)
        self.page.fill(selector, value)

    def download_file(self, click_selector: str, filename: str = None, timeout: int = 60000) -> Path:
        """
        Click a download button and wait for the download to complete.

        Args:
            click_selector: Selector for the element that triggers download
            filename: Optional custom filename for the downloaded file
            timeout: Download timeout in milliseconds

        Returns:
            Path to the downloaded file
        """
        with self.page.expect_download(timeout=timeout) as download_info:
            self.page.click(click_selector)

        download = download_info.value

        # Determine save path
        if filename:
            save_path = self.downloads_dir / filename
        else:
            save_path = self.downloads_dir / download.suggested_filename

        # Save the file
        download.save_as(str(save_path))
        self.logger.info(f"Downloaded: {save_path}")

        return save_path

    def wait_for_stable_page(self, timeout: int = 5000):
        """Wait for page to stabilize (no network activity)."""
        try:
            self.page.wait_for_load_state("networkidle", timeout=timeout)
        except Exception:
            pass  # Timeout is OK, page might have persistent connections
        time.sleep(0.5)  # Extra small wait for JS rendering

    @abstractmethod
    def login(self) -> bool:
        """
        Log into the platform.

        Returns:
            True if login successful, False otherwise
        """
        pass

    @abstractmethod
    def get_locations(self) -> List[dict]:
        """
        Get list of all locations/restaurants for the account.

        Returns:
            List of location dictionaries with at least 'id' and 'name' keys
        """
        pass

    @abstractmethod
    def download_invoices(
        self,
        location_id: str = None,
        start_date: datetime = None,
        end_date: datetime = None,
    ) -> List[DownloadedInvoice]:
        """
        Download invoices for a location within a date range.

        Args:
            location_id: Optional specific location ID (None = all locations)
            start_date: Start of date range (None = earliest available)
            end_date: End of date range (None = today)

        Returns:
            List of DownloadedInvoice objects
        """
        pass

    def run_full_sync(self) -> List[DownloadedInvoice]:
        """
        Run a full synchronization - download all historical invoices.

        This is the main entry point for downloading everything.
        """
        self.logger.info(f"Starting full sync for {self.PLATFORM_NAME}")

        all_invoices = []

        try:
            # Login
            if not self.login():
                self.logger.error("Login failed!")
                return []

            # Get all locations
            locations = self.get_locations()
            self.logger.info(f"Found {len(locations)} locations")

            # Download invoices for each location
            for location in locations:
                self.logger.info(f"Processing location: {location.get('name', location.get('id'))}")
                invoices = self.download_invoices(location_id=location["id"])
                all_invoices.extend(invoices)
                self.logger.info(f"Downloaded {len(invoices)} invoices for this location")

        except Exception as e:
            self.logger.error(f"Error during sync: {e}")
            self.screenshot("error")
            raise

        self.logger.info(f"Full sync complete. Total invoices: {len(all_invoices)}")
        return all_invoices
