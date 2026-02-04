from scripts.build_market_ready import build_market_ready


def test_keepa_sales_merge() -> None:
    deals = [
        {
            "title": "Widget A",
            "sku": "123",
            "price_sale": 10.0,
            "price_regular": 20.0,
        },
        {
            "title": "Widget B",
            "sku": "456",
            "price_sale": 15.0,
            "price_regular": 30.0,
        },
    ]
    keepa_index = {"ct|sku:123": 25}

    output, stats = build_market_ready(deals, keepa_index)

    assert stats["count_total"] == 2
    assert output[0]["deal"]["key"] == "ct|sku:123"
    assert output[1]["deal"]["key"] == "ct|sku:456"
    assert output[0]["keepa"]["sales_per_month"] == 25
    assert output[1]["keepa"]["sales_per_month"] is None
