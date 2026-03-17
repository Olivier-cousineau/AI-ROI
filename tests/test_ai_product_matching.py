from __future__ import annotations

from ai_roi.matching import ProductMatcher


def test_exact_match_with_upc_brand_model() -> None:
    matcher = ProductMatcher()
    result = matcher.match(
        {
            "title": "Sony WH-1000XM5 Wireless Noise Cancelling Headphones",
            "brand": "Sony",
            "model": "WH1000XM5",
            "upc": "027242924659",
            "category": "Electronics > Headphones",
        },
        {
            "title": "Sony WH1000XM5 Wireless Headphones New",
            "brand": "SONY",
            "model": "WH-1000XM5",
            "ean": "027242924659",
            "category": "Electronics/Audio/Headphones",
        },
    )

    assert result.match_label == "exact"
    assert result.match_confidence >= 0.9
    assert result.extracted_signals["upc_match"] is True


def test_same_family_wrong_variant() -> None:
    matcher = ProductMatcher()
    result = matcher.match(
        {
            "title": "Samsung Galaxy S23 128GB Black",
            "brand": "Samsung",
            "model": "SM-S911B-128",
            "category": "Electronics > Phones",
        },
        {
            "title": "Samsung Galaxy S23 256GB Noir",
            "brand": "Samsung",
            "model": "SM-S911B-256",
            "category": "Electronics > Cell Phones",
        },
    )

    assert result.extracted_signals["variant_conflict"] is True
    assert result.match_label in {"weak", "no_match"}


def test_wrong_brand_with_similar_title() -> None:
    matcher = ProductMatcher()
    result = matcher.match(
        {
            "title": "Dyson V11 Cordless Vacuum Cleaner",
            "brand": "Dyson",
            "model": "V11",
            "category": "Home > Vacuums",
        },
        {
            "title": "Shark V11 Cordless Vacuum Cleaner",
            "brand": "Shark",
            "model": "V11",
            "category": "Home Appliances > Vacuums",
        },
    )

    assert result.extracted_signals["brand_match"] is False
    assert result.match_label in {"weak", "no_match"}


def test_missing_upc_but_strong_title_and_model() -> None:
    matcher = ProductMatcher()
    result = matcher.match(
        {
            "title": "Ninja Foodi DualZone Air Fryer AF400",
            "brand": "Ninja",
            "model": "AF400",
            "category": "Kitchen > Air Fryers",
        },
        {
            "title": "Ninja AF400 Foodi Dual Zone Air Fryer 9.5L",
            "brand": "Ninja",
            "model": "AF400",
            "category": "Kitchen Appliances > Air Fryers",
        },
    )

    assert result.extracted_signals["upc_match"] is False
    assert result.match_confidence >= 0.7
    assert result.match_label in {"probable", "exact"}


def test_ambiguous_listing_low_confidence() -> None:
    matcher = ProductMatcher()
    result = matcher.match(
        {
            "title": "LEGO Star Wars X-Wing 75355",
            "brand": "LEGO",
            "model": "75355",
            "category": "Toys > Building Sets",
        },
        {
            "title": "Building blocks spaceship set compatible toys",
            "brand": "",
            "category": "Toys",
        },
    )

    assert result.match_label in {"weak", "no_match"}
    assert result.match_confidence < 0.7


def test_bilingual_fr_en_normalization_case() -> None:
    matcher = ProductMatcher()
    result = matcher.match(
        {
            "title": "Cafetière Nespresso Vertuo Plus Deluxe",
            "brand": "Nespresso",
            "model": "VertuoPlus",
            "category": "Maison > Cuisine > Café",
        },
        {
            "title": "Nespresso Vertuo Plus Deluxe Coffee Maker",
            "brand": "Nespresso",
            "model": "Vertuo Plus",
            "category": "Home/Kitchen/Coffee",
        },
    )

    assert result.extracted_signals["brand_match"] is True
    assert result.extracted_signals["model_match"] is True
    assert result.match_label in {"probable", "exact"}
