"""Amazon PA-API enrichment helpers."""
from __future__ import annotations

import logging
import os


LOGGER = logging.getLogger(__name__)


def _has_credentials() -> bool:
    return all(
        [
            os.getenv("AMAZON_ACCESS_KEY"),
            os.getenv("AMAZON_SECRET"),
            os.getenv("AMAZON_PARTNER_TAG"),
        ]
    )


def get_amazon_price(amazon_query: str | None) -> float | None:
    """Return the current Amazon price using PA-API when configured."""
    if not amazon_query:
        return None
    if not _has_credentials():
        return None
    LOGGER.warning("Amazon PA-API integration is not implemented yet. TODO: fetch price.")
    return None
