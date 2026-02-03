"""Deal input model."""
from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class Deal(BaseModel):
    """Represents a deal discovered in the market."""

    title: str = Field(..., min_length=1)
    price_sale: float = Field(..., gt=0)
    price_regular: float | None = Field(default=None, gt=0)
    source: str | None = Field(default=None, min_length=1)

    @field_validator("title")
    @classmethod
    def strip_title(cls, value: str) -> str:
        """Normalize whitespace for title."""
        return value.strip()
