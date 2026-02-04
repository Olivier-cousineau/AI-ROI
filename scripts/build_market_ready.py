"""Build market-ready dataset with optional marketplace enrichment."""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import argparse
import json
from typing import Any

from ai.product_matcher import build_queries
from ai.title_normalizer import normalize_title
from core.ct_extractors import extract_part_number
from core.keying import make_deal_key


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description="Build market-ready JSON dataset.")
    parser.add_argument("--deals", required=True, help="Path to deals JSON file.")
    parser.add_argument("--keepa", required=True, help="Path to Keepa sales JSON file.")
    parser.add_argument("--out", required=True, help="Path to output JSON file.")
    parser.add_argument(
        "--max-marketplace-items",
        type=int,
        default=None,
        help="Maximum number of marketplace items to keep after filtering.",
    )
    return parser.parse_args()


def _coerce_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        cleaned = value.strip()
        if not cleaned:
            return None
        try:
            return float(cleaned.replace(",", ""))
        except ValueError:
            return None
    return None


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


def _build_keepa_index(entries: list[dict[str, Any]]) -> dict[str, int]:
    index: dict[str, int] = {}
    for entry in entries:
        key = entry.get("key")
        sales = entry.get("sales_per_month")
        if isinstance(key, str) and key and isinstance(sales, int):
            index[key] = sales
    return index


def _coerce_discount_pct(price_sale: float | None, price_regular: float | None) -> float | None:
    if price_sale is None or price_regular in (None, 0):
        return None
    return round((1 - price_sale / price_regular) * 100, 2)


def _is_sorted_by_discount(entries: list[dict[str, Any]]) -> bool:
    last_discount: float | None = None
    for entry in entries:
        deal = entry.get("deal", {})
        if not isinstance(deal, dict):
            return False
        discount = deal.get("discount_pct")
        if not isinstance(discount, (int, float)):
            return False
        discount_value = float(discount)
        if last_discount is not None and discount_value > last_discount:
            return False
        last_discount = discount_value
    return True


DEFAULT_MAX_MARKETPLACE_ITEMS = 300


def _apply_marketplace_cap(
    entries: list[dict[str, Any]],
    max_marketplace_items: int,
) -> list[dict[str, Any]]:
    filtered = []
    for entry in entries:
        deal = entry.get("deal", {})
        if not isinstance(deal, dict):
            continue
        discount = deal.get("discount_pct")
        if isinstance(discount, (int, float)) and discount >= 60:
            filtered.append(entry)

    if not _is_sorted_by_discount(filtered):
        filtered = sorted(
            filtered,
            key=lambda item: item["deal"]["discount_pct"],
            reverse=True,
        )

    if max_marketplace_items > 0:
        filtered = filtered[:max_marketplace_items]
    return filtered


def build_market_ready(
    deals: list[dict[str, Any]],
    keepa_index: dict[str, int],
    max_marketplace_items: int | None = DEFAULT_MAX_MARKETPLACE_ITEMS,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Build the market-ready list and stats."""
    env_value = os.getenv("MAX_MARKETPLACE_ITEMS")
    use_env = env_value is not None and (
        max_marketplace_items is None or max_marketplace_items == DEFAULT_MAX_MARKETPLACE_ITEMS
    )
    max_items_source: int | str | None
    if use_env:
        max_items_source = env_value
    else:
        max_items_source = max_marketplace_items

    if max_items_source is None:
        max_items_source = DEFAULT_MAX_MARKETPLACE_ITEMS

    try:
        max_items = int(max_items_source)
    except (TypeError, ValueError) as exc:
        raise ValueError("max_marketplace_items must be an integer.") from exc

    if max_items < 1:
        max_items = 1

    output: list[dict[str, Any]] = []
    count_with_keepa_sales = 0

    for deal in deals:
        if not isinstance(deal, dict):
            raise ValueError("Each deal entry must be an object.")
        title = deal.get("title") or deal.get("name") or deal.get("productName") or "Unknown"
        url = deal.get("url") or deal.get("link")
        image = deal.get("image") or deal.get("imageUrl")
        price_sale = (
            deal.get("price_sale")
            if deal.get("price_sale") is not None
            else deal.get("salePrice")
            if deal.get("salePrice") is not None
            else deal.get("price")
        )
        price_regular = (
            deal.get("price_regular")
            if deal.get("price_regular") is not None
            else deal.get("regularPrice")
            if deal.get("regularPrice") is not None
            else deal.get("wasPrice")
        )
        price_sale_float = _coerce_float(price_sale)
        price_regular_float = _coerce_float(price_regular)
        discount_pct = deal.get("discount_pct")
        if not isinstance(discount_pct, (int, float)):
            discount_pct = _coerce_discount_pct(price_sale_float, price_regular_float)

        part_number = extract_part_number(deal)
        sku = deal.get("sku") or part_number
        normalized_title = normalize_title(title) if isinstance(title, str) else ""
        key = make_deal_key("Canadian Tire", sku, url, normalized_title)

        match_payload = build_queries(
            title=title if isinstance(title, str) else "",
            brand=deal.get("brand"),
            sku=sku,
            upc=deal.get("upc"),
        )

        keepa_sales = keepa_index.get(key)
        if keepa_sales is not None:
            count_with_keepa_sales += 1

        output.append(
            {
                "deal": {
                    "title": title,
                    "key": key,
                    "part_number": part_number,
                    "price_sale": price_sale_float,
                    "price_regular": price_regular_float,
                    "discount_pct": discount_pct,
                    "source": "Canadian Tire",
                    "sku": sku,
                    "url": url,
                    "image": image,
                    "brand": deal.get("brand"),
                    "upc": deal.get("upc"),
                },
                "market": {
                    "amazon_price": None,
                    "ebay_price": None,
                    "match_confidence": match_payload.get("confidence", 0.0),
                },
                "keepa": {
                    "sales_per_month": keepa_sales,
                },
            }
        )

    capped_output = _apply_marketplace_cap(output, max_items)
    stats = {
        "count_total": len(deals),
        "count_after_filter": len(capped_output),
        "count_with_keepa_sales": count_with_keepa_sales,
    }
    return capped_output, stats


def write_output(path: Path, payload: list[dict[str, Any]]) -> None:
    """Write market-ready payload to disk."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def main() -> None:
    """CLI entrypoint."""
    args = parse_args()
    deals_path = Path(args.deals)
    keepa_path = Path(args.keepa)
    output_path = Path(args.out)

    deals = _load_json_list(deals_path)
    keepa_entries = _load_json_list(keepa_path)
    keepa_index = _build_keepa_index(keepa_entries)
    market_ready, stats = build_market_ready(deals, keepa_index, args.max_marketplace_items)
    write_output(output_path, market_ready)

    print(
        "total={count_total} after_filter={count_after_filter} with_keepa_sales={count_with_keepa_sales}".format(
            **stats
        )
    )


if __name__ == "__main__":
    main()
