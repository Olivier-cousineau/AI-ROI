import argparse
import json
from pathlib import Path


def load_deals(path: Path) -> list:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        if isinstance(payload.get("items"), list):
            return payload["items"]
        if isinstance(payload.get("deals"), list):
            return payload["deals"]
        return [payload]
    return []


def merge_all_stores(input_dir: Path) -> list:
    deals: list = []
    for store_file in sorted(input_dir.rglob("*.json")):
        deals.extend(load_deals(store_file))
    return deals


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Merge all Canadian Tire store liquidation files into one list."
    )
    parser.add_argument(
        "--input-dir",
        default="input/canadiantire",
        help="Directory containing store JSON files.",
    )
    parser.add_argument(
        "--output",
        default="input/canadiantire_all_liquidations.json",
        help="Output JSON file path.",
    )
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    if not input_dir.exists():
        raise SystemExit(f"Input directory not found: {input_dir}")

    merged = merge_all_stores(input_dir)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(merged, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
