from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ai_roi.matching import ProductMatcher


def main() -> None:
    retail_product = {
        "title": "Apple AirPods Pro 2nd Gen with MagSafe Charging Case",
        "brand": "Apple",
        "model": "A2698",
        "sku": "AIRPODSPRO2",
        "upc": "194253397168",
        "category": "Electronics > Audio > Earbuds",
        "price": 199.99,
    }

    marketplace_product = {
        "title": "AirPods Pro (2nd Generation) A2698 - Apple - New",
        "brand": "Apple Inc.",
        "model": "A2698",
        "ean": "194253397168",
        "category": "Electronics/Headphones",
        "listed_price": 189.0,
        "condition": "New",
    }

    matcher = ProductMatcher()
    result = matcher.match(retail_product, marketplace_product)

    print(json.dumps({
        "match_confidence": result.match_confidence,
        "match_label": result.match_label,
        "explanation": result.explanation,
        "signals": result.extracted_signals,
    }, indent=2))


if __name__ == "__main__":
    main()
