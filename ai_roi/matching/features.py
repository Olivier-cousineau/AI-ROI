from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Optional, Set

from .schemas import ImageSimilarityProvider, MatchSignals, ProductRecord, SemanticSimilarityProvider


_STORAGE_TOKEN = re.compile(r"^(\d+)(gb|tb)$")


def _token_set(value: str) -> Set[str]:
    return {token for token in value.split() if token}


def _jaccard(left: Set[str], right: Set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def _category_match(left_category: Optional[str], right_category: Optional[str]) -> bool:
    if not left_category or not right_category:
        return False
    left_tokens = _token_set(left_category)
    right_tokens = _token_set(right_category)
    overlap = _jaccard(left_tokens, right_tokens)
    return overlap >= 0.5 or left_category in right_category or right_category in left_category


def _identifier_match(left: str, right: str) -> bool:
    if not left or not right:
        return False
    if left == right:
        return True
    if len(left) >= 12 and len(right) >= 12:
        return left[-12:] == right[-12:]
    return False


def _extract_storage_tokens(tokens: Set[str]) -> Set[str]:
    return {token for token in tokens if _STORAGE_TOKEN.match(token)}


def _detect_variant_conflict(left: ProductRecord, right: ProductRecord) -> bool:
    """Flag likely family match but wrong variant (e.g., 128GB vs 256GB)."""
    if left.model and right.model and left.model != right.model:
        if left.model[:6] == right.model[:6]:
            return True

    left_tokens = _token_set(left.title)
    right_tokens = _token_set(right.title)
    shared = left_tokens & right_tokens
    if not shared:
        return False

    left_storage = _extract_storage_tokens(left_tokens)
    right_storage = _extract_storage_tokens(right_tokens)
    return bool(left_storage and right_storage and left_storage != right_storage)


def compute_signals(
    left: ProductRecord,
    right: ProductRecord,
    semantic_provider: Optional[SemanticSimilarityProvider] = None,
    image_provider: Optional[ImageSimilarityProvider] = None,
) -> MatchSignals:
    """Compute deterministic and soft matching signals for two products."""
    title_tokens_left = _token_set(left.title)
    title_tokens_right = _token_set(right.title)
    token_similarity = _jaccard(title_tokens_left, title_tokens_right)
    lexical_similarity = SequenceMatcher(None, left.title, right.title).ratio()
    title_similarity = max(token_similarity, lexical_similarity)

    semantic_similarity = (
        semantic_provider.similarity(left.title, right.title) if semantic_provider else None
    )
    image_similarity = (
        image_provider.similarity(left.image_url, right.image_url)
        if image_provider and left.image_url and right.image_url
        else None
    )

    brand_match = bool(left.brand and right.brand and left.brand == right.brand)
    brand_conflict = bool(left.brand and right.brand and left.brand != right.brand)

    return MatchSignals(
        upc_match=_identifier_match(left.upc_ean or "", right.upc_ean or ""),
        brand_match=brand_match,
        brand_conflict=brand_conflict,
        model_match=bool(
            (left.model and right.model and left.model == right.model)
            or (left.sku and right.sku and left.sku == right.sku)
        ),
        title_similarity=round(title_similarity, 4),
        semantic_similarity=round(semantic_similarity, 4) if semantic_similarity is not None else None,
        category_match=_category_match(left.category, right.category),
        image_similarity=round(image_similarity, 4) if image_similarity is not None else None,
        variant_conflict=_detect_variant_conflict(left, right),
    )
