"""Enrich market-ready deals with eBay Browse API pricing."""
from __future__ import annotations

import argparse
import json
import logging
import os
import random
import re
import threading
import time
from pathlib import Path
from typing import Any

import requests

from ai.title_normalizer import normalize_title
from core.ct_extractors import normalize_model_number
from lib.ebay_auth import get_valid_token


LOGGER = logging.getLogger(__name__)
EBAY_BROWSE_ENDPOINT = "https://api.ebay.com/buy/browse/v1/item_summary/search"
CACHE_PATH = Path(".cache/ebay_browse_cache.json")
DEFAULT_EBAY_MIN_DELAY_MS = 1200
DEFAULT_EBAY_THROTTLE_SECONDS = 0.2
DEFAULT_EBAY_CONCURRENCY = 1
MAX_RETRIES = 6
CACHE_TTL_SECONDS = 24 * 60 * 60

EBAY_MIN_DELAY_MS = int(os.getenv("EBAY_MIN_DELAY_MS", str(DEFAULT_EBAY_MIN_DELAY_MS)))
EBAY_CONCURRENCY = int(os.getenv("EBAY_CONCURRENCY", str(DEFAULT_EBAY_CONCURRENCY)))
EBAY_THROTTLE_SECONDS = max(
    0.0, float(os.getenv("EBAY_THROTTLE_SECONDS", str(DEFAULT_EBAY_THROTTLE_SECONDS)))
)


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


RATE_LIMITER = RateLimiter(EBAY_CONCURRENCY, EBAY_MIN_DELAY_MS)


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
        default=None,
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


def _load_cache() -> dict[str, dict[str, float | None | list[str] | str]]:
    if not CACHE_PATH.exists():
        return {}
    try:
        payload = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        LOGGER.warning("Failed to read eBay cache: %s", exc)
        return {}
    if not isinstance(payload, dict):
        return {}
    cache: dict[str, dict[str, float | None | list[str] | str]] = {}
    for key, value in payload.items():
        if not isinstance(key, str):
            continue
        if isinstance(value, dict):
            try:
                cached_price = value.get("price")
                cached_ts = float(value.get("ts")) if value.get("ts") is not None else 0.0
                cached_titles = value.get("titles") if isinstance(value.get("titles"), list) else []
                titles = [title for title in cached_titles if isinstance(title, str)]
                cache[key] = {
                    "price": float(cached_price) if cached_price is not None else None,
                    "ts": cached_ts,
                    "titles": titles,
                    "top_image": value.get("top_image") if isinstance(value.get("top_image"), str) else None,
                }
            except (TypeError, ValueError):
                cache[key] = {"price": None, "ts": 0.0, "titles": [], "top_image": None}
        elif value is None:
            cache[key] = {"price": None, "ts": 0.0, "titles": [], "top_image": None}
        else:
            try:
                cache[key] = {"price": float(value), "ts": 0.0, "titles": [], "top_image": None}
            except (TypeError, ValueError):
                cache[key] = {"price": None, "ts": 0.0, "titles": [], "top_image": None}
    return cache


def _write_cache(cache: dict[str, dict[str, float | None | list[str] | str]]) -> None:
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


def _extract_title(item: dict[str, Any]) -> str | None:
    title = item.get("title") if isinstance(item, dict) else None
    if isinstance(title, str) and title.strip():
        return title.strip()
    return None




def _extract_image_url(item: dict[str, Any]) -> str | None:
    image = item.get("image") if isinstance(item, dict) else None
    if not isinstance(image, dict):
        return None
    url = image.get("imageUrl")
    if isinstance(url, str) and url.strip():
        return url.strip()
    return None


def _tokenize_image_url(url: str | None) -> set[str]:
    if not url:
        return set()
    return {
        token
        for token in re.split(r"[^a-z0-9]+", url.lower())
        if len(token) >= 3 and token not in {"https", "http", "www", "com", "jpg", "jpeg", "png", "webp", "img", "image"}
    }


def _images_look_similar(deal_image: str | None, ebay_image: str | None, brand: str | None = None) -> bool:
    deal_tokens = _tokenize_image_url(deal_image)
    ebay_tokens = _tokenize_image_url(ebay_image)
    if not deal_tokens or not ebay_tokens:
        return False

    overlap = deal_tokens & ebay_tokens
    if len(overlap) >= 3:
        return True

    if brand:
        brand_tokens = _tokenize_image_url(brand)
        if brand_tokens and (brand_tokens & overlap):
            return True

    min_len = min(len(deal_tokens), len(ebay_tokens))
    return min_len > 0 and (len(overlap) / min_len) >= 0.45

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


