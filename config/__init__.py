from .logging import setup_logging
from .settings import Settings

settings = Settings()

__all__ = ["settings", "Settings", "setup_logging"]
