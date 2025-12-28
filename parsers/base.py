"""Base parser class for invoice files."""

import hashlib
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List

from storage.database import Invoice


class BaseParser(ABC):
    """Base class for platform-specific invoice parsers."""

    PLATFORM_NAME: str = "base"

    @staticmethod
    def calculate_file_hash(file_path: Path) -> str:
        """Calculate SHA-256 hash of a file for deduplication."""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    @abstractmethod
    def parse(self, file_path: Path) -> List[Invoice]:
        """
        Parse an invoice file and return Invoice objects.

        Args:
            file_path: Path to the invoice file (CSV, PDF, etc.)

        Returns:
            List of Invoice objects extracted from the file
        """
        pass

    @abstractmethod
    def can_parse(self, file_path: Path) -> bool:
        """
        Check if this parser can handle the given file.

        Args:
            file_path: Path to the file to check

        Returns:
            True if this parser can handle the file
        """
        pass
