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


def mvp_match(title: str, brand: str | None, sku: str | None, upc: str | None) -> dict[str, str | float | None]:
    """Return a minimal match payload without external calls."""
    normalized_title = normalize_title(title)
    return {
        "asin": None,
        "confidence": 0.0,
        "ebay_query": generate_ebay_query(title, brand, sku, upc),
        "normalized_title": normalized_title,
    }
