"""Application settings."""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    """Runtime configuration settings."""

    app_name: str = "AI-ROI"
    log_level: str = "INFO"

    @classmethod
    def from_env(cls) -> "Settings":
        """Load settings from environment variables."""
        return cls(
            app_name=os.getenv("APP_NAME", cls.app_name),
            log_level=os.getenv("LOG_LEVEL", cls.log_level),
        )
