"""eBay enrichment helpers."""
from __future__ import annotations

import logging
from statistics import median
from typing import Any

from lib.ebay_auth import get_valid_token

LOGGER = logging.getLogger(__name__)


def _median_price(prices: list[float]) -> float | None:
    if not prices:
        return None
    return float(median(prices))


def _fetch_browse_api(query: str, token: str) -> float | None:
    import requests

    endpoint = "https://api.ebay.com/buy/browse/v1/item_summary/search"
    headers = {"Authorization": f"Bearer {token}"}
    params = {"q": query, "limit": "20"}
    try:
        response = requests.get(endpoint, headers=headers, params=params, timeout=15)
        response.raise_for_status()
        payload = response.json()
        items = payload.get("itemSummaries", [])
        prices: list[float] = []
        for item in items:
            price = _extract_browse_price(item)
            if price is not None:
                prices.append(price)
        return _median_price(prices)
    except requests.RequestException as exc:
        LOGGER.warning("eBay Browse API failed: %s", exc)
        return None
    except ValueError as exc:
        LOGGER.warning("eBay Browse API response parse failed: %s", exc)
        return None


def _extract_browse_price(item: dict[str, Any]) -> float | None:
    price = item.get("price") if isinstance(item, dict) else None
    if not isinstance(price, dict):
        return None
    value = price.get("value")
    try:
        if value is not None:
            return float(value)
    except (TypeError, ValueError):
        return None
    return None


def get_ebay_active_median_price(ebay_query: str | None) -> float | None:
    """Return median price from active eBay listings."""
    if not ebay_query:
        return None

    token = get_valid_token()
    if token:
        return _fetch_browse_api(ebay_query, token)
    return None


def fetch_active_prices(query: str) -> float | None:
    """Fetch median price for active eBay listings using Browse API."""
    if not query:
        return None
    token = get_valid_token()
    if not token:
        LOGGER.warning("Skipping eBay Browse API call: missing OAuth token.")
        return None
    return _fetch_browse_api(query, token)
