from __future__ import annotations

from dataclasses import dataclass, field
from statistics import median
from typing import Dict, List, Literal, Optional, Protocol


RiskLabel = Literal["low", "medium", "high"]


@dataclass
class RetailProductData:
    """Retail-side product context used for resale forecasting."""

    title: str
    buy_price: float
    category: Optional[str] = None
    condition: str = "new"


@dataclass
class MarketplaceProductData:
    """Matched marketplace product context from Phase 2."""

    title: str
    current_listing_price: Optional[float] = None
    listing_count: Optional[int] = None
    category: Optional[str] = None
    marketplace: str = "ebay"


@dataclass
class HistoricalObservation:
    """Sold/listed comp used by baseline heuristics."""

    price: float
    sold: bool = True
    days_to_sell: Optional[int] = None


@dataclass
class ExistingRoiMetrics:
    """Previously computed ROI metrics from earlier pipeline phases."""

    roi_pct: Optional[float] = None
    profit_est: Optional[float] = None
    margin_pct: Optional[float] = None


@dataclass
class ResaleScenario:
    conservative: float
    realistic: float
    optimistic: float


@dataclass
class ResaleEstimate:
    scenarios: ResaleScenario
    estimated_resale_price: float
    median_sold_price: float
    trimmed_mean_price: float
    volatility: float
    filtered_outliers_count: int


@dataclass
class SellThroughEstimate:
    sell_probability_30d: float
    estimated_days_to_sell: int
    diagnostics: Dict[str, float] = field(default_factory=dict)


@dataclass
class RiskAssessment:
    risk_score: RiskLabel
    risk_points: float
    reasons: List[str]


@dataclass
class PredictionResult:
    estimated_resale_price: float
    sell_probability_30d: float
    estimated_days_to_sell: int
    risk_score: RiskLabel
    ai_roi_score: float
    explanation: str
    scenarios: ResaleScenario
    diagnostics: Dict[str, float] = field(default_factory=dict)


@dataclass
class PredictionConfig:
    """Configurable thresholds/weights for deterministic baseline model."""

    trim_ratio: float = 0.1
    outlier_iqr_multiplier: float = 1.5
    weak_match_threshold: float = 0.6
    low_sales_threshold: int = 5
    volatility_high_threshold: float = 0.25
    thin_margin_threshold: float = 12.0
    uncertain_comps_threshold: float = 0.35
    category_velocity: Dict[str, float] = field(
        default_factory=lambda: {
            "electronics": 1.0,
            "home": 0.85,
            "fashion": 0.8,
            "collectibles": 0.7,
            "default": 0.75,
        }
    )
    seasonality_month_factor: Dict[int, float] = field(default_factory=dict)
    probability_weights: Dict[str, float] = field(
        default_factory=lambda: {
            "sales_volume": 0.25,
            "supply_demand": 0.2,
            "price_competitiveness": 0.2,
            "category_velocity": 0.15,
            "match_confidence": 0.2,
        }
    )


class ResaleEstimator(Protocol):
    def estimate(
        self,
        comps: List[HistoricalObservation],
        marketplace: MarketplaceProductData,
        config: PredictionConfig,
    ) -> ResaleEstimate:
        ...


class SellThroughPredictor(Protocol):
    def estimate(
        self,
        comps: List[HistoricalObservation],
        resale_estimate: ResaleEstimate,
        marketplace: MarketplaceProductData,
        match_confidence: float,
        config: PredictionConfig,
    ) -> SellThroughEstimate:
        ...


class RiskScorer(Protocol):
    def score(
        self,
        match_confidence: float,
        comps: List[HistoricalObservation],
        resale_estimate: ResaleEstimate,
        roi_metrics: ExistingRoiMetrics,
        config: PredictionConfig,
    ) -> RiskAssessment:
        ...


def sold_prices(comps: List[HistoricalObservation]) -> List[float]:
    return [c.price for c in comps if c.sold and c.price > 0]


def sold_days(comps: List[HistoricalObservation]) -> List[int]:
    return [c.days_to_sell for c in comps if c.sold and c.days_to_sell is not None]


def safe_median(values: List[float], default: float) -> float:
    return float(median(values)) if values else default
