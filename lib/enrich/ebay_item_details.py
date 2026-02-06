"""Fetch and normalize eBay item details with a simple file cache."""
from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any

import requests

from lib.ebay_auth import get_valid_token

LOGGER = logging.getLogger(__name__)
EBAY_ITEM_ENDPOINT = "https://api.ebay.com/buy/browse/v1/item/{item_id}"
DEFAULT_CACHE_DIR = Path(os.getenv("EBAY_ITEM_CACHE_DIR", "/tmp/ai_roi_ebay_item_cache"))
CACHE_TTL_SECONDS = 24 * 60 * 60


def _cache_path(item_id: str, cache_dir: Path = DEFAULT_CACHE_DIR) -> Path:
    safe_id = "".join(ch for ch in item_id if ch.isalnum() or ch in {"-", "_"})
    return cache_dir / f"{safe_id}.json"


def _read_cached_item(item_id: str, cache_dir: Path = DEFAULT_CACHE_DIR) -> dict[str, Any] | None:
    path = _cache_path(item_id, cache_dir)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def _write_cached_item(item_id: str, item_payload: dict[str, Any], cache_dir: Path = DEFAULT_CACHE_DIR) -> None:
    path = _cache_path(item_id, cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(item_payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _is_fresh(cached_payload: dict[str, Any], now_ts: float) -> bool:
    cached_at = cached_payload.get("cached_at")
    if not isinstance(cached_at, (int, float)):
        return False
    return (now_ts - float(cached_at)) < CACHE_TTL_SECONDS


def _parse_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _extract_price(price_obj: Any) -> float | None:
    if not isinstance(price_obj, dict):
        return None
    return _parse_float(price_obj.get("value"))


def _extract_image(item_payload: dict[str, Any]) -> str | None:
    image = item_payload.get("image")
    if isinstance(image, dict):
        image_url = image.get("imageUrl")
        if isinstance(image_url, str) and image_url.strip():
            return image_url.strip()
    additional = item_payload.get("additionalImages")
    if isinstance(additional, list):
        for image_obj in additional:
            if isinstance(image_obj, dict):
                image_url = image_obj.get("imageUrl")
                if isinstance(image_url, str) and image_url.strip():
                    return image_url.strip()
    return None


def _normalize_item(item_payload: dict[str, Any]) -> dict[str, Any]:
    seller = item_payload.get("seller") if isinstance(item_payload.get("seller"), dict) else {}
    shipping_opts = item_payload.get("shippingOptions")
    shipping_amount = None
    if isinstance(shipping_opts, list):
        for option in shipping_opts:
            if isinstance(option, dict):
                shipping_amount = _extract_price(option.get("shippingCost"))
                if shipping_amount is not None:
                    break

    return {
        "item_id": item_payload.get("itemId"),
        "title": item_payload.get("title"),
        "item_web_url": item_payload.get("itemWebUrl"),
        "image": _extract_image(item_payload),
        "price": _extract_price(item_payload.get("price")),
        "shipping": shipping_amount,
        "condition": item_payload.get("condition"),
        "seller": {
            "username": seller.get("username"),
            "feedback_percent": _parse_float(seller.get("feedbackPercentage")),
        },
    }


def fetch_ebay_item_details(item_id: str) -> dict[str, Any]:
    """Fetch item details from eBay with cache-first fallback on rate limits."""
    now_ts = time.time()
    cached = _read_cached_item(item_id)
    if cached and _is_fresh(cached, now_ts):
        payload = cached.get("payload") if isinstance(cached.get("payload"), dict) else {}
        return {
            "ok": True,
            "source": "cache",
            "cached_at": cached.get("cached_at"),
            "item": payload,
        }

    token = os.getenv("EBAY_ACCESS_TOKEN") or get_valid_token()
    if not token:
        if cached and isinstance(cached.get("payload"), dict):
            return {
                "ok": True,
                "source": "stale_cache",
                "cached_at": cached.get("cached_at"),
                "warning": "Missing eBay token; returning stale cached payload.",
                "item": cached.get("payload"),
            }
        return {
            "ok": False,
            "error": "missing_token",
            "message": "Missing eBay OAuth token. Set EBAY_ACCESS_TOKEN or configure token refresh.",
        }

    endpoint = EBAY_ITEM_ENDPOINT.format(item_id=item_id)
    headers = {"Authorization": f"Bearer {token}"}
    try:
        response = requests.get(endpoint, headers=headers, timeout=20)
    except requests.RequestException as exc:
        LOGGER.warning("eBay item details request failed: %s", exc)
        if cached and isinstance(cached.get("payload"), dict):
            return {
                "ok": True,
                "source": "stale_cache",
                "cached_at": cached.get("cached_at"),
                "warning": "Network error from eBay API; returning stale cached payload.",
                "item": cached.get("payload"),
            }
        return {
            "ok": False,
            "error": "request_failed",
            "message": "Failed to fetch eBay item details.",
        }

    if response.status_code == 429:
        if cached and isinstance(cached.get("payload"), dict):
            return {
                "ok": True,
                "source": "stale_cache",
                "cached_at": cached.get("cached_at"),
                "warning": "Rate limited by eBay API (429); returning stale cached payload.",
                "item": cached.get("payload"),
            }
        return {
            "ok": False,
            "error": "rate_limited",
            "message": "eBay API rate limited request (429) and no cached payload is available.",
        }

    if response.status_code >= 400:
        return {
            "ok": False,
            "error": "ebay_error",
            "message": f"eBay API returned HTTP {response.status_code}.",
            "details": response.text[:500],
        }

    try:
        raw_payload = response.json()
    except ValueError:
        return {
            "ok": False,
            "error": "invalid_json",
            "message": "eBay API returned invalid JSON payload.",
        }

    if not isinstance(raw_payload, dict):
        return {
            "ok": False,
            "error": "invalid_payload",
            "message": "eBay API payload did not match expected object format.",
        }

    normalized = _normalize_item(raw_payload)
    cached_payload = {"cached_at": now_ts, "payload": normalized}
    _write_cached_item(item_id, cached_payload)
    return {
        "ok": True,
        "source": "api",
        "cached_at": now_ts,
        "item": normalized,
    }
