"""Recompute ROI outputs from deal inputs."""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(SCRIPT_ROOT))

from core.roi_engine import compute_roi
from models.deal_model import DealInput
from models.keepa_model import KeepaManualInput
from models.market_model import MarketInput

TEST_MODE = os.getenv("IS_TESTRUN", "").strip().lower() == "true"


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description="Recompute ROI outputs from JSON input.")
    parser.add_argument(
        "--input",
        default="econoplus/public/index/deals-80.json",
        help=(
            "Path to input JSON file or a directory containing index/deals-80.json."
        ),
    )
    parser.add_argument(
        "--source",
        default="bestbuy",
        help="Input source to validate and report (ex: bestbuy, canadiantire).",
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


SOURCE_LABELS = {
    "bestbuy": "BestBuy",
    "canadiantire": "Canadian Tire",
}


def normalize_source(value: str | None) -> str:
    """Normalize source input to a simple token."""
    if not value:
        return ""
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def resolve_input_path(path: Path, source: str) -> Path:
    """Resolve the input path, allowing directory shortcuts."""
    if source == "bestbuy" and path.as_posix().rstrip("/") == "output/marketplace.json":
        raise ValueError("BestBuy ROI must use the BestBuy deals file, not output/marketplace.json.")

    if source == "bestbuy" and path.as_posix().rstrip("/") == "econoplus/public":
        candidates = [
            path / "bestbuy" / "index" / "deals-80.json",
            path / "bestbuy" / "deals-80.json",
            path / "bestbuy" / "index" / "deals.json",
            path / "bestbuy" / "online.json",
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate
        candidate_list = ", ".join(str(candidate) for candidate in candidates)
        raise FileNotFoundError(
            "No BestBuy deals file found under econoplus/public. "
            f"Tried: {candidate_list}"
        )

    if path.is_dir():
        normalized_source = normalize_source(source)
        candidates = [
            path / normalized_source / "index" / "deals-80.json",
            path / normalized_source / "deals-80.json",
            path / normalized_source / "online.json",
            path / "index" / "deals-80.json",
            path / "deals-80.json",
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate
        candidate_list = ", ".join(str(candidate) for candidate in candidates)
        raise FileNotFoundError(
            f"No deals-80.json found under directory {path}. "
            f"Tried: {candidate_list}"
        )
    return path


def load_deals(path: Path) -> list[dict[str, object]]:
    """Load deal items from JSON file."""
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    if not isinstance(payload, list):
        raise ValueError("Input JSON must be a list of deal entries.")

    return payload


def _detect_source_token(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    lowered = value.lower()
    if "bestbuy" in lowered or "best buy" in lowered:
        return "bestbuy"
    if "canadiantire" in lowered or "canadian tire" in lowered:
        return "canadiantire"
    return None


def detect_input_source(items: list[dict[str, object]]) -> str | None:
    """Detect the input source based on payload hints."""
    counts = {key: 0 for key in SOURCE_LABELS}
    for entry in items:
        if not isinstance(entry, dict):
            continue
        deal_payload = entry.get("deal") if isinstance(entry.get("deal"), dict) else {}
        candidates = [
            entry.get("source"),
            entry.get("retailer"),
            entry.get("retailer_name"),
            deal_payload.get("source"),
            deal_payload.get("retailer"),
        ]
        for candidate in candidates:
            token = _detect_source_token(candidate)
            if token in counts:
                counts[token] += 1
        url_token = _detect_source_token(deal_payload.get("url") or entry.get("url"))
        if url_token in counts:
            counts[url_token] += 1
    max_count = max(counts.values(), default=0)
    if max_count == 0:
        return None
    top_sources = [key for key, count in counts.items() if count == max_count]
    if len(top_sources) != 1:
        return None
    return top_sources[0]


def _to_number(value: object) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _normalize_token_text(value: object) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.lower().split())


def _title_similarity(left: object, right: object) -> float:
    left_tokens = {token for token in _normalize_token_text(left).split(" ") if token}
    right_tokens = {token for token in _normalize_token_text(right).split(" ") if token}
    if not left_tokens or not right_tokens:
        return 0.0
    overlap = len(left_tokens & right_tokens)
    union = len(left_tokens | right_tokens)
    if union == 0:
        return 0.0
    return round(overlap / union, 2)


def _tokenize_image_url(url: object) -> set[str]:
    if not isinstance(url, str):
        return set()
    return {
        token
        for token in re.split(r"[^a-z0-9]+", url.lower())
        if len(token) >= 3 and token not in {"https", "http", "www", "com", "jpg", "jpeg", "png", "webp", "img", "image"}
    }


def _image_match_score(deal_image: object, ebay_image: object) -> float:
    deal_tokens = _tokenize_image_url(deal_image)
    ebay_tokens = _tokenize_image_url(ebay_image)
    if not deal_tokens or not ebay_tokens:
        return 0.0
    overlap = len(deal_tokens & ebay_tokens)
    union = len(deal_tokens | ebay_tokens)
    if union == 0:
        return 0.0
    return round(overlap / union, 2)


def _confidence_label_from_signals(
    *,
    brand_match: bool,
    model_match: bool,
    part_match: bool,
    image_match: bool,
    title_similarity: float,
) -> str:
    core = [model_match, part_match, image_match]
    core_count = sum(1 for signal in core if signal)
    mid = brand_match and title_similarity >= 0.55

    if ((model_match or part_match) and image_match) or (image_match and mid):
        return "HIGH"
    if (image_match and (model_match or part_match)) or (model_match or part_match) or (core_count >= 2):
        return "MED"
    if core_count == 1 or mid:
        return "LOW"
    return "NONE"


def _confidence_rank(label: str | None) -> int:
    mapping = {"NONE": 0, "LOW": 1, "MED": 2, "HIGH": 3}
    return mapping.get((label or "").upper(), 0)


def _build_ebay_match(deal_payload: dict[str, object], market_payload: dict[str, object]) -> dict[str, object] | None:
    item_id = market_payload.get("ebay_item_id") or market_payload.get("item_id")
    ebay_title = market_payload.get("ebay_title")
    ebay_price = market_payload.get("ebay_price")
    ebay_image = market_payload.get("ebay_image")
    ebay_url = market_payload.get("ebay_item_web_url") or market_payload.get("item_web_url")

    if not any([item_id, ebay_title, ebay_price, ebay_image, ebay_url]):
        return None

    brand = deal_payload.get("brand") if isinstance(deal_payload.get("brand"), str) else None
    part_number = deal_payload.get("part_number") if isinstance(deal_payload.get("part_number"), str) else None
    model_number = deal_payload.get("model_number") if isinstance(deal_payload.get("model_number"), str) else None
    ebay_title_str = ebay_title if isinstance(ebay_title, str) else ""

    brand_match = bool(brand and brand.lower() in ebay_title_str.lower())
    model_match = bool(model_number and str(model_number).lower() in ebay_title_str.lower())
    part_match = bool(part_number and str(part_number).lower() in ebay_title_str.lower())

    title_similarity = _title_similarity(deal_payload.get("title"), ebay_title)

    seller_payload = market_payload.get("ebay_seller")
    seller = None
    if isinstance(seller_payload, dict):
        seller = {
            "username": seller_payload.get("username"),
            "feedback_percent": _to_number(seller_payload.get("feedback_percent")),
        }

    image_match_score = _to_number(market_payload.get("image_match_score"))
    if image_match_score is None:
        image_match_score = _image_match_score(deal_payload.get("image"), ebay_image)
    image_match_score = max(0.0, min(1.0, image_match_score))
    image_match = image_match_score >= 0.80
    confidence_label = _confidence_label_from_signals(
        brand_match=brand_match,
        model_match=model_match,
        part_match=part_match,
        image_match=image_match,
        title_similarity=title_similarity,
    )

    return {
        "item_id": item_id,
        "title": ebay_title,
        "item_web_url": ebay_url,
        "image": ebay_image,
        "price": _to_number(ebay_price),
        "shipping": _to_number(market_payload.get("ebay_shipping")),
        "condition": market_payload.get("ebay_condition"),
        "seller": seller,
        "match_confidence": confidence_label,
        "match_signals": {
            "brand_match": brand_match,
            "model_match": model_match,
            "part_number_match": part_match,
            "image_match": image_match,
            "image_match_score": image_match_score,
            "title_similarity": title_similarity,
        },
    }

def _append_reject(
    rejects: list[dict[str, object]] | None,
    deal_payload: dict[str, object],
    market_payload: dict[str, object],
    reason: str | None,
) -> None:
    if rejects is None or not reason:
        return
    rejects.append(
        {
            "title": deal_payload.get("title"),
            "key": deal_payload.get("key"),
            "reject_reason": reason,
            "match_confidence": market_payload.get("match_confidence"),
            "query_used": market_payload.get("query_used"),
        }
    )


def compute_results(
    items: list[dict[str, object]],
    shipping_floor: float,
    shipping_rate: float,
    rejects: list[dict[str, object]] | None = None,
    test_mode: bool | None = None,
) -> list[dict[str, object]]:
    """Compute ROI results for each item."""
    if test_mode is None:
        test_mode = TEST_MODE
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
            _append_reject(rejects, deal_payload, market_payload, "missing_market_price")
            continue

        deal = DealInput.model_validate(deal_payload)
        keepa = KeepaManualInput.model_validate(keepa_payload)

        ebay_match = _build_ebay_match(deal_payload, market_payload)
        match_label = ebay_match.get("match_confidence") if isinstance(ebay_match, dict) else None
        if _confidence_rank(str(match_label) if match_label is not None else None) < _confidence_rank("MED"):
            if not test_mode:
                _append_reject(rejects, deal_payload, market_payload, "low_ebay_match_confidence")
                continue

        roi_output = compute_roi(deal, market, keepa)
        sell_price = (
            market.amazon_price
            if roi_output.revenue_source == "amazon"
            else market.ebay_price
        )
        if sell_price is None:
            _append_reject(rejects, deal_payload, market_payload, "missing_sell_price")
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
        reject_reason = market_payload.get("reject_reason")
        if not isinstance(reject_reason, str):
            reject_reason = None
        if test_mode and _confidence_rank(str(match_label) if match_label is not None else None) < _confidence_rank("MED"):
            reject_reason = reject_reason or "low_ebay_match_confidence"
        _append_reject(rejects, deal_payload, market_payload, reject_reason)
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
                "reject_reason": reject_reason,
                "ebay_match": ebay_match,
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
    source: str,
    input_file: str,
    test_mode: bool | None = None,
) -> None:
    """Write output JSON to path."""
    if test_mode is None:
        test_mode = TEST_MODE
    deduped_results = dedupe_results(results)
    if test_mode:
        filtered_results = deduped_results
    else:
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
        "source": source,
        "input_file": input_file,
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
    source: str,
    input_file: str,
    test_mode: bool | None = None,
) -> None:
    """Write filtered ROI output JSON to path."""
    if test_mode is None:
        test_mode = TEST_MODE
    deduped_results = dedupe_results(results)
    if test_mode:
        filtered = deduped_results
    else:
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
        "source": source,
        "input_file": input_file,
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
    test_mode: bool | None = None,
) -> None:
    """Write confirmed and watchlist ROI outputs."""
    if test_mode is None:
        test_mode = TEST_MODE
    deduped_results = dedupe_results(results)
    if test_mode:
        confirmed = deduped_results
        watchlist = []
    else:
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


