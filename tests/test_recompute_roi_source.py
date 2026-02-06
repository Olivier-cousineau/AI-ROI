import json

from scripts.recompute_roi import compute_results, write_output, write_roi_output


def test_recompute_roi_outputs_bestbuy_source(tmp_path) -> None:
    items = [
        {
            "deal": {
                "title": "BestBuy Camera Kit",
                "price_sale": 100.0,
                "price_regular": 150.0,
                "brand": "BestBuy",
                "model_number": "BB-100",
                "url": "https://www.bestbuy.ca/en-ca/product/bb-100/12345",
                "image": "https://www.bestbuy.ca/image.jpg",
            },
            "market": {
                "ebay_price": 200.0,
                "match_confidence": 0.9,
                "ebay_item_id": "v1|999|0",
                "ebay_title": "BestBuy Camera Kit BB-100",
                "ebay_item_web_url": "https://ebay.example/item",
                "ebay_image": "https://ebay.example/bestbuy-bb-100.jpg",
                "ebay_shipping": "20.00",
                "ebay_condition": "New",
                "is_confirmed": True,
            },
            "keepa": {"sales_per_month": 5, "avg_price": 210, "rank": 20000},
        }
    ]

    results = compute_results(items, shipping_floor=8.99, shipping_rate=0.1)
    output_path = tmp_path / "marketplace.json"
    roi_path = tmp_path / "roi_results.json"

    write_output(
        output_path,
        results,
        count_total=len(items),
        top=10,
        source="BestBuy",
        input_file="input/bestbuy/index/deals-80.json",
    )
    write_roi_output(
        roi_path,
        results,
        source="BestBuy",
        input_file="input/bestbuy/index/deals-80.json",
    )

    output_payload = json.loads(output_path.read_text())
    roi_payload = json.loads(roi_path.read_text())

    assert output_payload["source"] == "BestBuy"
    assert roi_payload["source"] == "BestBuy"
    assert output_payload["input_file"] == "input/bestbuy/index/deals-80.json"
    assert roi_payload["input_file"] == "input/bestbuy/index/deals-80.json"
