"""Recompute ROI outputs from deal inputs."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(SCRIPT_ROOT))

from core.roi_engine import compute_roi
from models.deal_model import DealInput
from models.keepa_model import KeepaManualInput
from models.market_model import MarketInput


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description="Recompute ROI outputs from JSON input.")
    parser.add_argument(
        "--input",
        default="input/market_ready.json",
        help="Path to input JSON file.",
    )
    parser.add_argument(
        "--output",
        default="output/marketplace.json",
        help="Path to output JSON file.",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=300,
        help="Number of top results to include.",
    )
    return parser.parse_args()


def load_deals(path: Path) -> list[dict[str, object]]:
    """Load deal items from JSON file."""
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    if not isinstance(payload, list):
        raise ValueError("Input JSON must be a list of deal entries.")

    return payload


def compute_results(items: list[dict[str, object]]) -> list[dict[str, object]]:
    """Compute ROI results for each item."""
    results: list[dict[str, object]] = []
    for entry in items:
        if not isinstance(entry, dict):
            raise ValueError("Each deal entry must be an object.")

        deal_payload = entry.get("deal", {})
        market_payload = entry.get("market", {})
        keepa_payload = entry.get("keepa", {})

        market = MarketInput.model_validate(market_payload)
        if market.amazon_price is None and market.ebay_price is None:
            continue

        deal = DealInput.model_validate(deal_payload)
        keepa = KeepaManualInput.model_validate(keepa_payload)

        roi_output = compute_roi(deal, market, keepa)
        sell_price = (
            market.amazon_price
            if roi_output.revenue_source == "amazon"
            else market.ebay_price
        )
        discount_pct = None
        if deal.price_regular:
            discount_pct = round((1 - deal.price_sale / deal.price_regular) * 100, 2)
        results.append(
            {
                "title": deal.title,
                "sku": deal.sku,
                "url": deal_payload.get("url"),
                "image": deal_payload.get("image"),
                "price_sale": deal.price_sale,
                "price_regular": deal.price_regular,
                "discount_pct": discount_pct,
                "profit_est": roi_output.profit_est,
                "roi_pct": roi_output.roi_pct,
                "score": roi_output.score,
                "revenue_source": roi_output.revenue_source,
                "sell_price": sell_price,
                "keepa_sales_per_month": keepa.sales_per_month,
                "match_confidence": market.match_confidence,
            }
        )

    return results


def write_output(
    path: Path,
    results: list[dict[str, object]],
    count_total: int,
    top: int,
) -> None:
    """Write output JSON to path."""
    sorted_results = sorted(
        results,
        key=lambda item: (item["score"], item["roi_pct"], item["profit_est"]),
        reverse=True,
    )
    top_count = min(top, len(sorted_results))
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "Canadian Tire",
        "count_total": count_total,
        "count_scored": len(results),
        "top": top_count,
        "results": sorted_results[:top_count],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def main() -> None:
    """CLI entrypoint."""
    args = parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output)

    items = load_deals(input_path)
    results = compute_results(items)
    write_output(output_path, results, count_total=len(items), top=args.top)


if __name__ == "__main__":
    main()
