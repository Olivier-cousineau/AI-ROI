"""MVP product matching helpers."""
from __future__ import annotations

import re

from ai.title_normalizer import extract_key_tokens, normalize_title


def _is_allowed_token(token: str) -> bool:
    if len(token) > 2:
        return True
    if re.fullmatch(r"\d+v", token):
        return True
    if token in {"gb", "tb", "v"}:
        return True
    return False


def _unique_tokens(tokens: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for token in tokens:
        if token and token not in seen:
            seen.add(token)
            unique.append(token)
    return unique


def build_queries(
    title: str,
    brand: str | None = None,
    sku: str | None = None,
    upc: str | None = None,
) -> dict[str, str | float | None | dict[str, str | list[str] | None]]:
    """Build query payloads and confidence signals without external calls."""
    normalized_title = normalize_title(title)
    key_tokens = extract_key_tokens(normalized_title)
    model_tokens = [token for token in key_tokens["model_tokens"] if _is_allowed_token(token)]

    normalized_brand = normalize_title(brand) if brand else ""
    title_tokens = [
        token for token in normalized_title.split() if _is_allowed_token(token) and token not in model_tokens
    ]
    important_tokens = title_tokens[:6]
    base_tokens = [normalized_brand] if normalized_brand else []
    base_tokens.extend(model_tokens)
    base_tokens.extend(important_tokens)
    base_tokens = _unique_tokens([token for token in base_tokens if token])
    query = " ".join(base_tokens)

    confidence = 0.20
    if upc and len(upc.strip()) >= 10:
        confidence += 0.30
    if sku and len(sku.strip()) >= 5:
        confidence += 0.20
    if brand:
        confidence += 0.20
    if len(model_tokens) >= 2:
        confidence += 0.10
    confidence = max(0.0, min(1.0, confidence))

    return {
        "normalized_title": normalized_title,
        "amazon_query": query,
        "ebay_query": query,
        "key_tokens": key_tokens,
        "confidence": confidence,
        "asin": None,
    }


def mvp_match(
    title: str, brand: str | None, sku: str | None, upc: str | None
) -> dict[str, str | float | None | dict[str, str | list[str] | None]]:
    """Return a minimal match payload without external calls."""
    return build_queries(title=title, brand=brand, sku=sku, upc=upc)
