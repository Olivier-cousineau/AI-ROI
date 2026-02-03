"""ROI computation engine."""
from __future__ import annotations

from dataclasses import asdict

from config.assumptions import Assumptions
from core.fees_engine import estimate_fees
from core.scoring_engine import total_score
from models.keepa_model import KeepaData
from models.market_model import Market


def select_revenue(market: Market, assumptions: Assumptions) -> tuple[float, float]:
    """Select the revenue and platform fee percentage based on market prices."""
    if market.amazon_price is None and market.ebay_price is None:
        raise ValueError("Au moins un prix de marché (Amazon ou eBay) est requis.")

    if market.amazon_price is not None and (market.ebay_price is None or market.amazon_price >= market.ebay_price):
        return market.amazon_price, assumptions.amazon_fee_pct_est

    if market.ebay_price is None:
        raise ValueError("Prix eBay manquant.")

    return market.ebay_price, assumptions.ebay_fee_pct_est


def compute_roi(
    price_sale: float,
    market: Market,
    keepa: KeepaData,
    assumptions: Assumptions | None = None,
) -> dict[str, float | int | dict[str, float] | str]:
    """Compute ROI metrics based on deal and market data."""
    assumptions = assumptions or Assumptions()
    revenue, platform_fee_pct = select_revenue(market, assumptions)

    cost = price_sale * (1 + assumptions.tax_rate) + assumptions.ship_to_you
    fees = estimate_fees(revenue, platform_fee_pct, assumptions)
    profit = revenue - fees - cost
    roi_pct = (profit / cost) * 100 if cost > 0 else 0.0

    score = total_score(roi_pct, profit, keepa, has_market_price=True)

    notes = "Estimation basée sur les hypothèses par défaut."
    return {
        "profit_est": round(profit, 2),
        "roi_pct": round(roi_pct, 2),
        "score": score,
        "assumptions": asdict(assumptions),
        "notes": notes,
    }
