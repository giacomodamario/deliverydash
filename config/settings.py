import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

# Load .env file
load_dotenv(Path(__file__).parent.parent / ".env")


class DeliverooCredentials:
    """Deliveroo partner portal credentials."""
    email: Optional[str] = os.getenv("DELIVEROO_EMAIL")
    password: Optional[str] = os.getenv("DELIVEROO_PASSWORD")


class GlovoCredentials:
    """Glovo partner portal credentials."""
    email: Optional[str] = os.getenv("GLOVO_EMAIL")
    password: Optional[str] = os.getenv("GLOVO_PASSWORD")


class JustEatCredentials:
    """Just Eat partner portal credentials."""
    email: Optional[str] = os.getenv("JUSTEAT_EMAIL")
    password: Optional[str] = os.getenv("JUSTEAT_PASSWORD")


class Settings:
    """Main application settings."""

    # Paths
    base_dir: Path = Path(__file__).parent.parent
    downloads_dir: Path = base_dir / "data" / "downloads"
    database_path: Path = base_dir / "data" / "invoices.db"
    sessions_dir: Path = base_dir / "data" / "sessions"

    # Browser settings
    headless: bool = False  # Set to True for production
    slow_mo: int = 100  # Milliseconds between actions (helps with debugging)
    timeout: int = 30000  # Default timeout in milliseconds

    # Credentials
    deliveroo = DeliverooCredentials()
    glovo = GlovoCredentials()
    justeat = JustEatCredentials()

    def ensure_directories(self):
        """Create necessary directories if they don't exist."""
        self.downloads_dir.mkdir(parents=True, exist_ok=True)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.sessions_dir.mkdir(parents=True, exist_ok=True)

        # Create platform-specific download directories
        for platform in ["deliveroo", "glovo", "justeat"]:
            (self.downloads_dir / platform).mkdir(exist_ok=True)
