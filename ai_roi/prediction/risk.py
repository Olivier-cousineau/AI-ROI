from __future__ import annotations

from typing import List

from ai_roi.prediction.schemas import (
    ExistingRoiMetrics,
    HistoricalObservation,
    PredictionConfig,
    ResaleEstimate,
    RiskAssessment,
)


class BaselineRiskScorer:
    """Assign low/medium/high risk based on market and margin reliability signals."""

    def score(
        self,
        match_confidence: float,
        comps: List[HistoricalObservation],
        resale_estimate: ResaleEstimate,
        roi_metrics: ExistingRoiMetrics,
        config: PredictionConfig,
    ) -> RiskAssessment:
        risk_points = 0.0
        reasons: List[str] = []

        sold_count = sum(1 for c in comps if c.sold)

        if match_confidence < config.weak_match_threshold:
            risk_points += 2.0
            reasons.append("weak_match")

        if sold_count < config.low_sales_threshold:
            risk_points += 1.5
            reasons.append("low_sales_volume")

        if resale_estimate.volatility >= config.volatility_high_threshold:
            risk_points += 1.5
            reasons.append("high_price_volatility")

        margin_pct = roi_metrics.margin_pct
        if margin_pct is None and roi_metrics.roi_pct is not None:
            margin_pct = roi_metrics.roi_pct

        if margin_pct is not None and margin_pct < config.thin_margin_threshold:
            risk_points += 1.0
            reasons.append("thin_margin")

        if comps:
            uncertain_ratio = resale_estimate.filtered_outliers_count / len(comps)
            if uncertain_ratio >= config.uncertain_comps_threshold:
                risk_points += 1.0
                reasons.append("uncertain_comps")

        if risk_points >= 4.0:
            label = "high"
        elif risk_points >= 2.0:
            label = "medium"
        else:
            label = "low"

        return RiskAssessment(risk_score=label, risk_points=risk_points, reasons=reasons)
