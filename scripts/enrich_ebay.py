"""Enrich market-ready deals with eBay Browse API pricing."""
from __future__ import annotations

import argparse
import json
import logging
import time
from pathlib import Path
from typing import Any

import requests

from ai.product_matcher import build_queries
from lib.ebay_auth import get_valid_token


LOGGER = logging.getLogger(__name__)
EBAY_BROWSE_ENDPOINT = "https://api.ebay.com/buy/browse/v1/item_summary/search"
CACHE_PATH = Path(".cache/ebay_browse_cache.json")
RATE_LIMIT_SLEEP_SECONDS = 0.5
MAX_RETRIES = 5


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description="Enrich market-ready JSON with eBay prices.")
    parser.add_argument(
        "--input",
        default="input/market_ready.json",
        help="Path to market-ready JSON file.",
    )
    parser.add_argument(
        "--output",
        default="output/marketplace.json",
        help="Path to enriched output JSON file.",
    )
    parser.add_argument(
        "--max-ebay-queries",
        type=int,
        default=300,
        help="Maximum number of eBay Browse API queries to perform.",
    )
    return parser.parse_args()


def _load_json_list(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, list):
        raise ValueError(f"Expected list in {path}.")
    entries: list[dict[str, Any]] = []
    for entry in payload:
        if not isinstance(entry, dict):
            raise ValueError(f"Expected object entries in {path}.")
        entries.append(entry)
    return entries


def _load_cache() -> dict[str, float | None]:
    if not CACHE_PATH.exists():
        return {}
    try:
        payload = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        LOGGER.warning("Failed to read eBay cache: %s", exc)
        return {}
    if not isinstance(payload, dict):
        return {}
    cache: dict[str, float | None] = {}
    for key, value in payload.items():
        if not isinstance(key, str):
            continue
        if value is None:
            cache[key] = None
        else:
            try:
                cache[key] = float(value)
            except (TypeError, ValueError):
                cache[key] = None
    return cache


def _write_cache(cache: dict[str, float | None]) -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(cache, indent=2, sort_keys=True), encoding="utf-8")


def _median_price(prices: list[float]) -> float | None:
    if not prices:
        return None
    prices_sorted = sorted(prices)
    mid = len(prices_sorted) // 2
    if len(prices_sorted) % 2 == 1:
        return float(prices_sorted[mid])
    return float((prices_sorted[mid - 1] + prices_sorted[mid]) / 2)


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


def _fetch_browse_price(query: str, token: str) -> float | None:
    headers = {"Authorization": f"Bearer {token}"}
    params = {"q": query, "limit": "20"}
    backoff_seconds = 1.0
    for attempt in range(1, MAX_RETRIES + 1):
        time.sleep(RATE_LIMIT_SLEEP_SECONDS)
        try:
            response = requests.get(
                EBAY_BROWSE_ENDPOINT,
                headers=headers,
                params=params,
                timeout=15,
            )
        except requests.RequestException as exc:
            LOGGER.warning("eBay Browse API request failed: %s", exc)
            return None

        if response.status_code == 429:
            LOGGER.warning("eBay Browse API rate limited (429), retry %s/%s.", attempt, MAX_RETRIES)
            time.sleep(backoff_seconds)
            backoff_seconds *= 2
            continue

        try:
            response.raise_for_status()
        except requests.RequestException as exc:
            LOGGER.warning("eBay Browse API failed: %s", exc)
            return None

        try:
            payload = response.json()
        except ValueError as exc:
            LOGGER.warning("eBay Browse API response parse failed: %s", exc)
            return None

        items = payload.get("itemSummaries", [])
        prices: list[float] = []
        for item in items if isinstance(items, list) else []:
            price = _extract_price(item)
            if price is not None:
                prices.append(price)
        return _median_price(prices)

    LOGGER.warning("eBay Browse API rate limit retries exhausted.")
    return None


def _build_ebay_query(entry: dict[str, Any]) -> str | None:
    deal_payload = entry.get("deal", {})
    if not isinstance(deal_payload, dict):
        return None
    match_payload = build_queries(
        title=str(deal_payload.get("title") or ""),
        brand=deal_payload.get("brand"),
        sku=deal_payload.get("sku"),
        upc=deal_payload.get("upc"),
    )
    return match_payload.get("ebay_query")


def enrich_entries(
    entries: list[dict[str, Any]],
    max_queries: int,
) -> tuple[list[dict[str, Any]], dict[str, float | None]]:
    token = get_valid_token()
    if not token:
        LOGGER.warning("Skipping eBay enrichment: missing OAuth token.")
        return entries, {}

    cache = _load_cache()
    queries_made = 0
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        market_payload = entry.get("market")
        if not isinstance(market_payload, dict):
            market_payload = {}
            entry["market"] = market_payload

        query = _build_ebay_query(entry)
        if not query:
            market_payload["ebay_price"] = None
            continue

        if query in cache:
            market_payload["ebay_price"] = cache[query]
            continue

        if queries_made >= max_queries:
            market_payload["ebay_price"] = None
            continue

        price = _fetch_browse_price(query, token)
        cache[query] = price
        market_payload["ebay_price"] = price
        queries_made += 1

    _write_cache(cache)
    return entries, cache


def write_output(path: Path, payload: list[dict[str, Any]]) -> None:
    """Write enriched payload to disk."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def main() -> None:
    """CLI entrypoint."""
    logging.basicConfig(level=logging.INFO)
    args = parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output)

    entries = _load_json_list(input_path)
    enriched, cache = enrich_entries(entries, args.max_ebay_queries)
    write_output(output_path, enriched)
    print(f"ebay_cache_size={len(cache)} entries={len(enriched)}")


if __name__ == "__main__":
    main()
