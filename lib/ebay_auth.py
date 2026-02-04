"""eBay OAuth token management."""
from __future__ import annotations

import json
import logging
import subprocess
import sys
import time
from pathlib import Path


LOGGER = logging.getLogger(__name__)
CACHE_PATH = Path(".cache/ebay_token.json")
REFRESH_BUFFER_SECONDS = 60


def _read_cache() -> dict[str, object] | None:
    if not CACHE_PATH.exists():
        return None
    try:
        return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        LOGGER.warning("Failed to read eBay token cache: %s", exc)
        return None


def _is_valid(cache: dict[str, object]) -> bool:
    access_token = cache.get("access_token")
    expires_at = cache.get("expires_at")
    if not access_token or not expires_at:
        return False
    try:
        return int(expires_at) - REFRESH_BUFFER_SECONDS > int(time.time())
    except (TypeError, ValueError):
        return False


def _refresh_token() -> None:
    try:
        subprocess.run(
            [sys.executable, "scripts/get_ebay_token.py"],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as exc:
        LOGGER.warning("Failed to execute eBay token fetch script: %s", exc)


def get_valid_token() -> str | None:
    """Return a valid eBay OAuth token, refreshing when needed."""
    cache = _read_cache()
    if cache and _is_valid(cache):
        return str(cache.get("access_token"))

    _refresh_token()
    cache = _read_cache()
    if cache and _is_valid(cache):
        return str(cache.get("access_token"))

    LOGGER.warning("No valid eBay OAuth token available.")
    return None
