from __future__ import annotations

from dataclasses import asdict
from typing import List, Optional

from ai_roi.prediction.resale_estimator import BaselineResaleEstimator
from ai_roi.prediction.risk import BaselineRiskScorer
from ai_roi.prediction.schemas import (
    ExistingRoiMetrics,
    HistoricalObservation,
    MarketplaceProductData,
    PredictionConfig,
    PredictionResult,
    ResaleEstimator,
    RetailProductData,
    RiskScorer,
    SellThroughPredictor,
)
from ai_roi.prediction.sell_through import HeuristicSellThroughPredictor


class AIROIPredictiveScorer:
    """Pluggable Phase 3 orchestrator for resale intelligence."""

    def __init__(
        self,
        config: Optional[PredictionConfig] = None,
        resale_estimator: Optional[ResaleEstimator] = None,
        sell_through_predictor: Optional[SellThroughPredictor] = None,
        risk_scorer: Optional[RiskScorer] = None,
    ) -> None:
        self.config = config or PredictionConfig()
        self.resale_estimator = resale_estimator or BaselineResaleEstimator()
        self.sell_through_predictor = sell_through_predictor or HeuristicSellThroughPredictor()
        self.risk_scorer = risk_scorer or BaselineRiskScorer()

    def predict(
        self,
        retail_product: RetailProductData,
        marketplace_product: MarketplaceProductData,
        sold_comps: List[HistoricalObservation],
        roi_metrics: ExistingRoiMetrics,
        match_confidence: float,
    ) -> PredictionResult:
        resale_estimate = self.resale_estimator.estimate(
            comps=sold_comps,
            marketplace=marketplace_product,
            config=self.config,
        )
        sell_estimate = self.sell_through_predictor.estimate(
            comps=sold_comps,
            resale_estimate=resale_estimate,
            marketplace=marketplace_product,
            match_confidence=match_confidence,
            config=self.config,
        )
        risk = self.risk_scorer.score(
            match_confidence=match_confidence,
            comps=sold_comps,
            resale_estimate=resale_estimate,
            roi_metrics=roi_metrics,
            config=self.config,
        )
        ai_roi_score = self._compute_ai_roi_score(
            roi_metrics=roi_metrics,
            sell_probability_30d=sell_estimate.sell_probability_30d,
            risk_score=risk.risk_score,
            match_confidence=match_confidence,
        )
        explanation = self._build_explanation(
            retail_product=retail_product,
            match_confidence=match_confidence,
            risk_reasons=risk.reasons,
            sell_probability=sell_estimate.sell_probability_30d,
            volatility=resale_estimate.volatility,
        )
        return PredictionResult(
            estimated_resale_price=resale_estimate.estimated_resale_price,
            sell_probability_30d=sell_estimate.sell_probability_30d,
            estimated_days_to_sell=sell_estimate.estimated_days_to_sell,
            risk_score=risk.risk_score,
            ai_roi_score=ai_roi_score,
            explanation=explanation,
            scenarios=resale_estimate.scenarios,
            diagnostics={
                "match_confidence": round(match_confidence, 4),
                "median_sold_price": resale_estimate.median_sold_price,
                "trimmed_mean_price": resale_estimate.trimmed_mean_price,
                "volatility": resale_estimate.volatility,
                "risk_points": risk.risk_points,
                **sell_estimate.diagnostics,
            },
        )

    @staticmethod
    def _compute_ai_roi_score(
        roi_metrics: ExistingRoiMetrics,
        sell_probability_30d: float,
        risk_score: str,
        match_confidence: float,
    ) -> float:
        roi_pct = roi_metrics.roi_pct if roi_metrics.roi_pct is not None else 0.0
        roi_component = max(0.0, min(4.0, roi_pct / 10))
        liquidity_component = sell_probability_30d * 3.0
        confidence_component = max(0.0, min(2.0, match_confidence * 2.0))
        risk_penalty = {"low": 0.0, "medium": 0.8, "high": 1.6}[risk_score]

        score = max(0.0, min(10.0, roi_component + liquidity_component + confidence_component - risk_penalty))
        return round(score, 2)

    @staticmethod
    def _build_explanation(
        retail_product: RetailProductData,
        match_confidence: float,
        risk_reasons: List[str],
        sell_probability: float,
        volatility: float,
    ) -> str:
        segments: List[str] = []
        if match_confidence >= 0.8:
            segments.append("Strong product match")
        elif match_confidence >= 0.6:
            segments.append("Reasonable product match")
        else:
            segments.append("Weak product match")

        if sell_probability >= 0.7:
            segments.append("healthy sell-through outlook")
        elif sell_probability >= 0.45:
            segments.append("moderate sell-through outlook")
        else:
            segments.append("slow sell-through outlook")

        if volatility >= 0.25:
            segments.append("high resale price volatility")
        elif volatility >= 0.15:
            segments.append("moderate volatility in resale pricing")

        if "thin_margin" in risk_reasons:
            segments.append("tight margins")

        sentence = ", and ".join(segments)
        return f"{sentence} for {retail_product.title}."


def result_to_dict(result: PredictionResult) -> dict:
    payload = asdict(result)
    payload["scenarios"] = asdict(result.scenarios)
    return payload
