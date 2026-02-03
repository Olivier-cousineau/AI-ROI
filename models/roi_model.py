"""ROI request/response models."""
from __future__ import annotations

from pydantic import BaseModel, Field

from models.deal_model import Deal
from models.keepa_model import KeepaData
from models.market_model import Market


class ComputeRoiRequest(BaseModel):
    """Request payload for ROI computation."""

    deal: Deal
    market: Market
    keepa: KeepaData


class RoiResponse(BaseModel):
    """Response payload for ROI computation."""

    profit_est: float = Field(...)
    roi_pct: float = Field(...)
    score: int = Field(..., ge=0, le=100)
    assumptions: dict[str, float]
    notes: str
