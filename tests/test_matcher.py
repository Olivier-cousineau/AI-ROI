from __future__ import annotations

from ai.product_matcher import build_queries
from ai.title_normalizer import normalize_title


def test_matcher_case1_title_only() -> None:
    title = "ProForm 550R Rowing Machine - Improved Flywheel"
    normalized = normalize_title(title)
    assert normalized == "proform 550r rowing machine improved flywheel"

    result = build_queries(title)
    assert "proform" in result["amazon_query"]
    assert "550r" in result["amazon_query"]
    assert result["confidence"] >= 0.3


def test_matcher_confidence_brand_sku_increases() -> None:
    title = "Acme 12V Drill"
    base = build_queries(title)
    enriched = build_queries(title, brand="Acme", sku="ACME-12345")
    assert enriched["confidence"] > base["confidence"]


def test_matcher_confidence_upc() -> None:
    title = "ACME 18V Impact Driver"
    result = build_queries(title, brand="ACME", upc="123456789012")
    assert result["confidence"] >= 0.7
