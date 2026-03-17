from __future__ import annotations

from typing import Mapping, Optional, Union

from .features import compute_signals
from .normalizer import normalize_product
from .schemas import (
    ImageSimilarityProvider,
    MatchResult,
    MatcherConfig,
    ProductRecord,
    SemanticSimilarityProvider,
)
from .scoring import score_match


class ProductMatcher:
    """AI-assisted, explainable product matcher for retail vs marketplace items."""

    def __init__(
        self,
        config: Optional[MatcherConfig] = None,
        semantic_provider: Optional[SemanticSimilarityProvider] = None,
        image_provider: Optional[ImageSimilarityProvider] = None,
    ) -> None:
        self.config = config or MatcherConfig()
        self.semantic_provider = semantic_provider
        self.image_provider = image_provider

    @staticmethod
    def _coerce_product(product: Union[ProductRecord, Mapping[str, object]]) -> ProductRecord:
        if isinstance(product, ProductRecord):
            return product

        return ProductRecord(
            title=str(product.get("title") or ""),
            brand=_get_optional_str(product, ("brand",)),
            model=_get_optional_str(product, ("model",)),
            sku=_get_optional_str(product, ("sku",)),
            upc_ean=_get_optional_str(product, ("upc_ean", "upc", "ean")),
            category=_get_optional_str(product, ("category",)),
            price=_get_optional_float(product, ("price", "listed_price", "sold_price")),
            condition=_get_optional_str(product, ("condition",)),
            image_url=_get_optional_str(product, ("image_url",)),
        )

    def match(
        self,
        retail_product: Union[ProductRecord, Mapping[str, object]],
        marketplace_product: Union[ProductRecord, Mapping[str, object]],
    ) -> MatchResult:
        """Match two products and return confidence, label, explanation, and signals."""
        retail = normalize_product(self._coerce_product(retail_product))
        market = normalize_product(self._coerce_product(marketplace_product))

        signals = compute_signals(
            retail,
            market,
            semantic_provider=self.semantic_provider,
            image_provider=self.image_provider,
        )
        return score_match(signals, self.config)


def _get_optional_str(payload: Mapping[str, object], keys: tuple[str, ...]) -> Optional[str]:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _get_optional_float(payload: Mapping[str, object], keys: tuple[str, ...]) -> Optional[float]:
    for key in keys:
        value = payload.get(key)
        if value is None:
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return None
