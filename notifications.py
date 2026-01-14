#!/usr/bin/env python3
"""Notification utilities for delivery-analytics sync."""

import os
import time
import logging
from typing import Optional

import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)


def send_slack_notification(
    message: str,
    is_error: bool = False,
    title: Optional[str] = None
) -> bool:
    """
    Send a notification to Slack via webhook.

    Args:
        message: The message body
        is_error: If True, shows as red/error styling
        title: Optional custom title

    Returns:
        True if sent successfully, False otherwise
    """
    webhook_url = os.getenv("SLACK_WEBHOOK_URL")

    if not webhook_url:
        logger.warning("SLACK_WEBHOOK_URL not configured, skipping notification")
        return False

    # Determine styling
    if is_error:
        color = "#ff0000"  # Red
        default_title = "Delivery Sync Failed"
        emoji = ":x:"
    else:
        color = "#36a64f"  # Green
        default_title = "Delivery Sync Complete"
        emoji = ":white_check_mark:"

    title = title or default_title

    payload = {
        "attachments": [{
            "color": color,
            "title": f"{emoji} {title}",
            "text": message,
            "footer": "delivery-analytics",
            "ts": int(time.time())
        }]
    }

    try:
        response = requests.post(webhook_url, json=payload, timeout=10)
        response.raise_for_status()
        logger.info(f"Slack notification sent: {title}")
        return True
    except requests.RequestException as e:
        logger.error(f"Failed to send Slack notification: {e}")
        return False


def send_sync_success(
    platform: str,
    files_downloaded: int,
    orders_imported: int,
    duration_seconds: float
) -> bool:
    """Send a success notification for a completed sync."""
    message = (
        f"*Platform:* {platform}\n"
        f"*Files downloaded:* {files_downloaded}\n"
        f"*Orders imported:* {orders_imported}\n"
        f"*Duration:* {duration_seconds:.1f}s"
    )
    return send_slack_notification(message, is_error=False)


def send_sync_failure(
    platform: str,
    error_message: str,
    stage: str = "unknown"
) -> bool:
    """Send a failure notification for a failed sync."""
    message = (
        f"*Platform:* {platform}\n"
        f"*Stage:* {stage}\n"
        f"*Error:* {error_message}"
    )
    return send_slack_notification(message, is_error=True)


def send_reauth_needed(
    platform: str,
    reason: str = "Session expired"
) -> bool:
    """
    Send a notification that manual re-authentication is required.

    This is sent when API sync fails due to invalid/expired session.
    """
    message = (
        f"*Platform:* {platform.upper()}\n"
        f"*Reason:* {reason}\n"
        f"*Action Required:* Manual login needed\n\n"
        f"Run: `python glovo_manual_login.py`"
    )
    return send_slack_notification(
        message,
        is_error=True,
        title=f"{platform.upper()} Re-Authentication Required"
    )


if __name__ == "__main__":
    # Test notifications
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "test":
        print("Testing Slack notification...")
        success = send_slack_notification(
            "This is a test notification from delivery-analytics",
            is_error=False,
            title="Test Notification"
        )
        if success:
            print("Notification sent successfully!")
        else:
            print("Failed to send notification. Check SLACK_WEBHOOK_URL in .env")
    else:
        print("Usage: python notifications.py test")
