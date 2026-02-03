"""Default assumptions used for ROI calculations."""
from __future__ import annotations

from dataclasses import dataclass, asdict


@dataclass(frozen=True)
class Assumptions:
    """Assumptions for ROI computation."""

    tax_rate: float = 0.14975
    ship_to_you: float = 0.0
    shipping_out_est: float = 15.0
    amazon_fee_pct_est: float = 0.15
    ebay_fee_pct_est: float = 0.13
    returns_risk_pct: float = 0.05

    def as_dict(self) -> dict[str, float]:
        """Return assumptions as a dictionary."""
        return asdict(self)
