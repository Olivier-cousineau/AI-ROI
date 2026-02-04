"""Tests for manual enrichment merge."""
from __future__ import annotations

from scripts.merge_enrichment import merge_deals
from core.keying import make_deal_key


def test_merge_enrichment_applies_manual_data() -> None:
    deals = [
        {
            "title": "Widget A",
            "price_sale": 10.0,
            "price_regular": 20.0,
            "partNumber": "12345",
            "url": "https://example.com/a",
            "image": "https://example.com/a.jpg",
        },
        {
            "title": "Widget B",
            "price_sale": 15.0,
            "price_regular": 30.0,
            "url": "https://example.com/b",
        },
    ]

    key = make_deal_key("Canadian Tire", "12345", "https://example.com/a", "widget a")
    assert key == "ct|pn:12345"

    enrichment = [
        {
            "key": key,
            "title_hint": "Widget A",
            "amazon": {"asin": "B0TEST", "price": 99.99, "match_confidence": 0.9},
            "ebay": {"price": 89.99},
            "keepa": {"sales_per_month": 12, "avg_price": 95.0, "rank": 5000},
            "notes": "Manual match.",
        }
    ]

    merged, stats = merge_deals(deals, enrichment)

    assert len(merged) == 2
    first = merged[0]
    second = merged[1]

    assert first["market"]["amazon_price"] == 99.99
    assert first["market"]["ebay_price"] == 89.99
    assert first["market"]["match_confidence"] == 0.9
    assert first["market"]["asin"] == "B0TEST"
    assert first["keepa"]["sales_per_month"] == 12
    assert first["keepa"]["avg_price"] == 95.0
    assert first["keepa"]["rank"] == 5000
    assert first["keepa"]["notes"] == "Manual match."

    assert second["market"]["amazon_price"] is None
    assert second["market"]["ebay_price"] is None
    assert second["market"]["match_confidence"] == 0.0
    assert second["market"]["asin"] is None
    assert second["keepa"]["sales_per_month"] is None

    assert stats["count_total"] == 2
    assert stats["count_enriched"] == 1
    assert stats["count_with_amazon_price"] == 1
    assert stats["count_with_ebay_price"] == 1
    assert stats["count_with_keepa_sales"] == 1
