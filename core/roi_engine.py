"""ROI computation engine."""
from __future__ import annotations

from config.assumptions import Assumptions
from core.fees_engine import estimate_fees
from core.scoring_engine import total_score
from models.deal_model import DealInput
from models.keepa_model import KeepaManualInput
from models.market_model import MarketInput
from models.roi_model import ROIResult


def select_revenue(market: MarketInput, assumptions: Assumptions) -> tuple[float, float, str]:
    """Select the revenue and platform fee percentage based on market prices."""
    if market.amazon_price is None and market.ebay_price is None:
        raise ValueError("Au moins un prix de marché (Amazon ou eBay) est requis.")

    if market.amazon_price is None:
        return market.ebay_price, assumptions.ebay_fee_pct_est, "ebay"

    if market.ebay_price is None:
        return market.amazon_price, assumptions.amazon_fee_pct_est, "amazon"

    if market.amazon_price >= market.ebay_price:
        return market.amazon_price, assumptions.amazon_fee_pct_est, "amazon"

    return market.ebay_price, assumptions.ebay_fee_pct_est, "ebay"


def compute_roi(
    deal: DealInput,
    market: MarketInput,
    keepa: KeepaManualInput,
    assumptions: Assumptions | None = None,
) -> ROIResult:
    """Compute ROI metrics based on deal and market data."""
    assumptions = assumptions or Assumptions()
    revenue, platform_fee_pct, revenue_source = select_revenue(market, assumptions)

    cost = deal.price_sale * (1 + assumptions.tax_rate) + assumptions.ship_to_you
    fees = estimate_fees(revenue, platform_fee_pct, assumptions)
    profit = revenue - fees - cost
    roi_pct = (profit / cost) * 100 if cost > 0 else 0.0

    score = total_score(roi_pct, profit, keepa, market.match_confidence)

    notes = "Estimation basée sur les hypothèses par défaut."
    return ROIResult(
        profit_est=round(profit, 2),
        roi_pct=round(roi_pct, 2),
        score=score,
        assumptions=assumptions.as_dict(),
        revenue_source=revenue_source,
        notes=notes,
    )
