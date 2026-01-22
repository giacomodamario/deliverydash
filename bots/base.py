"""Base bot class with common functionality for all platform bots."""

import json
import logging
import os
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, List
from datetime import datetime
from dataclasses import dataclass

from patchright.sync_api import sync_playwright, Browser, BrowserContext, Page

from config import settings
from .stealth import (
    get_random_viewport,
    get_random_user_agent,
    human_sleep,
    human_type,
    human_click,
    human_mouse_move,
    random_scroll,
)


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

        # Launch browser with stealth settings (Patchright handles anti-detection)
        launch_args = {
            'headless': self.headless,
            'slow_mo': self.slow_mo,
            'args': [
                '--disable-blink-features=AutomationControlled',
                '--disable-infobars',
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
            ],
        }

        self._browser = self._playwright.chromium.launch(**launch_args)

        # Try to load existing session
        storage_state = None
        if use_session and self.session_file.exists():
            try:
                self.logger.info("Loading saved session...")
                storage_state = str(self.session_file)
            except Exception as e:
                self.logger.warning(f"Could not load session: {e}")

        # Get randomized browser fingerprint for stealth
        viewport = get_random_viewport()
        user_agent = get_random_user_agent()
        self.logger.info(f"Using viewport: {viewport['width']}x{viewport['height']}")
        self.logger.debug(f"Using User-Agent: {user_agent}")

        # Create browser context with stealth settings
        self._context = self._browser.new_context(
            accept_downloads=True,
            viewport=viewport,
            storage_state=storage_state,
            user_agent=user_agent,
            locale="en-GB",
            timezone_id="Europe/Rome",
            # Additional stealth settings
            color_scheme="light",
            device_scale_factor=1,
            has_touch=True,  # Enable touch for press & hold challenges
            is_mobile=False,
            java_script_enabled=True,
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
                os.chmod(self.session_file, 0o600)  # Restrict permissions to owner only
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
        """Take a screenshot for debugging (only if debug_screenshots enabled)."""
        if not settings.debug_screenshots:
            self.logger.debug(f"Screenshot skipped (debug_screenshots=False): {name}")
            return None
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
        human_sleep(0.5, 0.15)  # Extra small wait for JS rendering

    def dismiss_cookie_consent(self, timeout: int = 5000) -> bool:
        """
        Dismiss cookie consent popups (OneTrust, CookieBot, etc.).

        This handles common cookie consent implementations across platforms.
        Call this after navigating to a new page before interacting with elements.

        Returns:
            True if a popup was found and dismissed, False otherwise
        """
        # Quick pre-check: skip selector iteration if no cookie-related content
        try:
            content = self.page.content().lower()
            cookie_keywords = ['cookie', 'consent', 'privacy', 'onetrust', 'cookiebot', 'gdpr']
            if not any(kw in content for kw in cookie_keywords):
                self.logger.debug("No cookie keywords found, skipping popup check")
                return False
        except Exception:
            pass  # If content check fails, fall through to selector check

        # Common cookie consent button selectors (in priority order)
        cookie_selectors = [
            # OneTrust (used by Deliveroo and many others) - most common first
            '#onetrust-accept-btn-handler',
            'button:has-text("Accept All Cookies")',
            'button:has-text("Accept all cookies")',

            # Generic accept buttons (multiple languages)
            'button:has-text("Accept All")',
            'button:has-text("Accept all")',
            'button:has-text("Accept")',
            'button:has-text("Accetta tutti")',
            'button:has-text("Accetta")',

            # CookieBot
            '#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll',
            '#CybotCookiebotDialogBodyButtonAccept',

            # Less common patterns
            '#onetrust-pc-btn-handler',
            'button[id*="onetrust"]',
            'button:has-text("Accept Cookies")',
            'button:has-text("Accept cookies")',
            'button:has-text("Accepter tout")',
            'button:has-text("Accepter")',
            'button:has-text("Akzeptieren")',
            'button:has-text("Alle akzeptieren")',
            '[data-testid="cookie-accept"]',
            '[data-testid="accept-cookies"]',
            '.cookie-consent-accept',
            '.cc-accept',
            '.cc-allow',
            '#cookie-accept',
            '#accept-cookies',
            '[aria-label="Accept cookies"]',
            '[aria-label="Accept all cookies"]',
        ]

        self.logger.debug("Checking for cookie consent popup...")

        for selector in cookie_selectors:
            try:
                button = self.page.locator(selector).first
                if button.is_visible(timeout=300):  # Reduced from 500ms
                    self.logger.info(f"Found cookie consent button: {selector}")
                    button.click()
                    human_sleep(0.5, 0.15)  # Wait for popup to dismiss
                    self.logger.info("Cookie consent dismissed")
                    return True
            except Exception:
                continue

        self.logger.debug("No cookie consent popup found")
        return False

    # Common popup selectors shared across platforms
    COMMON_POPUP_SELECTORS = [
        # Generic close buttons
        ('button[aria-label="Close"]', "Close button"),
        ('button[aria-label="Chiudi"]', "Close button (IT)"),
        ('button[aria-label="Cerrar"]', "Close button (ES)"),
        ('[data-testid="modal-close"]', "Modal close"),
        ('.modal-close', "Modal close class"),

        # OK/Got it/Acknowledge buttons
        ('button:has-text("Got it")', "Got it"),
        ('button:has-text("OK")', "OK button"),
        ('button:has-text("Capito")', "Capito"),
        ('button:has-text("Dismiss")', "Dismiss"),

        # Skip/Later buttons
        ('button:has-text("Skip")', "Skip"),
        ('button:has-text("Not now")', "Not now"),
        ('button:has-text("Maybe later")', "Maybe later"),
        ('button:has-text("No thanks")', "No thanks"),

        # Generic X buttons
        ('[role="dialog"] button:has-text("×")', "Dialog X"),
        ('button:has-text("×")', "X button"),
        ('button:has-text("✕")', "Close symbol"),
    ]

    # Override in subclass to add platform-specific selectors
    PLATFORM_POPUP_SELECTORS = []

    def dismiss_popups(self, timeout: int = 500) -> int:
        """
        Dismiss any visible popups (announcements, surveys, modals).

        Uses common selectors plus any platform-specific selectors defined
        in PLATFORM_POPUP_SELECTORS.

        Args:
            timeout: Timeout in ms to wait for each selector check

        Returns:
            Number of popups dismissed
        """
        self.logger.debug("Checking for popups...")

        # Combine common + platform-specific selectors
        all_selectors = self.COMMON_POPUP_SELECTORS + self.PLATFORM_POPUP_SELECTORS

        dismissed_count = 0
        for selector, description in all_selectors:
            try:
                button = self.page.locator(selector).first
                if button.is_visible(timeout=timeout):
                    self.logger.debug(f"Dismissing popup: {description}")
                    button.click()
                    human_sleep(0.3, 0.1)
                    dismissed_count += 1
            except Exception:
                continue

        if dismissed_count > 0:
            self.logger.debug(f"Dismissed {dismissed_count} popup(s)")
        return dismissed_count

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
        max_invoices: int = 5,
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

    def run_full_sync(
        self,
        max_invoices: int = 5,
        start_date: datetime = None,
        end_date: datetime = None,
    ) -> List[DownloadedInvoice]:
        """
        Run a synchronization - download invoices.

        Args:
            max_invoices: Max invoices to check (default 5 for quick sync).
            start_date: Only download invoices on or after this date.
            end_date: Only download invoices on or before this date.
        """
        self.logger.info(f"Starting sync for {self.PLATFORM_NAME}")

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
                invoices = self.download_invoices(
                    location_id=location["id"],
                    start_date=start_date,
                    end_date=end_date,
                    max_invoices=max_invoices,
                )
                all_invoices.extend(invoices)
                self.logger.info(f"Downloaded {len(invoices)} invoices for this location")

        except Exception as e:
            self.logger.error(f"Error during sync: {e}")
            self.screenshot("error")
            raise

        self.logger.info(f"Full sync complete. Total invoices: {len(all_invoices)}")
        return all_invoices

    def is_session_valid(self) -> bool:
        """
        Check if saved session exists and is still fresh.

        Returns:
            True if session file exists and is within max age, False otherwise
        """
        if not self.session_file.exists():
            self.logger.info("No session file found")
            return False

        age_seconds = time.time() - self.session_file.stat().st_mtime
        max_age_seconds = settings.session_max_age_days * 86400

        if age_seconds > max_age_seconds:
            self.logger.warning(
                f"Session is {age_seconds / 86400:.1f} days old "
                f"(max: {settings.session_max_age_days} days)"
            )
            return False

        self.logger.info(f"Session is {age_seconds / 86400:.1f} days old - still valid")
        return True

    def get_session_age_days(self) -> float:
        """Get the age of the session file in days."""
        if not self.session_file.exists():
            return float('inf')
        age_seconds = time.time() - self.session_file.stat().st_mtime
        return age_seconds / 86400
