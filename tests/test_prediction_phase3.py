from __future__ import annotations

from ai_roi.prediction.resale_estimator import BaselineResaleEstimator
from ai_roi.prediction.risk import BaselineRiskScorer
from ai_roi.prediction.scoring import AIROIPredictiveScorer, result_to_dict
from ai_roi.prediction.schemas import (
    ExistingRoiMetrics,
    HistoricalObservation,
    MarketplaceProductData,
    PredictionConfig,
    RetailProductData,
)


def test_resale_estimator_filters_outliers_and_builds_scenarios() -> None:
    estimator = BaselineResaleEstimator()
    comps = [
        HistoricalObservation(price=50.0),
        HistoricalObservation(price=52.0),
        HistoricalObservation(price=55.0),
        HistoricalObservation(price=300.0),
        HistoricalObservation(price=54.0),
    ]
    estimate = estimator.estimate(
        comps=comps,
        marketplace=MarketplaceProductData(title="Item", current_listing_price=60.0),
        config=PredictionConfig(),
    )

    assert estimate.filtered_outliers_count >= 1
    assert estimate.scenarios.conservative <= estimate.estimated_resale_price <= estimate.scenarios.optimistic
    assert 45 <= estimate.estimated_resale_price <= 60


def test_risk_scorer_detects_high_risk_signals() -> None:
    scorer = BaselineRiskScorer()
    comps = [HistoricalObservation(price=40.0), HistoricalObservation(price=120.0)]
    resale = BaselineResaleEstimator().estimate(
        comps=comps,
        marketplace=MarketplaceProductData(title="Sparse comps", current_listing_price=99.0),
        config=PredictionConfig(),
    )
    risk = scorer.score(
        match_confidence=0.45,
        comps=comps,
        resale_estimate=resale,
        roi_metrics=ExistingRoiMetrics(roi_pct=6.0, margin_pct=5.0),
        config=PredictionConfig(),
    )

    assert risk.risk_score in {"medium", "high"}
    assert "weak_match" in risk.reasons


def test_phase3_predictive_scorer_output_contract() -> None:
    scorer = AIROIPredictiveScorer()
    retail = RetailProductData(title="Wireless Headphones", buy_price=30.0, category="electronics")
    marketplace = MarketplaceProductData(
        title="Wireless Headphones", current_listing_price=59.99, listing_count=17, category="electronics"
    )
    comps = [
        HistoricalObservation(price=55.0, sold=True, days_to_sell=20),
        HistoricalObservation(price=58.0, sold=True, days_to_sell=18),
        HistoricalObservation(price=61.0, sold=True, days_to_sell=23),
        HistoricalObservation(price=57.0, sold=True, days_to_sell=21),
        HistoricalObservation(price=59.0, sold=False),
    ]

    result = scorer.predict(
        retail_product=retail,
        marketplace_product=marketplace,
        sold_comps=comps,
        roi_metrics=ExistingRoiMetrics(roi_pct=24.0, margin_pct=18.0, profit_est=14.0),
        match_confidence=0.86,
    )

    payload = result_to_dict(result)
    assert set(payload).issuperset(
        {
            "estimated_resale_price",
            "sell_probability_30d",
            "estimated_days_to_sell",
            "risk_score",
            "ai_roi_score",
            "explanation",
        }
    )
    assert 0 <= result.sell_probability_30d <= 1
    assert result.estimated_days_to_sell > 0
    assert 0 <= result.ai_roi_score <= 10
