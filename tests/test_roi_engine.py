"""Unit tests for ROI engine."""
from __future__ import annotations

import pytest

from config.assumptions import Assumptions
from core.roi_engine import compute_roi
from models.deal_model import DealInput
from models.keepa_model import KeepaManualInput
from models.market_model import MarketInput


def test_compute_roi_with_amazon_price() -> None:
    assumptions = Assumptions(
        tax_rate=0.1,
        ship_to_you=0.0,
        shipping_out_est=10.0,
        amazon_fee_pct_est=0.15,
        ebay_fee_pct_est=0.13,
        returns_risk_pct=0.05,
    )
    deal = DealInput(title="Test", price_sale=100.0)
    market = MarketInput(amazon_price=200.0, ebay_price=180.0, match_confidence=0.8)
    keepa = KeepaManualInput(sales_per_month=20, avg_price=190.0, rank=10000)

    result = compute_roi(
        deal=deal,
        market=market,
        keepa=keepa,
        assumptions=assumptions,
    )

    expected_profit = 200.0 - (200.0 * 0.15 + 10.0 + 200.0 * 0.05) - 110.0
    assert result.profit_est == pytest.approx(expected_profit, abs=0.01)
    assert result.roi_pct == pytest.approx((expected_profit / 110.0) * 100, abs=0.01)
    assert result.revenue_source == "amazon"


def test_compute_roi_with_ebay_price() -> None:
    deal = DealInput(title="Test", price_sale=80.0)
    market = MarketInput(amazon_price=None, ebay_price=140.0, match_confidence=0.7)
    keepa = KeepaManualInput(sales_per_month=5)

    result = compute_roi(deal=deal, market=market, keepa=keepa)

    assert result.revenue_source == "ebay"
    assert result.profit_est > -100


def test_compute_roi_requires_market_price() -> None:
    deal = DealInput(title="Test", price_sale=80.0)
    market = MarketInput()
    keepa = KeepaManualInput()

    with pytest.raises(ValueError, match="prix de marché"):
        compute_roi(deal=deal, market=market, keepa=keepa)
