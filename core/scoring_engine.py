"""Scoring engine for ROI opportunities."""
from __future__ import annotations

from models.keepa_model import KeepaData


def clamp(value: float, min_value: float, max_value: float) -> int:
    """Clamp a value to an integer within the given bounds."""
    return int(max(min_value, min(value, max_value)))


def roi_bucket(roi_pct: float) -> int:
    """Score ROI percentage into a bucket (0-40)."""
    if roi_pct >= 50:
        return 40
    if roi_pct >= 30:
        return 30
    if roi_pct >= 15:
        return 20
    if roi_pct >= 5:
        return 10
    return 0


def profit_bucket(profit: float) -> int:
    """Score profit into a bucket (0-25)."""
    if profit >= 100:
        return 25
    if profit >= 50:
        return 18
    if profit >= 20:
        return 10
    if profit > 0:
        return 5
    return 0


def demand_bucket(keepa: KeepaData) -> int:
    """Score demand based on Keepa sales per month (0-25)."""
    sales = keepa.sales_per_month
    if sales is None or sales <= 0:
        return 0
    if sales >= 30:
        return 25
    if 15 <= sales <= 29:
        return 18
    if 5 <= sales <= 14:
        return 10
    if 1 <= sales <= 4:
        return 5
    return 0


def confidence_score(keepa: KeepaData, has_market_price: bool) -> int:
    """Estimate confidence score based on available data (0-10)."""
    score = 0
    if has_market_price:
        score += 4
    if keepa.sales_per_month is not None:
        score += 3
    if keepa.avg_price is not None:
        score += 3
    return clamp(score, 0, 10)


def total_score(roi_pct: float, profit: float, keepa: KeepaData, has_market_price: bool) -> int:
    """Compute total score (0-100)."""
    score = (
        roi_bucket(roi_pct)
        + profit_bucket(profit)
        + demand_bucket(keepa)
        + confidence_score(keepa, has_market_price)
    )
    return clamp(score, 0, 100)
