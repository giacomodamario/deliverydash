import os
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings


class DeliverooCredentials(BaseSettings):
    """Deliveroo partner portal credentials."""
    email: Optional[str] = None
    password: Optional[str] = None

    class Config:
        env_prefix = "DELIVEROO_"


class GlovoCredentials(BaseSettings):
    """Glovo partner portal credentials."""
    email: Optional[str] = None
    password: Optional[str] = None

    class Config:
        env_prefix = "GLOVO_"


class JustEatCredentials(BaseSettings):
    """Just Eat partner portal credentials."""
    email: Optional[str] = None
    password: Optional[str] = None

    class Config:
        env_prefix = "JUSTEAT_"


class Settings(BaseSettings):
    """Main application settings."""

    # Paths
    base_dir: Path = Path(__file__).parent.parent
    downloads_dir: Path = base_dir / "downloads"
    database_path: Path = base_dir / "data" / "invoices.db"

    # Browser settings
    headless: bool = False  # Set to True for production
    slow_mo: int = 100  # Milliseconds between actions (helps with debugging)
    timeout: int = 30000  # Default timeout in milliseconds

    # Credentials (loaded from environment)
    deliveroo: DeliverooCredentials = DeliverooCredentials()
    glovo: GlovoCredentials = GlovoCredentials()
    justeat: JustEatCredentials = JustEatCredentials()

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    def ensure_directories(self):
        """Create necessary directories if they don't exist."""
        self.downloads_dir.mkdir(parents=True, exist_ok=True)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)

        # Create platform-specific download directories
        for platform in ["deliveroo", "glovo", "justeat"]:
            (self.downloads_dir / platform).mkdir(exist_ok=True)
