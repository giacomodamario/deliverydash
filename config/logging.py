"""Centralized logging configuration for delivery-analytics."""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_DIR = Path("/var/log/delivery-analytics")

CONSOLE_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
CONSOLE_DATE_FORMAT = "%H:%M:%S"

FILE_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
FILE_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging(clear_handlers: bool = True) -> None:
    """
    Configure logging with both console and file output.

    Args:
        clear_handlers: If True, clears existing handlers to avoid duplicates.
    """
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    if clear_handlers:
        root_logger.handlers.clear()

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(
        logging.Formatter(CONSOLE_FORMAT, datefmt=CONSOLE_DATE_FORMAT)
    )

    file_formatter = logging.Formatter(FILE_FORMAT, datefmt=FILE_DATE_FORMAT)

    file_handler = RotatingFileHandler(
        LOG_DIR / "sync.log",
        maxBytes=10_000_000,
        backupCount=4
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(file_formatter)

    error_handler = RotatingFileHandler(
        LOG_DIR / "error.log",
        maxBytes=5_000_000,
        backupCount=4
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(file_formatter)

    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(error_handler)