def write_roi_rejects_debug(path: Path, rejects: list[dict[str, object]]) -> None:
    """Write debug output for ROI rejects."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(rejects, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def main() -> None:
    """CLI entrypoint."""
    args = parse_args()
    normalized_source = normalize_source(args.source)
    if not normalized_source:
        raise ValueError("--source must be a non-empty string.")
    input_path = resolve_input_path(Path(args.input), normalized_source)
    print("input_path resolved:", input_path)
    output_path = Path(args.output)
    roi_output_path = Path("output/roi_results.json")
    roi_confirmed_path = Path("output/roi_confirmed.json")
    roi_watchlist_path = Path("output/roi_watchlist.json")
    roi_rejects_debug_path = Path("output/roi_rejects_debug.json")

    items = load_deals(input_path)
    print("items loaded:", len(items))
    if items:
        print("first item keys:", list(items[0].keys()))
    if len(items) == 0:
        raise Exception(f"No items loaded from {input_path}")
    detected_source = detect_input_source(items)
    if detected_source and detected_source != normalized_source:
        detected_label = SOURCE_LABELS.get(detected_source, detected_source)
        raise ValueError(
            f"Input is {detected_label} but --source={args.source}. Check input path."
        )
    source_label = SOURCE_LABELS.get(normalized_source, args.source)
    rejects: list[dict[str, object]] = []
    results = compute_results(items, args.shipping_floor, args.shipping_rate, rejects=rejects)
    write_output(
        output_path,
        results,
        count_total=len(items),
        top=args.top,
        source=source_label,
        input_file=str(input_path),
    )
    write_roi_output(
        roi_output_path,
        results,
        source=source_label,
        input_file=str(input_path),
    )
    write_roi_segments(roi_confirmed_path, roi_watchlist_path, results)
    write_roi_rejects_debug(roi_rejects_debug_path, rejects)


if __name__ == "__main__":
    main()
