"""Market pricing model."""
from __future__ import annotations

from pydantic import BaseModel, Field


class Market(BaseModel):
    """Represents market prices from Amazon and eBay."""

    amazon_price: float | None = Field(default=None, gt=0)
    ebay_price: float | None = Field(default=None, gt=0)
