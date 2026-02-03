"""Market pricing model."""
from __future__ import annotations

from pydantic import BaseModel, Field


class MarketInput(BaseModel):
    """Represents market prices from Amazon and eBay."""

    amazon_price: float | None = Field(default=None, gt=0)
    ebay_price: float | None = Field(default=None, gt=0)
    match_confidence: float = Field(default=0.0, ge=0, le=1)
