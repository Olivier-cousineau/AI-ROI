"""Matching utilities for eBay liquidation alignment."""
from __future__ import annotations

import difflib
import re
import unicodedata
from dataclasses import dataclass
from typing import Iterable

from core.ct_extractors import normalize_model_number


MARKETING_STOPWORDS = {
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
    "free",
    "shipping",
    "livraison",
    "gratuite",
    "exclusive",
    "limited",
    "edition",
    "bundle",
    "lot",
    "pack",
    "combo",
    "kit",
    "set",
}

SIZE_WORDS = {
    "xs",
    "s",
    "m",
    "l",
    "xl",
    "xxl",
    "xxxl",
    "small",
    "medium",
    "large",
    "taille",
    "size",
}

COLOR_WORDS = {
    "black",
    "white",
    "red",
    "blue",
    "green",
    "yellow",
    "orange",
    "pink",
    "purple",
    "silver",
    "grey",
    "gray",
    "gold",
    "brown",
    "beige",
    "navy",
}

TITLE_STOPWORDS = {
    "with",
    "for",
    "and",
    "the",
    "a",
    "an",
    "de",
    "avec",
    "pour",
    "sur",
} | MARKETING_STOPWORDS


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
    tokens = [
        token
        for token in cleaned.split()
        if token not in MARKETING_STOPWORDS and token not in SIZE_WORDS and token not in COLOR_WORDS
    ]
    return " ".join(tokens)


def normalize_brand(brand: str | None) -> str | None:
    if not brand:
        return None
    cleaned = _basic_normalize(brand)
    cleaned = re.sub(r"\b(inc|ltd|llc|co|corp|corporation)\b", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned or None


def normalize_model(model: str | None) -> str | None:
    if not model:
        return None
    return normalize_model_number(model)


def normalize_part_number(value: str | None) -> str | None:
    if not value:
        return None
    return normalize_model_number(value)


def normalize_upc(upc: str | None) -> str | None:
    if not upc:
        return None
    cleaned = re.sub(r"\D+", "", str(upc))
    if len(cleaned) < 8:
        return None
    return cleaned


def _tokenize_title(title: str) -> list[str]:
    normalized = normalize_title(title)
    return [token for token in normalized.split() if token and token not in TITLE_STOPWORDS]


def extract_title_tokens(title: str) -> dict[str, list[str] | None]:
    tokens = _tokenize_title(title)
    model_tokens = [token for token in tokens if re.search(r"\d", token)]
    voltage_tokens = [token for token in tokens if re.fullmatch(r"\d{2,3}v", token)]
    capacity_tokens = [
        token
        for token in tokens
        if re.fullmatch(r"\d+(?:gb|tb|mb)", token) or re.fullmatch(r"\d+(?:l|ah)", token)
    ]
    dimensions = re.findall(r"\d+(?:\.\d+)?\s?[x×]\s?\d+(?:\.\d+)?(?:\s?[x×]\s?\d+(?:\.\d+)?)?", title)
    return {
        "tokens": tokens,
        "model_tokens": model_tokens,
        "voltage_tokens": voltage_tokens,
        "capacity_tokens": capacity_tokens,
        "dimensions": dimensions or None,
    }


def jaccard_similarity(tokens_a: Iterable[str], tokens_b: Iterable[str]) -> float:
    set_a = {token for token in tokens_a if token}
    set_b = {token for token in tokens_b if token}
    if not set_a or not set_b:
        return 0.0
    return len(set_a & set_b) / len(set_a | set_b)


def sequence_similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return difflib.SequenceMatcher(None, a, b).ratio()


def title_similarity(title_a: str, title_b: str) -> float:
    tokens_a = _tokenize_title(title_a)
    tokens_b = _tokenize_title(title_b)
    jaccard = jaccard_similarity(tokens_a, tokens_b)
    seq = sequence_similarity(normalize_title(title_a), normalize_title(title_b))
    return round((0.6 * jaccard) + (0.4 * seq), 4)


def has_model_match(model_norm: str | None, title: str | None) -> tuple[bool, bool]:
    if not model_norm or not title:
        return False, False
    normalized_title = re.sub(r"[^A-Z0-9]+", " ", str(title).upper()).strip()
    normalized_compact = re.sub(r"[^A-Z0-9]+", "", str(title).upper())
    if not normalized_title:
        return False, False
    escaped = re.escape(model_norm)
    exact = bool(re.search(rf"(?<![A-Z0-9]){escaped}(?![A-Z0-9])", normalized_title))
    partial = model_norm in normalized_compact
    return exact, partial


def has_brand_match(brand_norm: str | None, title: str | None, brand_field: str | None = None) -> bool:
    if not brand_norm:
        return False
    if brand_field:
        brand_field_norm = normalize_brand(brand_field)
        if brand_field_norm and brand_field_norm == brand_norm:
            return True
    if title:
        normalized_title = normalize_title(title)
        return brand_norm in normalized_title.split()
    return False


def has_part_match(part_norm: str | None, title: str | None, mpn: str | None = None) -> tuple[bool, bool]:
    if not part_norm:
        return False, False
    if mpn:
        normalized_mpn = normalize_part_number(mpn)
        if normalized_mpn and normalized_mpn == part_norm:
            return True, True
    return has_model_match(part_norm, title)


@dataclass
class MatchSignals:
    brand_match: bool
    model_match: bool
    model_exact: bool
    part_number_match: bool
    title_similarity: float
    upc_match: bool
    image_match: bool
    image_match_score: float


def score_candidate(
    signals: MatchSignals,
    require_brand: bool = False,
) -> float:
    if signals.upc_match:
        return 0.98
    if signals.brand_match and (signals.model_exact or signals.part_number_match):
        return 0.92
    if require_brand and not signals.brand_match:
        return 0.0
    score = (
        (0.35 if signals.model_match else 0.0)
        + (0.35 if signals.part_number_match else 0.0)
        + (0.25 if signals.brand_match else 0.0)
        + (0.25 * signals.title_similarity)
        + (0.05 * signals.image_match_score)
    )
    return round(min(0.91, score), 4)
