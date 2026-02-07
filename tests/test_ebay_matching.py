from __future__ import annotations

from ai.ebay_matcher import match_ebay_candidates


def _candidate(
    item_id: str,
    title: str,
    brand: str | None = None,
    upc: str | None = None,
    image: str | None = None,
) -> dict[str, object]:
    return {
        "item_id": item_id,
        "title": title,
        "brand": brand,
        "upc": upc,
        "price": 149.99,
        "shipping": 12.0,
        "condition": "NEW",
        "image": image,
        "item_web_url": "https://ebay.example/item",
    }


def test_matcher_golden_set() -> None:
    cases = [
        {
            "name": "upc_exact",
            "deal": {
                "title": "Acme A100 Drill 12V",
                "brand": "Acme",
                "model_number": "A100",
                "upc": "123456789012",
            },
            "candidates": [
                _candidate("1", "Acme A100 12V Drill", brand="Acme", upc="123456789012"),
            ],
            "pass_label": "A",
            "expect_status": "matched",
            "expect_reason": "UPC_EXACT",
        },
        {
            "name": "brand_model_exact",
            "deal": {
                "title": "Sony A7C Mirrorless Camera",
                "brand": "Sony",
                "model_number": "A7C",
            },
            "candidates": [
                _candidate("2", "Sony A7C Mirrorless Camera Body", brand="Sony"),
            ],
            "pass_label": "B",
            "expect_status": "matched",
            "expect_reason": "BRAND_MODEL_EXACT",
        },
        {
            "name": "brand_mismatch",
            "deal": {
                "title": "Acme X1 Driver",
                "brand": "Acme",
                "model_number": "X1",
            },
            "candidates": [
                _candidate("3", "OtherBrand X1 Driver", brand="OtherBrand"),
            ],
            "pass_label": "B",
            "expect_status": "unmatched",
            "expect_reason": "NO_VALID_CANDIDATES",
        },
        {
            "name": "model_missing",
            "deal": {
                "title": "Acme ABC123 Drill",
                "brand": "Acme",
                "model_number": "ABC123",
            },
            "candidates": [
                _candidate("4", "Acme Drill 12V", brand="Acme"),
            ],
            "pass_label": "B",
            "expect_status": "unmatched",
            "expect_reason": "NO_VALID_CANDIDATES",
        },
        {
            "name": "title_similarity_low",
            "deal": {
                "title": "Acme Laptop Stand Aluminum",
                "brand": "Acme",
            },
            "candidates": [
                _candidate("5", "Acme Garden Hose 50ft", brand="Acme"),
            ],
            "pass_label": "C",
            "expect_status": "unmatched",
            "expect_reason": "NO_VALID_CANDIDATES",
        },
        {
            "name": "ambiguous",
            "deal": {
                "title": "Craftsman CM200 Impact Driver",
                "brand": "Craftsman",
                "model_number": "CM200",
            },
            "candidates": [
                _candidate("6", "Craftsman CM200 Impact Driver", brand="Craftsman"),
                _candidate("7", "Craftsman CM200 Impact Driver Kit", brand="Craftsman"),
            ],
            "pass_label": "C",
            "expect_status": "ambiguous",
            "expect_reason": "AMBIGUOUS_MATCH",
        },
        {
            "name": "fallback_not_perfect",
            "deal": {
                "title": "Acme Z10 Wireless Headphones",
                "brand": "Acme",
                "model_number": "Z10",
            },
            "candidates": [
                _candidate("8", "Acme Z10 Headphones", brand="Acme"),
            ],
            "pass_label": "C",
            "expect_status": "unmatched",
            "expect_reason": "NOT_PERFECT_MATCH",
        },
        {
            "name": "upc_mismatch_pass_a",
            "deal": {
                "title": "Acme Q5 Speaker",
                "brand": "Acme",
                "model_number": "Q5",
                "upc": "999999999999",
            },
            "candidates": [
                _candidate("9", "Acme Q5 Speaker", brand="Acme", upc="111111111111"),
            ],
            "pass_label": "A",
            "expect_status": "unmatched",
            "expect_reason": "NO_VALID_CANDIDATES",
        },
        {
            "name": "brand_model_but_low_similarity",
            "deal": {
                "title": "Acme X200 Widget",
                "brand": "Acme",
                "model_number": "X200",
            },
            "candidates": [
                _candidate("10", "Acme X200 Widget Replacement", brand="Acme"),
            ],
            "pass_label": "C",
            "expect_status": "unmatched",
            "expect_reason": "NOT_PERFECT_MATCH",
        },
        {
            "name": "upc_overrides_brand",
            "deal": {
                "title": "Brandless B200 Adapter",
                "brand": "Brandless",
                "model_number": "B200",
                "upc": "012345678901",
            },
            "candidates": [
                _candidate("11", "OtherBrand Adapter", brand="OtherBrand", upc="012345678901"),
            ],
            "pass_label": "A",
            "expect_status": "matched",
            "expect_reason": "UPC_EXACT",
        },
    ]

    for case in cases:
        result = match_ebay_candidates(
            case["deal"],
            case["candidates"],
            case["pass_label"],
            query_used="test",
        )
        assert result.status == case["expect_status"]
        assert case["expect_reason"] in result.reason_codes
