"""eBay enrichment helpers."""
from __future__ import annotations

import logging
import os
from statistics import median
from typing import Any


LOGGER = logging.getLogger(__name__)


def _get_app_id() -> str | None:
    return os.getenv("EBAY_APP_ID") or os.getenv("EBAY_APPID")


def _get_oauth_token() -> str | None:
    return os.getenv("EBAY_OAUTH_TOKEN") or os.getenv("EBAY_TOKEN")


def _median_price(prices: list[float]) -> float | None:
    if not prices:
        return None
    return float(median(prices))


def _fetch_finding_api(query: str, app_id: str) -> float | None:
    import requests

    endpoint = "https://svcs.ebay.com/services/search/FindingService/v1"
    params = {
        "OPERATION-NAME": "findItemsByKeywords",
        "SERVICE-VERSION": "1.0.0",
        "SECURITY-APPNAME": app_id,
        "RESPONSE-DATA-FORMAT": "JSON",
        "REST-PAYLOAD": "true",
        "keywords": query,
        "paginationInput.entriesPerPage": "20",
    }
    try:
        response = requests.get(endpoint, params=params, timeout=15)
        response.raise_for_status()
        payload = response.json()
        search_result = (
            payload.get("findItemsByKeywordsResponse", [{}])[0].get("searchResult", [{}])[0]
        )
        items = search_result.get("item", []) if isinstance(search_result, dict) else []
        prices: list[float] = []
        for item in items:
            selling_status = item.get("sellingStatus", [{}])[0]
            current_price = selling_status.get("currentPrice", [{}])[0]
            value = current_price.get("__value__")
            try:
                if value is not None:
                    prices.append(float(value))
            except (TypeError, ValueError):
                continue
        return _median_price(prices)
    except requests.RequestException as exc:
        LOGGER.warning("eBay Finding API failed: %s", exc)
        return None
    except ValueError as exc:
        LOGGER.warning("eBay Finding API response parse failed: %s", exc)
        return None


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
    app_id = _get_app_id()
    token = _get_oauth_token()
    if token:
        return _fetch_browse_api(ebay_query, token)
    if app_id:
        return _fetch_finding_api(ebay_query, app_id)
    return None
