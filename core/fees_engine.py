"""Fee calculation engine."""
from __future__ import annotations

from config.assumptions import Assumptions


def estimate_fees(revenue: float, platform_fee_pct: float, assumptions: Assumptions) -> float:
    """Estimate total fees for a given revenue and platform fee percentage."""
    return (
        revenue * platform_fee_pct
        + assumptions.shipping_out_est
        + revenue * assumptions.returns_risk_pct
    )
