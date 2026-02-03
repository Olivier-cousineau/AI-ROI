"""Keepa data input model."""
from __future__ import annotations

from pydantic import BaseModel, Field


class KeepaManualInput(BaseModel):
    """Represents Keepa metrics entered manually."""

    sales_per_month: int | None = Field(default=None, ge=0)
    avg_price: float | None = Field(default=None, ge=0)
    rank: int | None = Field(default=None, ge=0)
    notes: str | None = None
