"""Simple title normalization utilities."""
from __future__ import annotations

import re
import unicodedata

MARKETING_STOPWORDS = [
    "liquidation",
    "clearance",
    "sale",
    "special",
    "deal",
    "rabais",
    "economisez",
    "promo",
    "promotion",
    "nouveau",
    "new",
    "best",
    "top",
    "free shipping",
    "livraison gratuite",
    "exclusive",
    "limited",
    "edition limitee",
    "bundle",
    "lot",
    "pack",
    "combo",
    "kit",
    "set",
]

MARKETING_WORDS = set(MARKETING_STOPWORDS)
_MARKETING_PATTERNS = [re.compile(rf"\b{re.escape(word)}\b") for word in MARKETING_WORDS]


def _strip_accents(text: str) -> str:
    return "".join(
        char for char in unicodedata.normalize("NFKD", text) if not unicodedata.combining(char)
    )


def _basic_normalize(text: str) -> str:
    cleaned = _strip_accents(text.strip().lower())
    cleaned = re.sub(r"[^a-z0-9\s]", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def normalize_title(title: str) -> str:
    """Normalize a product title for matching."""
    cleaned = _basic_normalize(title)
    for pattern in _MARKETING_PATTERNS:
        cleaned = pattern.sub(" ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    words = [word for word in cleaned.split() if word not in MARKETING_WORDS]
    return " ".join(words)


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
    size_tokens = [
        token
        for token in tokens
        if re.fullmatch(r"\d+(?:\.\d+)?(?:in|inch|cm|mm|ft|oz|lb|lbs|kg|g)?", token)
        or re.fullmatch(r"\d+/\d+", token)
        or re.fullmatch(r"\d+(?:pack|pk)", token)
    ]
    voltage_tokens = [token for token in tokens if re.fullmatch(r"\d{2,3}v", token)]
    capacity_tokens = [
        token
        for token in tokens
        if re.fullmatch(r"\d+(?:gb|tb|mb)", token)
        or re.fullmatch(r"\d+(?:l|ah)", token)
    ]

    return {
        "brand_guess": brand_guess,
        "model_tokens": model_tokens,
        "size_tokens": size_tokens,
        "voltage_tokens": voltage_tokens,
        "capacity_tokens": capacity_tokens,
    }
