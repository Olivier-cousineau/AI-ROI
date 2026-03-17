"""Demo script for Phase 3 predictive resale intelligence."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai_roi.prediction import (
    AIROIPredictiveScorer,
    ExistingRoiMetrics,
    HistoricalObservation,
    MarketplaceProductData,
    RetailProductData,
    result_to_dict,
)


def main() -> None:
    scorer = AIROIPredictiveScorer()

    retail = RetailProductData(
        title="EconoPlus Air Fryer 5L",
        buy_price=34.99,
        category="home",
    )
    marketplace = MarketplaceProductData(
        title="EconoPlus Air Fryer 5L",
        current_listing_price=64.99,
        listing_count=26,
        category="home",
        marketplace="ebay",
    )
    comps = [
        HistoricalObservation(price=56.0, sold=True, days_to_sell=21),
        HistoricalObservation(price=58.5, sold=True, days_to_sell=18),
        HistoricalObservation(price=59.0, sold=True, days_to_sell=23),
        HistoricalObservation(price=54.0, sold=True, days_to_sell=25),
        HistoricalObservation(price=62.0, sold=True, days_to_sell=20),
        HistoricalObservation(price=80.0, sold=False),
    ]

    output = scorer.predict(
        retail_product=retail,
        marketplace_product=marketplace,
        sold_comps=comps,
        roi_metrics=ExistingRoiMetrics(roi_pct=31.0, margin_pct=21.0, profit_est=11.5),
        match_confidence=0.83,
    )
    print(json.dumps(result_to_dict(output), indent=2))


if __name__ == "__main__":
    main()
