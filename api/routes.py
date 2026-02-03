"""API routes for AI-ROI."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ai.product_matcher import generate_ebay_query, match_confidence
from ai.title_normalizer import normalize_title
from config.assumptions import Assumptions
from core.roi_engine import compute_roi
from models.roi_model import ComputeRoiRequest, RoiResponse

router = APIRouter()


class MatchRequest(BaseModel):
    """Request payload for product matching."""

    title: str = Field(..., min_length=1)
    brand: str | None = None
    sku: str | None = None
    upc: str | None = None


class MatchResponse(BaseModel):
    """Response payload for product matching."""

    asin: str | None
    confidence: float = Field(..., ge=0, le=1)
    ebay_query: str


@router.post("/compute-roi", response_model=RoiResponse)
def compute_roi_endpoint(payload: ComputeRoiRequest) -> RoiResponse:
    """Compute ROI and scoring based on deal and market data."""
    try:
        assumptions = Assumptions()
        result = compute_roi(
            price_sale=payload.deal.price_sale,
            market=payload.market,
            keepa=payload.keepa,
            assumptions=assumptions,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return RoiResponse(**result)


@router.post("/match", response_model=MatchResponse)
def match_endpoint(payload: MatchRequest) -> MatchResponse:
    """Normalize title and generate a minimal matching response."""
    normalized_title = normalize_title(payload.title)
    ebay_query = generate_ebay_query(
        payload.title,
        payload.brand,
        payload.sku,
        payload.upc,
    )
    confidence = match_confidence(
        normalized_title,
        payload.brand,
        payload.sku,
        payload.upc,
    )
    return MatchResponse(asin=None, confidence=confidence, ebay_query=ebay_query)
