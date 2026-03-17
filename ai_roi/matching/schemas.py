from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Dict, Literal, Optional, Protocol


MatchLabel = Literal["exact", "probable", "weak", "no_match"]


class SemanticSimilarityProvider(Protocol):
    """Optional adapter for semantic title similarity (e.g., embeddings)."""

    def similarity(self, left_title: str, right_title: str) -> Optional[float]:
        """Return a similarity score in [0, 1] or None if unavailable."""


class ImageSimilarityProvider(Protocol):
    """Optional adapter for image similarity between product photos."""

    def similarity(self, left_image_url: str, right_image_url: str) -> Optional[float]:
        """Return a similarity score in [0, 1] or None if unavailable."""


@dataclass
class ProductRecord:
    """Canonical product schema used by the matcher."""

    title: str
    brand: Optional[str] = None
    model: Optional[str] = None
    sku: Optional[str] = None
    upc_ean: Optional[str] = None
    category: Optional[str] = None
    price: Optional[float] = None
    condition: Optional[str] = None
    image_url: Optional[str] = None


@dataclass
class MatchSignals:
    """Feature-level matching signals for explainability and debugging."""

    upc_match: bool = False
    brand_match: bool = False
    brand_conflict: bool = False
    model_match: bool = False
    title_similarity: float = 0.0
    semantic_similarity: Optional[float] = None
    category_match: bool = False
    image_similarity: Optional[float] = None
    variant_conflict: bool = False

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


@dataclass
class MatcherConfig:
    """Configurable weights and thresholds for hybrid scoring."""

    weights: Dict[str, float] = field(
        default_factory=lambda: {
            "upc_match": 0.45,
            "brand_match": 0.15,
            "model_match": 0.2,
            "title_similarity": 0.15,
            "category_match": 0.05,
            "semantic_similarity": 0.1,
            "image_similarity": 0.1,
        }
    )
    thresholds: Dict[MatchLabel, float] = field(
        default_factory=lambda: {
            "exact": 0.9,
            "probable": 0.7,
            "weak": 0.45,
            "no_match": 0.0,
        }
    )
    brand_mismatch_penalty: float = 0.35
    variant_mismatch_penalty: float = 0.25


@dataclass
class MatchResult:
    """Final matcher output for downstream ROI workflows."""

    match_confidence: float
    match_label: MatchLabel
    explanation: str
    extracted_signals: Dict[str, object]
