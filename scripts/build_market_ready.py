"""Build market-ready dataset with optional marketplace enrichment."""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import argparse
import json
from collections import Counter
from typing import Any

from ai.title_normalizer import normalize_title
from core.ct_extractors import extract_model_number, extract_part_number, normalize_model_number
from core.keying import make_deal_key


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description="Build market-ready JSON dataset.")
    parser.add_argument("--deals", required=True, help="Path to deals JSON file.")
    parser.add_argument("--out", required=True, help="Path to output JSON file.")
    parser.add_argument(
        "--store-slug",
        default=os.getenv("CT_STORE_SLUG"),
        help="Limit processing to a single store slug (ex: laval-qc).",
    )
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


def _extract_store_slug(deal: dict[str, Any]) -> str | None:
    store_payload = deal.get("store") if isinstance(deal.get("store"), dict) else {}
    candidates = (
        deal.get("store_slug"),
        deal.get("storeSlug"),
        store_payload.get("slug"),
        store_payload.get("store_slug"),
    )
    for value in candidates:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _coerce_discount_pct(price_sale: float | None, price_regular: float | None) -> float | None:
    if price_sale is None or price_regular in (None, 0):
        return None
    return round((1 - price_sale / price_regular) * 100, 2)


DEFAULT_MAX_MARKETPLACE_ITEMS = 3000


def _apply_marketplace_cap(
    entries: list[dict[str, Any]],
    max_marketplace_items: int,
) -> list[dict[str, Any]]:
    if max_marketplace_items > 0:
        return entries[:max_marketplace_items]
    return entries


def _resolve_max_marketplace_items(max_marketplace_items: int | None) -> int:
    env_value = os.getenv("MAX_MARKETPLACE_ITEMS")
    env_value = env_value.strip() if env_value is not None else None
    env_value = env_value if env_value else None

    selected: int | str | None = max_marketplace_items
    if selected is None:
        selected = env_value or DEFAULT_MAX_MARKETPLACE_ITEMS
    elif env_value and selected == DEFAULT_MAX_MARKETPLACE_ITEMS:
        selected = env_value

    try:
        max_items = int(selected)
    except (TypeError, ValueError) as exc:
        raise ValueError("max_marketplace_items must be an integer.") from exc

    if max_items < 1:
        max_items = DEFAULT_MAX_MARKETPLACE_ITEMS

    return max_items


def _is_out_of_stock(deal: dict[str, Any]) -> bool:
    def _string_status(value: str) -> bool | None:
        lowered = value.strip().lower()
        if not lowered:
            return None
        out_tokens = (
            "out of stock",
            "sold out",
            "unavailable",
            "not available",
            "épuisé",
            "rupture",
        )
        in_tokens = ("in stock", "available", "en stock", "disponible")
        if any(token in lowered for token in out_tokens):
            return False
        if any(token in lowered for token in in_tokens):
            return True
        return None

    def _interpret(value: Any) -> bool | None:
        if value is None:
            return None
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return value > 0
        if isinstance(value, str):
            return _string_status(value)
        if isinstance(value, dict):
            for key in ("available", "in_stock", "inStock", "is_in_stock", "status"):
                if key in value:
                    return _interpret(value.get(key))
        return None

    candidates = [
        deal.get("availability"),
        deal.get("availability_status"),
        deal.get("availabilityStatus"),
        deal.get("stock_status"),
        deal.get("stockStatus"),
        deal.get("inventory_status"),
        deal.get("in_stock"),
        deal.get("inStock"),
        deal.get("is_in_stock"),
        deal.get("available"),
        deal.get("stock"),
        deal.get("qty"),
        deal.get("quantity"),
    ]

    for value in candidates:
        interpreted = _interpret(value)
        if interpreted is None:
            continue
        return not interpreted
    return False


