"""Unit tests for ROI engine."""
from __future__ import annotations

import pytest

from config.assumptions import Assumptions
from core.roi_engine import compute_roi
from models.keepa_model import KeepaData
from models.market_model import Market


def test_compute_roi_returns_expected_values() -> None:
    assumptions = Assumptions(
        tax_rate=0.1,
        ship_to_you=0.0,
        shipping_out_est=10.0,
        amazon_fee_pct_est=0.15,
        ebay_fee_pct_est=0.13,
        returns_risk_pct=0.05,
    )
    market = Market(amazon_price=200.0, ebay_price=180.0)
    keepa = KeepaData(sales_per_month=20, avg_price=190.0, rank=10000)

    result = compute_roi(
        price_sale=100.0,
        market=market,
        keepa=keepa,
        assumptions=assumptions,
    )

    assert result["profit_est"] == pytest.approx(200.0 - (200.0 * 0.15 + 10.0 + 200.0 * 0.05) - 110.0, abs=0.01)
    assert result["roi_pct"] == pytest.approx((result["profit_est"] / 110.0) * 100, abs=0.01)
    assert 0 <= result["score"] <= 100