def _resolve_max_queries(max_queries: int | None) -> int:
    env_value = os.getenv("MAX_MARKETPLACE_ITEMS")
    env_value = env_value.strip() if env_value is not None else None
    env_value = env_value if env_value else None

    selected: int | str | None = max_queries
    if selected is None:
        selected = env_value or 300
    elif env_value and selected == 300:
        selected = env_value

    try:
        value = int(selected)
    except (TypeError, ValueError) as exc:
        raise ValueError("max_ebay_queries must be an integer.") from exc
    return max(0, value)


def _fetch_browse_summary(query: str, token: str) -> dict[str, float | None | list[str] | str]:
    headers = {"Authorization": f"Bearer {token}"}
    params = {"q": query, "limit": "20"}
    for attempt in range(1, MAX_RETRIES + 1):
        with RATE_LIMITER:
            try:
                if EBAY_THROTTLE_SECONDS:
                    time.sleep(EBAY_THROTTLE_SECONDS)
                response = requests.get(
                    EBAY_BROWSE_ENDPOINT,
                    headers=headers,
                    params=params,
                    timeout=15,
                )
            except requests.RequestException as exc:
                LOGGER.warning("eBay Browse API request failed: %s", exc)
                return {"price": None, "titles": [], "top_image": None}

        if response.status_code == 429:
            retry_after = _parse_retry_after(response.headers.get("Retry-After"))
            LOGGER.warning("eBay Browse API rate limited (429), retry %s/%s.", attempt, MAX_RETRIES)
            if retry_after is not None:
                time.sleep(retry_after + random.uniform(0, 0.5))
            else:
                _backoff_sleep(attempt)
            continue

        try:
            response.raise_for_status()
        except requests.RequestException as exc:
            LOGGER.warning("eBay Browse API failed: %s", exc)
            return {"price": None, "titles": [], "top_image": None}

        try:
            payload = response.json()
        except ValueError as exc:
            LOGGER.warning("eBay Browse API response parse failed: %s", exc)
            return {"price": None, "titles": [], "top_image": None}

        items = payload.get("itemSummaries", [])
        prices: list[float] = []
        titles: list[str] = []
        top_image: str | None = None
        for item in items if isinstance(items, list) else []:
            price = _extract_price(item)
            if price is not None:
                prices.append(price)
            title = _extract_title(item)
            if title is not None:
                titles.append(title)
            if top_image is None:
                top_image = _extract_image_url(item)
        return {"price": _median_price(prices), "titles": titles, "top_image": top_image}

    LOGGER.warning("eBay Browse API rate limit retries exhausted.")
    return {"price": None, "titles": [], "top_image": None}


def _is_cache_fresh(entry: dict[str, float | None | list[str]], now: float) -> bool:
    ts = entry.get("ts") if entry else None
    if not isinstance(ts, (int, float)):
        return False
    return now - float(ts) < CACHE_TTL_SECONDS


def _normalize_match_text(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"[^A-Z0-9]", "", str(value).upper())


def _has_exact_part_number(part_number: str, title: str) -> bool:
    if not part_number or not title:
        return False
    escaped = re.escape(part_number.strip())
    pattern = re.compile(rf"(?<![A-Za-z0-9]){escaped}(?![A-Za-z0-9])", re.IGNORECASE)
    return bool(pattern.search(title))


def _build_query_context(deal_payload: dict[str, Any]) -> dict[str, str | float | None]:
    brand = deal_payload.get("brand")
    brand_value = brand.strip() if isinstance(brand, str) and brand.strip() else None
    model_number = deal_payload.get("model_number")
    model_number_value = str(model_number).strip() if model_number else None
    model_number_norm = normalize_model_number(model_number_value)
    part_number = deal_payload.get("part_number")
    part_value = str(part_number).strip() if part_number else None

    if model_number_norm:
        query = f"{brand_value} {model_number_value}".strip() if brand_value else model_number_value
        return {
            "query_used": query,
            "match_method": "model_number",
            "base_confidence": 0.85,
            "model_number_norm": model_number_norm,
        }

    if part_value:
        query = f"{brand_value} {part_value}".strip() if brand_value else part_value
        return {
            "query_used": query,
            "match_method": "part_number",
            "base_confidence": 0.70,
            "model_number_norm": None,
        }

    title = deal_payload.get("title") or ""
    normalized_title = normalize_title(str(title))
    query = normalized_title if normalized_title else None
    return {
        "query_used": query,
        "match_method": "title",
        "base_confidence": 0.45,
        "model_number_norm": None,
    }


