"""Merge Canadian Tire deals with manual enrichment."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from ai.title_normalizer import normalize_title
from core.ct_extractors import extract_part_number
from core.keying import make_deal_key


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description="Merge deals with manual enrichment.")
    parser.add_argument("--deals", required=True, help="Path to deals JSON file.")
    parser.add_argument(
        "--enrichment",
        required=True,
        help="Path to manual enrichment JSON file.",
    )
    parser.add_argument("--out", required=True, help="Path to output JSON file.")
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


def _build_enrichment_index(
    enrichment_entries: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for entry in enrichment_entries:
        key = entry.get("key")
        if isinstance(key, str) and key:
            index[key] = entry
    return index


def merge_deals(
    deals: list[dict[str, Any]],
    enrichment_entries: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Merge deals with manual enrichment entries."""
    index = _build_enrichment_index(enrichment_entries)
    output: list[dict[str, Any]] = []
    count_total = len(deals)
    count_enriched = 0
    count_with_amazon_price = 0
    count_with_ebay_price = 0
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
        discount_pct = _coerce_float(deal.get("discount_pct"))
        price_sale_float = _coerce_float(price_sale)
        price_regular_float = _coerce_float(price_regular)
        if discount_pct is None and price_sale_float and price_regular_float:
            discount_pct = round((1 - price_sale_float / price_regular_float) * 100, 2)

        part_number = extract_part_number(deal)
        normalized_title = normalize_title(title) if isinstance(title, str) else ""
        key = make_deal_key("Canadian Tire", part_number, url, normalized_title)
        enrichment = index.get(key)
        if enrichment:
            count_enriched += 1

        amazon = enrichment.get("amazon", {}) if enrichment else {}
        ebay = enrichment.get("ebay", {}) if enrichment else {}
        keepa = enrichment.get("keepa", {}) if enrichment else {}
        notes = enrichment.get("notes") if enrichment else None

        amazon_price = amazon.get("price") if amazon else None
        ebay_price = ebay.get("price") if ebay else None
        match_confidence = amazon.get("match_confidence") if amazon else None
        asin = amazon.get("asin") if amazon else None

        if amazon_price is not None:
            count_with_amazon_price += 1
        if ebay_price is not None:
            count_with_ebay_price += 1
        if keepa.get("sales_per_month") is not None:
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
                    "url": url,
                    "image": image,
                },
                "market": {
                    "amazon_price": amazon_price,
                    "ebay_price": ebay_price,
                    "match_confidence": match_confidence or 0.0,
                    "asin": asin,
                    "is_confirmed": False,
                },
                "keepa": {
                    "sales_per_month": keepa.get("sales_per_month") if keepa else None,
                    "avg_price": keepa.get("avg_price") if keepa else None,
                    "rank": keepa.get("rank") if keepa else None,
                    "notes": notes,
                },
            }
        )

    stats = {
        "count_total": count_total,
        "count_enriched": count_enriched,
        "count_with_amazon_price": count_with_amazon_price,
        "count_with_ebay_price": count_with_ebay_price,
        "count_with_keepa_sales": count_with_keepa_sales,
    }
    return output, stats


def write_output(path: Path, payload: list[dict[str, Any]]) -> None:
    """Write merged payload to disk."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def main() -> None:
    """CLI entrypoint."""
    args = parse_args()
    deals_path = Path(args.deals)
    enrichment_path = Path(args.enrichment)
    output_path = Path(args.out)

    deals = _load_json_list(deals_path)
    enrichment_entries = _load_json_list(enrichment_path)
    merged, stats = merge_deals(deals, enrichment_entries)
    write_output(output_path, merged)

    print(
        "count_total={count_total} count_enriched={count_enriched} "
        "count_with_amazon_price={count_with_amazon_price} "
        "count_with_ebay_price={count_with_ebay_price} "
        "count_with_keepa_sales={count_with_keepa_sales}".format(**stats)
    )


if __name__ == "__main__":
    main()
