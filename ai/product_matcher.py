"""MVP product matching helpers."""
from __future__ import annotations

from ai.title_normalizer import normalize_title


def generate_ebay_query(title: str, brand: str | None, sku: str | None, upc: str | None) -> str:
    """Generate an eBay search query string."""
    parts = [normalize_title(title)]
    if brand:
        parts.append(brand.strip())
    if sku:
        parts.append(sku.strip())
    if upc:
        parts.append(upc.strip())
    return " ".join(part for part in parts if part)


def match_confidence(title: str, brand: str | None, sku: str | None, upc: str | None) -> float:
    """Compute a simple confidence score for matching (0-1)."""
    score = 0.0
    if title:
        score += 0.4
    if brand:
        score += 0.2
    if sku:
        score += 0.2
    if upc:
        score += 0.2
    return round(min(score, 1.0), 2)
