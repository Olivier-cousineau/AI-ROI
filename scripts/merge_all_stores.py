import argparse
import json
import os
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


def merge_all_stores(input_dir: Path, store_only: str | None = None) -> list:
    deals: list = []
    if store_only:
        store_path = Path(store_only)
        if not store_path.is_absolute():
            store_path = input_dir / store_only
        if store_path.is_dir():
            store_files = sorted(store_path.rglob("*.json"))
        elif store_path.is_file():
            store_files = [store_path]
        else:
            raise SystemExit(f"Store path not found: {store_path}")
    else:
        store_files = sorted(input_dir.rglob("*.json"))

    for store_file in store_files:
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
    parser.add_argument(
        "--store-only",
        help="Store folder or file to process (ex: 0271-st-jerome-qc).",
    )
    parser.add_argument(
        "--store-slug",
        default=os.getenv("CT_STORE_SLUG"),
        help="Store slug to process (ex: laval-qc).",
    )
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    if not input_dir.exists():
        raise SystemExit(f"Input directory not found: {input_dir}")

    store_target = args.store_slug or args.store_only
    merged = merge_all_stores(input_dir, store_target)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(merged, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
