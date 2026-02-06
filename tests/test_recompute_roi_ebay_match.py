from scripts.recompute_roi import compute_results


def test_compute_results_adds_ebay_match_payload() -> None:
    items = [
        {
            "deal": {
                "title": "Mastercraft Impact Wrench 20V",
                "price_sale": 99.99,
                "price_regular": 199.99,
                "brand": "Mastercraft",
                "part_number": "MC-20V-100",
                "model_number": "20V-100",
                "url": "https://ct.example/item",
                "image": "https://ct.example/mastercraft-20v-100-image.jpg",
            },
            "market": {
                "ebay_price": 149.99,
                "match_confidence": 0.9,
                "ebay_item_id": "v1|123|0",
                "ebay_title": "Mastercraft 20V-100 Impact Wrench MC-20V-100",
                "ebay_item_web_url": "https://ebay.example/item",
                "ebay_image": "https://ebay.example/mastercraft-20v-100-image.jpg",
                "ebay_shipping": "14.99",
                "ebay_condition": "New",
                "ebay_seller": {"username": "seller-a", "feedback_percent": "99.7"},
                "is_confirmed": True,
            },
            "keepa": {"sales_per_month": 5, "avg_price": 150, "rank": 20000},
        }
    ]

    results = compute_results(items, shipping_floor=8.99, shipping_rate=0.1)

    assert len(results) == 1
    ebay_match = results[0]["ebay_match"]
    assert ebay_match is not None
    assert ebay_match["item_id"] == "v1|123|0"
    assert ebay_match["price"] == 149.99
    assert ebay_match["shipping"] == 14.99
    assert ebay_match["match_confidence"] == "HIGH"
    assert ebay_match["match_signals"]["model_match"] is True
    assert ebay_match["match_signals"]["image_match"] is True
    assert ebay_match["match_signals"]["image_match_score"] >= 0.8


def test_compute_results_skips_low_confidence_for_roi() -> None:
    items = [
        {
            "deal": {
                "title": "Mastercraft Impact Wrench 20V",
                "price_sale": 99.99,
                "price_regular": 199.99,
                "brand": "Mastercraft",
                "part_number": "MC-20V-100",
                "model_number": "20V-100",
                "url": "https://ct.example/item",
                "image": "https://ct.example/mastercraft-20v-100.jpg",
            },
            "market": {
                "ebay_price": 149.99,
                "match_confidence": 0.9,
                "ebay_item_id": "v1|123|0",
                "ebay_title": "Completely different listing title",
                "ebay_item_web_url": "https://ebay.example/item",
                "ebay_image": "https://ebay.example/sony-camera.jpg",
                "ebay_shipping": "14.99",
                "ebay_condition": "New",
                "is_confirmed": True,
            },
            "keepa": {"sales_per_month": 5, "avg_price": 150, "rank": 20000},
        }
    ]

    results = compute_results(items, shipping_floor=8.99, shipping_rate=0.1)

    assert results == []
