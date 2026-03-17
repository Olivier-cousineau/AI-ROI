from __future__ import annotations

from datetime import datetime, timezone
from typing import List

from ai_roi.prediction.schemas import (
    HistoricalObservation,
    MarketplaceProductData,
    PredictionConfig,
    ResaleEstimate,
    SellThroughEstimate,
    sold_days,
)


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


class HeuristicSellThroughPredictor:
    """Baseline 30-day sell-through estimator using interpretable heuristics."""

    def estimate(
        self,
        comps: List[HistoricalObservation],
        resale_estimate: ResaleEstimate,
        marketplace: MarketplaceProductData,
        match_confidence: float,
        config: PredictionConfig,
    ) -> SellThroughEstimate:
        sold_count = sum(1 for c in comps if c.sold)
        listing_count = marketplace.listing_count

        sales_volume_factor = _clamp(sold_count / 20)

        if listing_count is None or listing_count <= 0:
            supply_demand_factor = 0.5 if sold_count > 0 else 0.2
        else:
            supply_demand_factor = _clamp(sold_count / max(1, sold_count + listing_count))

        current_listing = marketplace.current_listing_price or resale_estimate.estimated_resale_price
        price_gap = (current_listing - resale_estimate.estimated_resale_price) / max(
            current_listing, 1.0
        )
        price_competitiveness = _clamp(0.5 + price_gap)

        category_key = (marketplace.category or "default").lower()
        category_velocity = config.category_velocity.get(
            category_key,
            config.category_velocity.get("default", 0.75),
        )
        velocity_factor = _clamp(category_velocity)

        month = datetime.now(timezone.utc).month
        seasonality_factor = config.seasonality_month_factor.get(month, 1.0)

        w = config.probability_weights
        prob = (
            sales_volume_factor * w["sales_volume"]
            + supply_demand_factor * w["supply_demand"]
            + price_competitiveness * w["price_competitiveness"]
            + velocity_factor * w["category_velocity"]
            + _clamp(match_confidence) * w["match_confidence"]
        )
        prob = _clamp(prob * seasonality_factor)

        observed_days = sold_days(comps)
        if observed_days:
            baseline_days = int(sum(observed_days) / len(observed_days))
        else:
            baseline_days = int(max(7, min(60, 45 - int(prob * 25))))

        adjusted_days = int(
            max(3, min(90, baseline_days * (1.15 - prob * 0.45) / max(0.5, velocity_factor)))
        )

        return SellThroughEstimate(
            sell_probability_30d=round(prob, 4),
            estimated_days_to_sell=adjusted_days,
            diagnostics={
                "sales_volume_factor": round(sales_volume_factor, 4),
                "supply_demand_factor": round(supply_demand_factor, 4),
                "price_competitiveness": round(price_competitiveness, 4),
                "category_velocity_factor": round(velocity_factor, 4),
                "seasonality_factor": round(seasonality_factor, 4),
            },
        )
