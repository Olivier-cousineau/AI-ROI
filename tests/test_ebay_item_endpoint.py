from lib.enrich.ebay_item_details import fetch_ebay_item_details


def test_fetch_ebay_item_requires_token_or_cache(monkeypatch) -> None:
    monkeypatch.delenv("EBAY_ACCESS_TOKEN", raising=False)

    payload = fetch_ebay_item_details("v1|foo|0")

    assert payload["ok"] is False
    assert payload["error"] == "missing_token"
