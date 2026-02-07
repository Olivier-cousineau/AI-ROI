"""Enrich market-ready deals with eBay Browse API pricing."""
from __future__ import annotations

import argparse
import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Any

from ai.ebay_matcher import build_search_plan, match_ebay_candidates
from lib.enrich.ebay_browse_client import EbayBrowseClient


LOGGER = logging.getLogger(__name__)
CACHE_PATH = Path(".cache/ebay_browse_cache.json")
DEFAULT_EBAY_THROTTLE_SECONDS = 0.2
CACHE_TTL_SECONDS = 24 * 60 * 60

EBAY_THROTTLE_SECONDS = max(
    0.0, float(os.getenv("EBAY_THROTTLE_SECONDS", str(DEFAULT_EBAY_THROTTLE_SECONDS)))
)


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
                cached_ts = float(value.get("ts")) if value.get("ts") is not None else 0.0
                cached_items = value.get("items") if isinstance(value.get("items"), list) else []
                items = [item for item in cached_items if isinstance(item, dict)]
                cache[key] = {
                    "ts": cached_ts,
                    "items": items,
                }
            except (TypeError, ValueError):
                cache[key] = {"ts": 0.0, "items": []}
        elif value is None:
            cache[key] = {"ts": 0.0, "items": []}
        else:
            cache[key] = {"ts": 0.0, "items": []}
    return cache


def _write_cache(cache: dict[str, dict[str, float | None | list[str] | str]]) -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(cache, indent=2, sort_keys=True), encoding="utf-8")


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


def _is_cache_fresh(entry: dict[str, float | None | list[str]], now: float) -> bool:
    ts = entry.get("ts") if entry else None
    if not isinstance(ts, (int, float)):
        return False
    return now - float(ts) < CACHE_TTL_SECONDS


def enrich_entries(
    entries: list[dict[str, Any]],
    max_queries: int,
) -> tuple[list[dict[str, Any]], dict[str, dict[str, float | None | list[str] | str]]]:
    browse_client = EbayBrowseClient()
    cache = _load_cache()
    queries_made = 0
    resolved_max_queries = _resolve_max_queries(max_queries)
    stats = {
        "total": 0,
        "searched": 0,
        "matched": 0,
        "ambiguous": 0,
        "unmatched_by_reason": {},
    }
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        stats["total"] += 1
        market_payload = entry.get("market")
        if not isinstance(market_payload, dict):
            market_payload = {}
            entry["market"] = market_payload

        deal_payload = entry.get("deal")
        if not isinstance(deal_payload, dict):
            market_payload["is_confirmed"] = False
            continue

        plan = build_search_plan(deal_payload)
        best_result = None
        for context in plan:
            query = context.get("query")
            pass_label = context.get("pass") or "C"
            if not query:
                continue
            market_payload["query_used"] = query
            market_payload["match_method"] = pass_label
            cache_entry = cache.get(query)
            candidates: list[dict[str, Any]] = []
            if cache_entry and _is_cache_fresh(cache_entry, time.time()):
                cached_items = cache_entry.get("items")
                if isinstance(cached_items, list):
                    candidates = [item for item in cached_items if isinstance(item, dict)]
            elif queries_made < resolved_max_queries:
                stats["searched"] += 1
                if EBAY_THROTTLE_SECONDS:
                    time.sleep(EBAY_THROTTLE_SECONDS)
                raw_candidates = browse_client.search_items(query, limit=20, condition="NEW")
                candidates = [candidate.__dict__ for candidate in raw_candidates]
                cache[query] = {"items": candidates, "ts": time.time()}
                queries_made += 1

            result = match_ebay_candidates(deal_payload, candidates, pass_label, query)
            best_result = result
            if result.status == "matched":
                break
            if result.status == "ambiguous":
                break

        if best_result is None:
            continue

        market_payload["match_confidence"] = best_result.confidence
        market_payload["match_reason_codes"] = best_result.reason_codes
        market_payload["match_signals"] = {
            "brand_match": best_result.signals.brand_match,
            "model_match": best_result.signals.model_match,
            "model_exact": best_result.signals.model_exact,
            "title_similarity": best_result.signals.title_similarity,
            "upc_match": best_result.signals.upc_match,
            "image_match": best_result.signals.image_match,
            "image_match_score": best_result.signals.image_match_score,
        }

        if best_result.status == "matched" and best_result.candidate:
            candidate = best_result.candidate
            market_payload["is_confirmed"] = True
            market_payload["ebay_item_id"] = candidate.get("item_id")
            market_payload["ebay_item_web_url"] = candidate.get("item_web_url")
            market_payload["ebay_title"] = candidate.get("title")
            market_payload["ebay_price"] = candidate.get("price")
            market_payload["ebay_shipping"] = candidate.get("shipping")
            market_payload["ebay_condition"] = candidate.get("condition")
            market_payload["ebay_image"] = candidate.get("image")
            stats["matched"] += 1
        elif best_result.status == "ambiguous":
            market_payload["is_confirmed"] = False
            stats["ambiguous"] += 1
        else:
            market_payload["is_confirmed"] = False
            reason = best_result.reason_codes[0] if best_result.reason_codes else "unmatched"
            stats["unmatched_by_reason"][reason] = stats["unmatched_by_reason"].get(reason, 0) + 1
            market_payload["ebay_price"] = None

    _write_cache(cache)
    LOGGER.info(
        "ebay_match totals=%s searched=%s matched=%s ambiguous=%s unmatched=%s",
        stats["total"],
        stats["searched"],
        stats["matched"],
        stats["ambiguous"],
        stats["unmatched_by_reason"],
    )
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
