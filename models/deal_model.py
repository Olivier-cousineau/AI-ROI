"""Deal input model."""
from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class DealInput(BaseModel):
    """Represents a deal discovered in the market."""

    title: str = Field(..., min_length=1)
    price_sale: float = Field(..., gt=0)
    price_regular: float | None = Field(default=None, gt=0)
    source: str | None = Field(default=None, min_length=1)
    sku: str | None = Field(default=None, min_length=1)
    upc: str | None = Field(default=None, min_length=1)
    brand: str | None = Field(default=None, min_length=1)
    model_number: str | None = Field(default=None, min_length=1)

    @field_validator("title")
    @classmethod
    def strip_title(cls, value: str) -> str:
        """Normalize whitespace for title."""
        return value.strip()
