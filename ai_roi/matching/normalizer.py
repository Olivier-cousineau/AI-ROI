from __future__ import annotations

import re
import unicodedata
from typing import Optional, Set

from .schemas import ProductRecord

NOISE_WORDS: Set[str] = {
    "new",
    "with",
    "for",
    "and",
    "the",
    "edition",
    "pack",
    "pcs",
    "piece",
    "official",
    "clearance",
    "promo",
    "sale",
    "de",
    "le",
    "la",
    "les",
    "et",
    "avec",
    "pour",
}


def _ascii_fold(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(char for char in normalized if not unicodedata.combining(char))


def normalize_text(value: Optional[str]) -> str:
    """Normalize noisy free-text by lowercasing and removing punctuation."""
    if not value:
        return ""
    folded = _ascii_fold(value).lower()
    alnum = re.sub(r"[^a-z0-9\s]", " ", folded)
    compact = re.sub(r"\s+", " ", alnum).strip()
    return compact


def normalize_title(value: Optional[str]) -> str:
    """Normalize title and remove common noise tokens in EN/FR."""
    normalized = normalize_text(value)
    tokens = [tok for tok in normalized.split() if tok not in NOISE_WORDS]
    return " ".join(tokens)


def normalize_brand(value: Optional[str]) -> str:
    """Normalize brand strings and strip legal suffixes."""
    normalized = normalize_text(value)
    normalized = re.sub(r"\b(inc|ltd|llc|corp|company|co)\b", "", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


def normalize_model(value: Optional[str]) -> str:
    """Canonical model representation preserving alphanumeric identity."""
    if not value:
        return ""
    normalized = normalize_text(value)
    return normalized.replace(" ", "").upper()


def normalize_identifier(value: Optional[str]) -> str:
    """Normalize UPC/EAN/SKU style identifiers to digits when possible."""
    if not value:
        return ""
    digits = re.sub(r"\D", "", value)
    return digits.lstrip("0") if digits else normalize_model(value)


def normalize_category(value: Optional[str]) -> str:
    """Normalize hierarchical categories into a simple comparable string."""
    normalized = normalize_text(value)
    return normalized.replace(">", " ").replace("/", " ")


def normalize_product(product: ProductRecord) -> ProductRecord:
    """Return normalized product record for robust cross-market comparison."""
    return ProductRecord(
        title=normalize_title(product.title),
        brand=normalize_brand(product.brand),
        model=normalize_model(product.model),
        sku=normalize_model(product.sku),
        upc_ean=normalize_identifier(product.upc_ean),
        category=normalize_category(product.category),
        price=product.price,
        condition=normalize_text(product.condition),
        image_url=product.image_url,
    )
