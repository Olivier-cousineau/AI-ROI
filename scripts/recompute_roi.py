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
    parser.add_argument(
        "--shipping-floor",
        type=float,
        default=8.99,
        help="Minimum shipping estimate applied to ROI computations.",
    )
    parser.add_argument(
        "--shipping-rate",
        type=float,
        default=0.10,
        help="Shipping estimate rate applied to sell price.",
    )
    return parser.parse_args()


def load_deals(path: Path) -> list[dict[str, object]]:
    """Load deal items from JSON file."""
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    if not isinstance(payload, list):
        raise ValueError("Input JSON must be a list of deal entries.")

    return payload


def compute_results(
    items: list[dict[str, object]],
    shipping_floor: float,
    shipping_rate: float,
) -> list[dict[str, object]]:
    """Compute ROI results for each item."""
    results: list[dict[str, object]] = []
    strong_profit_floor = 50
    strong_roi_floor = 50
    unconfirmed_penalty = 30
    unconfirmed_strong_penalty = 15
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
        if sell_price is None:
            continue
        fees_est = sell_price * 0.15
        shipping_est = max(shipping_floor, sell_price * shipping_rate)
        profit_net = sell_price - fees_est - shipping_est - deal.price_sale
        if deal.price_sale:
            roi_pct_net = (profit_net / deal.price_sale) * 100
        else:
            roi_pct_net = None
        low_cost_outlier = False
        if deal.price_sale is not None and deal.price_sale < 5 and roi_pct_net is not None:
            roi_pct_net = min(roi_pct_net, 500)
            low_cost_outlier = True
        score = roi_output.score
        is_confirmed = bool(market_payload.get("is_confirmed"))
        low_confidence_unconfirmed = (market.match_confidence or 0) < 0.70 and not is_confirmed
        if not is_confirmed:
            strong_profit = profit_net >= strong_profit_floor
            strong_roi = (roi_pct_net or 0) >= strong_roi_floor
            penalty = unconfirmed_strong_penalty if (strong_profit and strong_roi) else unconfirmed_penalty
            score = max(score - penalty, 0)
        if low_confidence_unconfirmed:
            score = 0
        discount_pct = deal_payload.get("discount_pct")
        if discount_pct is None and deal.price_regular:
            discount_pct = round((1 - deal.price_sale / deal.price_regular) * 100, 2)
        results.append(
            {
                "key": deal_payload.get("key"),
                "title": deal.title,
                "part_number": deal_payload.get("part_number"),
                "model_number": deal_payload.get("model_number"),
                "model_number_norm": deal_payload.get("model_number_norm"),
                "url": deal_payload.get("url"),
                "image": deal_payload.get("image"),
                "price_sale": deal.price_sale,
                "price_regular": deal.price_regular,
                "discount_pct": discount_pct,
                "profit_est": roi_output.profit_est,
                "roi_pct": roi_output.roi_pct,
                "fees_est": round(fees_est, 2),
                "shipping_est": round(shipping_est, 2),
                "profit_net": round(profit_net, 2),
                "roi_pct_net": None if roi_pct_net is None else round(roi_pct_net, 2),
                "low_cost_outlier": low_cost_outlier,
                "score": score,
                "revenue_source": roi_output.revenue_source,
                "sell_price": sell_price,
                "keepa_sales_per_month": keepa.sales_per_month,
                "match_confidence": market.match_confidence,
                "is_confirmed": is_confirmed,
                "match_method": market_payload.get("match_method"),
                "query_used": market_payload.get("query_used"),
            }
        )

    return results


def dedupe_results(results: list[dict[str, object]]) -> list[dict[str, object]]:
    """Dedupe results by key using match confidence then profit net."""
    deduped: dict[str, dict[str, object]] = {}
    extras: list[dict[str, object]] = []
    for item in results:
        key = item.get("key")
        if not key:
            extras.append(item)
            continue
        if key not in deduped:
            deduped[key] = item
            continue
        current = deduped[key]
        current_conf = current.get("match_confidence") or 0
        new_conf = item.get("match_confidence") or 0
        if new_conf > current_conf:
            deduped[key] = item
            continue
        if new_conf == current_conf:
            current_profit = current.get("profit_net") or 0
            new_profit = item.get("profit_net") or 0
            if new_profit > current_profit:
                deduped[key] = item
    return list(deduped.values()) + extras


def write_output(
    path: Path,
    results: list[dict[str, object]],
    count_total: int,
    top: int,
) -> None:
    """Write output JSON to path."""
    deduped_results = dedupe_results(results)
    filtered_results = [
        item
        for item in deduped_results
        if not ((item.get("match_confidence") or 0) < 0.70 and not item.get("is_confirmed"))
    ]
    sorted_results = sorted(
        filtered_results,
        key=lambda item: (item["score"], item["roi_pct"], item["profit_est"]),
        reverse=True,
    )
    top_count = min(top, len(sorted_results))
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "Canadian Tire",
        "count_total": count_total,
        "count_scored": len(deduped_results),
        "top": top_count,
        "results": sorted_results[:top_count],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def write_roi_output(
    path: Path,
    results: list[dict[str, object]],
) -> None:
    """Write filtered ROI output JSON to path."""
    deduped_results = dedupe_results(results)
    filtered = [
        item
        for item in deduped_results
        if item.get("is_confirmed")
        and item.get("profit_net", 0) > 20
        and (item.get("match_confidence") or 0) >= 0.7
    ]
    sorted_results = sorted(
        filtered,
        key=lambda item: (item["profit_net"], item["roi_pct_net"]),
        reverse=True,
    )
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "count_scored": len(deduped_results),
        "count_filtered": len(sorted_results),
        "results": sorted_results,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def write_roi_segments(
    confirmed_path: Path,
    watchlist_path: Path,
    results: list[dict[str, object]],
) -> None:
    """Write confirmed and watchlist ROI outputs."""
    deduped_results = dedupe_results(results)
    confirmed = [item for item in deduped_results if item.get("is_confirmed")]
    watchlist_profit_floor = 30
    watchlist_roi_floor = 40
    watchlist = [
        item
        for item in deduped_results
        if not item.get("is_confirmed")
        and (item.get("profit_net") or 0) >= watchlist_profit_floor
        and (item.get("roi_pct_net") or 0) >= watchlist_roi_floor
    ]
    for path, items in ((confirmed_path, confirmed), (watchlist_path, watchlist)):
        sorted_items = sorted(
            items,
            key=lambda item: (item.get("profit_net") or 0, item.get("roi_pct_net") or 0),
            reverse=True,
        )
        payload = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "count_scored": len(deduped_results),
            "count_filtered": len(sorted_items),
            "results": sorted_items,
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
    roi_output_path = Path("output/roi_results.json")
    roi_confirmed_path = Path("output/roi_confirmed.json")
    roi_watchlist_path = Path("output/roi_watchlist.json")

    items = load_deals(input_path)
    results = compute_results(items, args.shipping_floor, args.shipping_rate)
    write_output(output_path, results, count_total=len(items), top=args.top)
    write_roi_output(roi_output_path, results)
    write_roi_segments(roi_confirmed_path, roi_watchlist_path, results)


if __name__ == "__main__":
    main()