def build_market_ready(
    deals: list[dict[str, Any]],
    max_marketplace_items: int | None = DEFAULT_MAX_MARKETPLACE_ITEMS,
    store_slug: str | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Build the market-ready list and stats."""
    max_items = _resolve_max_marketplace_items(max_marketplace_items)
    target_slug = store_slug.strip() if isinstance(store_slug, str) else None

    output: list[dict[str, Any]] = []
    dropped = Counter()

    for deal in deals:
        if not isinstance(deal, dict):
            dropped["invalid_entry"] += 1
            continue

        if _is_out_of_stock(deal):
            dropped["out_of_stock"] += 1
            continue

        deal_store_slug = _extract_store_slug(deal)
        if target_slug and deal_store_slug != target_slug:
            dropped["store_slug_mismatch"] += 1
            continue

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

        if price_sale_float is None:
            dropped["no_price"] += 1
            continue
        if price_sale_float <= 0 or (price_regular_float is not None and price_regular_float <= 0):
            dropped["invalid_price"] += 1
            continue

        discount_pct = deal.get("discount_pct")
        if not isinstance(discount_pct, (int, float)):
            discount_pct = _coerce_discount_pct(price_sale_float, price_regular_float)
        if discount_pct is not None and discount_pct <= 0:
            dropped["no_discount"] += 1
            continue

        part_number = extract_part_number(deal)
        model_number = extract_model_number(deal)
        model_number_norm = normalize_model_number(model_number)
        sku = deal.get("sku") or part_number
        product_id = deal.get("product_id") or deal.get("productId") or deal.get("productID")
        store_payload = deal.get("store") if isinstance(deal.get("store"), dict) else {}
        store_id = (
            deal.get("store_id")
            or deal.get("storeId")
            or deal.get("storeID")
            or store_payload.get("id")
            or store_payload.get("store_id")
        )
        city = (
            deal.get("city")
            or deal.get("store_city")
            or deal.get("storeCity")
            or store_payload.get("city")
        )
        normalized_title = normalize_title(title) if isinstance(title, str) else ""
        key = make_deal_key("Canadian Tire", sku, url, normalized_title)

        brand_value = deal.get("brand")
        brand_value = brand_value.strip() if isinstance(brand_value, str) and brand_value.strip() else None
        if model_number:
            query_used = f"{brand_value} {model_number}".strip() if brand_value else model_number
            match_method = "model_number"
            base_confidence = 0.85
        elif part_number:
            query_used = f"{brand_value} {part_number}".strip() if brand_value else part_number
            match_method = "part_number"
            base_confidence = 0.70
        else:
            query_used = normalized_title
            match_method = "title"
            base_confidence = 0.45

        output.append(
            {
                "deal": {
                    "title": title,
                    "key": key,
                    "part_number": part_number,
                    "model_number": model_number,
                    "model_number_norm": model_number_norm,
                    "price_sale": price_sale_float,
                    "price_regular": price_regular_float,
                    "discount_pct": discount_pct,
                    "source": "Canadian Tire",
                    "sku": sku,
                    "product_id": product_id,
                    "url": url,
                    "image": image,
                    "brand": deal.get("brand"),
                    "upc": deal.get("upc"),
                    "store_id": store_id,
                    "city": city,
                    "store_slug": deal_store_slug,
                },
                "market": {
                    "amazon_price": None,
                    "ebay_price": None,
                    "match_confidence": base_confidence,
                    "is_confirmed": False,
                    "match_method": match_method,
                    "query_used": query_used,
                },
            }
        )

    capped_output = _apply_marketplace_cap(output, max_items)
    stats = {
        "count_total": len(deals),
        "count_after_filter": len(capped_output),
        "count_dropped": sum(dropped.values()),
        "dropped": dict(sorted(dropped.items())),
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
    output_path = Path(args.out)

    deals = _load_json_list(deals_path)
    market_ready, stats = build_market_ready(
        deals,
        args.max_marketplace_items,
        store_slug=args.store_slug,
    )
    write_output(output_path, market_ready)

    print(
        "total={count_total} after_filter={count_after_filter}".format(**stats)
    )
    print(f"dropped: {stats['dropped']}")


if __name__ == "__main__":
    main()
