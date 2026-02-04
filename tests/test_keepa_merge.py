from scripts.build_market_ready import build_market_ready


def test_market_ready_keys() -> None:
    deals = [
        {
            "title": "Widget A",
            "sku": "123",
            "price_sale": 8.0,
            "price_regular": 20.0,
        },
        {
            "title": "Widget B",
            "sku": "456",
            "price_sale": 12.0,
            "price_regular": 30.0,
        },
    ]

    output, stats = build_market_ready(deals)

    assert stats["count_total"] == 2
    assert output[0]["deal"]["key"] == "ct|sku:123"
    assert output[1]["deal"]["key"] == "ct|sku:456"


def test_env_marketplace_cap(monkeypatch) -> None:
    deals = [
        {
            "title": "Widget A",
            "sku": "123",
            "price_sale": 8.0,
            "price_regular": 20.0,
        },
        {
            "title": "Widget B",
            "sku": "456",
            "price_sale": 12.0,
            "price_regular": 30.0,
        },
    ]

    monkeypatch.setenv("MAX_MARKETPLACE_ITEMS", "")

    output, stats = build_market_ready(deals)

    assert stats["count_total"] == 2
    assert stats["count_after_filter"] == 2
    assert len(output) == 2