def _has_direct_model_number(model_number_norm: str | None, ebay_title: str | None) -> bool:
    if not model_number_norm or not ebay_title:
        return False
    normalized_title = _normalize_match_text(ebay_title)
    return model_number_norm in normalized_title


def _has_direct_part_number(part_number: str | None, ebay_title: str | None) -> bool:
    if not part_number or not ebay_title:
        return False
    if _has_exact_part_number(part_number, ebay_title):
        return True
    normalized_part = _normalize_match_text(part_number)
    normalized_title = _normalize_match_text(ebay_title)
    return bool(normalized_part and normalized_part in normalized_title)


def enrich_entries(
    entries: list[dict[str, Any]],
    max_queries: int,
) -> tuple[list[dict[str, Any]], dict[str, dict[str, float | None | list[str] | str]]]:
    token = get_valid_token()
    if not token:
        LOGGER.warning("Skipping eBay enrichment: missing OAuth token.")
        return entries, {}

    cache = _load_cache()
    queries_made = 0
    resolved_max_queries = _resolve_max_queries(max_queries)
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        market_payload = entry.get("market")
        if not isinstance(market_payload, dict):
            market_payload = {}
            entry["market"] = market_payload

        deal_payload = entry.get("deal")
        if not isinstance(deal_payload, dict):
            market_payload["is_confirmed"] = False
            continue

        match_context = _build_query_context(deal_payload)
        query = match_context.get("query_used")
        match_method = match_context.get("match_method")
        base_confidence = match_context.get("base_confidence", 0.0)
        model_number_norm = match_context.get("model_number_norm")
        market_payload["query_used"] = query
        market_payload["match_method"] = match_method
        market_payload["model_number_norm"] = model_number_norm

        ebay_price = None
        titles: list[str] = []
        ebay_image: str | None = None
        if query:
            cache_entry = cache.get(query)
            if cache_entry and _is_cache_fresh(cache_entry, time.time()):
                ebay_price = cache_entry.get("price")
                cached_titles = cache_entry.get("titles")
                titles = cached_titles if isinstance(cached_titles, list) else []
                cached_image = cache_entry.get("top_image")
                ebay_image = cached_image if isinstance(cached_image, str) else None
            elif queries_made < resolved_max_queries:
                summary = _fetch_browse_summary(query, token)
                cache[query] = {
                    "price": summary.get("price"),
                    "titles": summary.get("titles", []),
                    "top_image": summary.get("top_image"),
                    "ts": time.time(),
                }
                ebay_price = summary.get("price")
                titles = summary.get("titles", []) if isinstance(summary, dict) else []
                top_image = summary.get("top_image") if isinstance(summary, dict) else None
                ebay_image = top_image if isinstance(top_image, str) else None
                queries_made += 1
        market_payload["ebay_price"] = ebay_price

        titles = [title for title in titles if isinstance(title, str)]
        ebay_title = titles[0] if titles else None
        part_number = deal_payload.get("part_number")
        part_number_value = str(part_number).strip() if part_number else None
        is_confirmed = False
        has_model_match = _has_direct_model_number(model_number_norm, ebay_title)
        has_part_match = _has_direct_part_number(part_number_value, ebay_title)
        deal_image = deal_payload.get("image") if isinstance(deal_payload.get("image"), str) else None
        brand_value = deal_payload.get("brand") if isinstance(deal_payload.get("brand"), str) else None
        has_image_match = _images_look_similar(deal_image, ebay_image, brand_value)

        market_payload["ebay_title"] = ebay_title
        market_payload["ebay_image"] = ebay_image
        market_payload["has_image_match"] = has_image_match
        current_confidence = market_payload.get("match_confidence") or 0.0
        match_confidence = max(current_confidence, float(base_confidence or 0.0))

        if has_model_match:
            is_confirmed = True
            match_confidence = max(match_confidence, 0.85)
        elif not model_number_norm and has_part_match:
            is_confirmed = True
            match_confidence = max(match_confidence, 0.70)

        if deal_image and ebay_image:
            if has_image_match:
                match_confidence = min(1.0, match_confidence + 0.10)
            elif is_confirmed:
                is_confirmed = False
                match_confidence = min(match_confidence, 0.55)

        if match_method == "title" and not has_model_match and not has_part_match:
            match_confidence = min(match_confidence, 0.60)

        market_payload["is_confirmed"] = is_confirmed
        market_payload["match_confidence"] = match_confidence

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
