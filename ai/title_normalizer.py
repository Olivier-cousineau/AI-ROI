"""Simple title normalization utilities."""
from __future__ import annotations

import re
from ai.match_utils import extract_title_tokens, normalize_brand, normalize_model, normalize_title, normalize_upc


def extract_key_tokens(normalized_title: str) -> dict[str, str | list[str] | None]:
    """Extract key tokens for matching heuristics."""
    tokens = normalized_title.split()
    brand_guess = None
    if tokens and re.fullmatch(r"[a-z]{3,}", tokens[0]):
        brand_guess = tokens[0]

    model_tokens: list[str] = []
    for token in tokens:
        if not re.search(r"\d", token):
            continue
        model_tokens.append(token)
        if re.search(r"[a-z]", token):
            digits = "".join(re.findall(r"\d+", token))
            if digits and digits != token:
                model_tokens.append(digits)
    title_tokens = extract_title_tokens(normalized_title)
    size_tokens = [
        token
        for token in tokens
        if re.fullmatch(r"\d+(?:\.\d+)?(?:in|inch|cm|mm|ft|oz|lb|lbs|kg|g)?", token)
        or re.fullmatch(r"\d+/\d+", token)
        or re.fullmatch(r"\d+(?:pack|pk)", token)
    ]
    voltage_tokens = title_tokens.get("voltage_tokens") or []
    capacity_tokens = title_tokens.get("capacity_tokens") or []

    return {
        "brand_guess": brand_guess,
        "model_tokens": model_tokens,
        "size_tokens": size_tokens,
        "voltage_tokens": voltage_tokens,
        "capacity_tokens": capacity_tokens,
    }


__all__ = [
    "normalize_title",
    "normalize_brand",
    "normalize_model",
    "normalize_upc",
    "extract_key_tokens",
]
