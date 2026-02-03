"""Recompute ROI outputs from deal inputs."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from core.roi_engine import compute_roi
from models.deal_model import Deal
from models.keepa_model import KeepaData
from models.market_model import Market


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description="Recompute ROI outputs from JSON input.")
    parser.add_argument("--input", required=True, help="Path to input JSON file.")
    parser.add_argument("--output", required=True, help="Path to output JSON file.")
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

        deal = Deal.model_validate(entry.get("deal", {}))
        market = Market.model_validate(entry.get("market", {}))
        keepa = KeepaData.model_validate(entry.get("keepa", {}))

        roi_output = compute_roi(deal.price_sale, market, keepa)
        results.append(
            {
                "deal": deal.model_dump(),
                "market": market.model_dump(),
                "keepa": keepa.model_dump(),
                "roi": roi_output,
            }
        )

    return results


def write_output(path: Path, results: list[dict[str, object]]) -> None:
    """Write output JSON to path."""
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "results": results,
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
    write_output(output_path, results)


if __name__ == "__main__":
    main()
