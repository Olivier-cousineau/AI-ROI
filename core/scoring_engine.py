"""Scoring engine for ROI opportunities."""
from __future__ import annotations

from models.keepa_model import KeepaManualInput


def clamp(value: float, min_value: float, max_value: float) -> int:
    """Clamp a value to an integer within the given bounds."""
    return int(max(min_value, min(value, max_value)))


def roi_bucket(roi_pct: float) -> int:
    """Score ROI percentage into a bucket (0-40)."""
    if roi_pct >= 60:
        return 40
    if roi_pct >= 40:
        return 30
    if roi_pct >= 20:
        return 18
    if roi_pct >= 10:
        return 10
    if roi_pct >= 0:
        return 5
    return 0


def profit_bucket(profit: float) -> int:
    """Score profit into a bucket (0-25)."""
    if profit >= 80:
        return 25
    if profit >= 40:
        return 18
    if profit >= 20:
        return 12
    if profit >= 10:
        return 6
    if profit >= 0:
        return 3
    return 0


def demand_bucket(keepa: KeepaManualInput) -> int:
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


def confidence_bucket(match_confidence: float) -> int:
    """Score confidence based on match confidence (0-10)."""
    if match_confidence >= 0.90:
        return 10
    if match_confidence >= 0.75:
        return 7
    if match_confidence >= 0.60:
        return 4
    return 0


def total_score(
    roi_pct: float,
    profit: float,
    keepa: KeepaManualInput,
    match_confidence: float,
) -> int:
    """Compute total score (0-100)."""
    score = (
        roi_bucket(roi_pct)
        + profit_bucket(profit)
        + demand_bucket(keepa)
        + confidence_bucket(match_confidence)
    )
    return clamp(score, 0, 100)
