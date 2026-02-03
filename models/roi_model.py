"""ROI request/response models."""
from __future__ import annotations

from pydantic import BaseModel, Field

from models.deal_model import DealInput
from models.keepa_model import KeepaManualInput
from models.market_model import MarketInput


class ComputeROIRequest(BaseModel):
    """Request payload for ROI computation."""

    deal: DealInput
    market: MarketInput
    keepa: KeepaManualInput


class ROIResult(BaseModel):
    """Response payload for ROI computation."""

    profit_est: float = Field(...)
    roi_pct: float = Field(...)
    score: int = Field(..., ge=0, le=100)
    assumptions: dict[str, float]
    revenue_source: str
    notes: str


class RoiResponse(ROIResult):
    """Alias for ROI response payload."""
