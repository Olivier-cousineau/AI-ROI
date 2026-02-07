"""eBay Browse API client with retries and rate limiting."""
from __future__ import annotations

import logging
import os
import random
import threading
import time
from dataclasses import dataclass
from typing import Any

import requests

from lib.ebay_auth import get_valid_token


LOGGER = logging.getLogger(__name__)
EBAY_BROWSE_ENDPOINT = "https://api.ebay.com/buy/browse/v1/item_summary/search"
EBAY_SOLD_ENDPOINT = "https://api.ebay.com/buy/marketplace_insights/v1_beta/item_sales/search"
DEFAULT_EBAY_MIN_DELAY_MS = 500
DEFAULT_EBAY_CONCURRENCY = 3
MAX_RETRIES = 6


def _parse_retry_after(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        return None


def _backoff_sleep(attempt: int) -> None:
    base = min(32.0, 2 ** (attempt - 1))
    jitter = random.uniform(0, 0.5)
    time.sleep(base + jitter)


class RateLimiter:
    def __init__(self, max_concurrency: int, min_delay_ms: int) -> None:
        self._semaphore = threading.Semaphore(max(1, max_concurrency))
        self._min_delay_seconds = max(0, min_delay_ms) / 1000

    def __enter__(self) -> "RateLimiter":
        self._semaphore.acquire()
        return self

    def __exit__(self, exc_type, exc, exc_tb) -> None:
        time.sleep(self._min_delay_seconds)
        self._semaphore.release()


@dataclass
class BrowseCandidate:
    item_id: str
    title: str
    price: float | None
    image: str | None
    item_web_url: str | None
    shipping: float | None
    condition: str | None
    brand: str | None
    upc: str | None
    mpn: str | None


@dataclass
class SoldCandidate:
    item_id: str
    title: str
    price: float | None
    image: str | None
    item_web_url: str | None
    shipping: float | None
    condition: str | None
    brand: str | None
    upc: str | None
    mpn: str | None
    sold_date: str | None


def _extract_specifics(item: dict[str, Any]) -> dict[str, str]:
    specifics = {}
    raw = item.get("itemSpecifics")
    if isinstance(raw, list):
        for entry in raw:
            if not isinstance(entry, dict):
                continue
            name = entry.get("name")
            values = entry.get("values")
            if not isinstance(name, str):
                continue
            if isinstance(values, list) and values:
                value = values[0]
                if isinstance(value, str):
                    specifics[name.lower()] = value
            elif isinstance(values, str):
                specifics[name.lower()] = values
    return specifics


def _extract_price(item: dict[str, Any]) -> float | None:
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


def _extract_shipping(item: dict[str, Any]) -> float | None:
    shipping_options = item.get("shippingOptions")
    if isinstance(shipping_options, list) and shipping_options:
        option = shipping_options[0]
        if isinstance(option, dict):
            shipping_cost = option.get("shippingCost")
            if isinstance(shipping_cost, dict):
                value = shipping_cost.get("value")
                try:
                    if value is not None:
                        return float(value)
                except (TypeError, ValueError):
                    return None
    return None


def _extract_image_url(item: dict[str, Any]) -> str | None:
    image = item.get("image") if isinstance(item, dict) else None
    if not isinstance(image, dict):
        return None
    url = image.get("imageUrl")
    if isinstance(url, str) and url.strip():
        return url.strip()
    return None


def _extract_sold_price(item: dict[str, Any]) -> float | None:
    price = item.get("transactionPrice") if isinstance(item, dict) else None
    if not isinstance(price, dict):
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


class EbayBrowseClient:
    def __init__(self, marketplace_id: str | None = None) -> None:
        self.marketplace_id = marketplace_id or os.getenv("EBAY_MARKETPLACE_ID", "EBAY_CA")
        min_delay = int(os.getenv("EBAY_MIN_DELAY_MS", str(DEFAULT_EBAY_MIN_DELAY_MS)))
        concurrency = int(os.getenv("EBAY_CONCURRENCY", str(DEFAULT_EBAY_CONCURRENCY)))
        self._rate_limiter = RateLimiter(concurrency, min_delay)

    def search_items(
        self,
        query: str,
        limit: int = 20,
        condition: str | None = None,
    ) -> list[BrowseCandidate]:
        token = get_valid_token()
        if not token:
            LOGGER.warning("Missing eBay OAuth token for Browse API.")
            return []
        headers = {"Authorization": f"Bearer {token}"}
        params = {
            "q": query,
            "limit": str(min(max(limit, 1), 50)),
            "marketplace_id": self.marketplace_id,
        }
        if condition:
            params["filter"] = f"conditions:{condition}"

        for attempt in range(1, MAX_RETRIES + 1):
            with self._rate_limiter:
                try:
                    response = requests.get(
                        EBAY_BROWSE_ENDPOINT,
                        headers=headers,
                        params=params,
                        timeout=20,
                    )
                except requests.RequestException as exc:
                    LOGGER.warning("eBay Browse API request failed: %s", exc)
                    return []

            if response.status_code == 429:
                retry_after = _parse_retry_after(response.headers.get("Retry-After"))
                LOGGER.warning("eBay Browse API rate limited (429), retry %s/%s.", attempt, MAX_RETRIES)
                if retry_after is not None:
                    time.sleep(retry_after + random.uniform(0, 0.5))
                else:
                    _backoff_sleep(attempt)
                continue

            if 500 <= response.status_code < 600:
                LOGGER.warning("eBay Browse API server error (%s).", response.status_code)
                _backoff_sleep(attempt)
                continue

            try:
                response.raise_for_status()
            except requests.RequestException as exc:
                LOGGER.warning("eBay Browse API failed: %s", exc)
                return []

            try:
                payload = response.json()
            except ValueError as exc:
                LOGGER.warning("eBay Browse API response parse failed: %s", exc)
                return []

            items = payload.get("itemSummaries", [])
            candidates: list[BrowseCandidate] = []
            for item in items if isinstance(items, list) else []:
                if not isinstance(item, dict):
                    continue
                specifics = _extract_specifics(item)
                brand = specifics.get("brand") or item.get("brand")
                upc = specifics.get("upc") or specifics.get("gtin")
                mpn = specifics.get("mpn")
                gtin = item.get("gtin")
                if not upc and isinstance(gtin, list) and gtin:
                    upc = gtin[0]
                candidates.append(
                    BrowseCandidate(
                        item_id=str(item.get("itemId", "")).strip(),
                        title=str(item.get("title", "")).strip(),
                        price=_extract_price(item),
                        image=_extract_image_url(item),
                        item_web_url=item.get("itemWebUrl"),
                        shipping=_extract_shipping(item),
                        condition=item.get("condition"),
                        brand=str(brand).strip() if isinstance(brand, str) else None,
                        upc=str(upc).strip() if isinstance(upc, str) else None,
                        mpn=str(mpn).strip() if isinstance(mpn, str) else None,
                    )
                )
            return candidates

        LOGGER.warning("eBay Browse API rate limit retries exhausted.")
        return []

    def search_sold_items(
        self,
        query: str,
        limit: int = 20,
        days: int = 30,
    ) -> list[SoldCandidate]:
        token = get_valid_token()
        if not token:
            LOGGER.warning("Missing eBay OAuth token for Marketplace Insights API.")
            return []
        headers = {"Authorization": f"Bearer {token}"}
        params: dict[str, str] = {
            "q": query,
            "limit": str(min(max(limit, 1), 50)),
            "marketplace_id": self.marketplace_id,
        }

        def _request(with_date_filter: bool) -> requests.Response | None:
            if with_date_filter:
                from datetime import datetime, timedelta, timezone

                end = datetime.now(timezone.utc)
                start = end - timedelta(days=days)
                params["filter"] = f"transactionDate:[{start.isoformat()}..{end.isoformat()}]"
            for attempt in range(1, MAX_RETRIES + 1):
                with self._rate_limiter:
                    try:
                        response = requests.get(
                            EBAY_SOLD_ENDPOINT,
                            headers=headers,
                            params=params,
                            timeout=20,
                        )
                    except requests.RequestException as exc:
                        LOGGER.warning("eBay sold API request failed: %s", exc)
                        return None

                if response.status_code == 429:
                    retry_after = _parse_retry_after(response.headers.get("Retry-After"))
                    LOGGER.warning("eBay sold API rate limited (429), retry %s/%s.", attempt, MAX_RETRIES)
                    if retry_after is not None:
                        time.sleep(retry_after + random.uniform(0, 0.5))
                    else:
                        _backoff_sleep(attempt)
                    continue

                if 500 <= response.status_code < 600:
                    LOGGER.warning("eBay sold API server error (%s).", response.status_code)
                    _backoff_sleep(attempt)
                    continue

                return response
            return None

        response = _request(with_date_filter=True)
        if response is None:
            return []
        if response.status_code == 400 and "filter" in params:
            params.pop("filter", None)
            response = _request(with_date_filter=False)
            if response is None:
                return []

        try:
            response.raise_for_status()
        except requests.RequestException as exc:
            LOGGER.warning("eBay sold API failed: %s", exc)
            return []

        try:
            payload = response.json()
        except ValueError as exc:
            LOGGER.warning("eBay sold API response parse failed: %s", exc)
            return []

        items = payload.get("itemSales", [])
        candidates: list[SoldCandidate] = []
        for item in items if isinstance(items, list) else []:
            if not isinstance(item, dict):
                continue
            specifics = _extract_specifics(item)
            brand = specifics.get("brand") or item.get("brand")
            upc = specifics.get("upc") or specifics.get("gtin")
            mpn = specifics.get("mpn")
            gtin = item.get("gtin")
            if not upc and isinstance(gtin, list) and gtin:
                upc = gtin[0]
            candidates.append(
                SoldCandidate(
                    item_id=str(item.get("itemId", "")).strip(),
                    title=str(item.get("title", "")).strip(),
                    price=_extract_sold_price(item),
                    image=_extract_image_url(item),
                    item_web_url=item.get("itemWebUrl"),
                    shipping=_extract_shipping(item),
                    condition=item.get("condition"),
                    brand=str(brand).strip() if isinstance(brand, str) else None,
                    upc=str(upc).strip() if isinstance(upc, str) else None,
                    mpn=str(mpn).strip() if isinstance(mpn, str) else None,
                    sold_date=item.get("transactionDate") if isinstance(item.get("transactionDate"), str) else None,
                )
            )
        return candidates
