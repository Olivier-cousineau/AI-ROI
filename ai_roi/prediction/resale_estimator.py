from __future__ import annotations

from statistics import mean, median, pstdev
from typing import List

from ai_roi.prediction.schemas import (
    HistoricalObservation,
    MarketplaceProductData,
    PredictionConfig,
    ResaleEstimate,
    ResaleScenario,
    sold_prices,
)


def _filter_outliers_iqr(prices: List[float], multiplier: float) -> List[float]:
    if len(prices) < 4:
        return prices

    ordered = sorted(prices)
    q1 = ordered[len(ordered) // 4]
    q3 = ordered[(len(ordered) * 3) // 4]
    iqr = q3 - q1
    if iqr <= 0:
        return prices

    low = q1 - multiplier * iqr
    high = q3 + multiplier * iqr
    filtered = [p for p in ordered if low <= p <= high]
    return filtered or prices


def _trimmed_mean(values: List[float], trim_ratio: float) -> float:
    if not values:
        raise ValueError("Cannot compute trimmed mean without values")

    ordered = sorted(values)
    trim_n = int(len(values) * trim_ratio)
    if trim_n * 2 >= len(values):
        trim_n = max(0, (len(values) // 2) - 1)
    trimmed = ordered[trim_n : len(values) - trim_n] or ordered
    return float(mean(trimmed))


class BaselineResaleEstimator:
    """Deterministic baseline estimator using sold comps statistics."""

    def estimate(
        self,
        comps: List[HistoricalObservation],
        marketplace: MarketplaceProductData,
        config: PredictionConfig,
    ) -> ResaleEstimate:
        prices = sold_prices(comps)
        if not prices:
            fallback = marketplace.current_listing_price or 0.0
            scenarios = ResaleScenario(
                conservative=round(fallback * 0.9, 2),
                realistic=round(fallback, 2),
                optimistic=round(fallback * 1.08, 2),
            )
            return ResaleEstimate(
                scenarios=scenarios,
                estimated_resale_price=scenarios.realistic,
                median_sold_price=fallback,
                trimmed_mean_price=fallback,
                volatility=0.0,
                filtered_outliers_count=0,
            )

        filtered = _filter_outliers_iqr(prices, config.outlier_iqr_multiplier)
        med = float(median(filtered))
        trimmed = _trimmed_mean(filtered, config.trim_ratio)
        realistic = (0.6 * med) + (0.4 * trimmed)

        volatility = 0.0
        if len(filtered) > 1:
            volatility = pstdev(filtered) / (mean(filtered) or 1.0)

        conservative = realistic * (0.92 - min(0.08, volatility / 3))
        optimistic = realistic * (1.06 + min(0.06, volatility / 4))

        if marketplace.current_listing_price and marketplace.current_listing_price > 0:
            optimistic = min(optimistic, marketplace.current_listing_price * 1.1)

        scenarios = ResaleScenario(
            conservative=round(max(0.0, conservative), 2),
            realistic=round(max(0.0, realistic), 2),
            optimistic=round(max(0.0, optimistic), 2),
        )
        return ResaleEstimate(
            scenarios=scenarios,
            estimated_resale_price=scenarios.realistic,
            median_sold_price=round(med, 2),
            trimmed_mean_price=round(trimmed, 2),
            volatility=round(volatility, 4),
            filtered_outliers_count=max(0, len(prices) - len(filtered)),
        )
