from __future__ import annotations

from scripts.enrich_ebay import _images_look_similar, _tokenize_image_url


def test_tokenize_image_url_extracts_significant_tokens() -> None:
    url = "https://cdn.example.com/images/acme-drill-550r-angle.jpg"
    tokens = _tokenize_image_url(url)
    assert "acme" in tokens
    assert "drill" in tokens
    assert "550r" in tokens


def test_images_look_similar_by_overlap() -> None:
    deal_image = "https://shop.example.com/products/acme-drill-550r-front.jpg"
    ebay_image = "https://i.ebayimg.com/images/g/acme-drill-550r-main.png"
    assert _images_look_similar(deal_image, ebay_image, "Acme")


def test_images_look_similar_rejects_different_images() -> None:
    deal_image = "https://shop.example.com/products/acme-drill-550r-front.jpg"
    ebay_image = "https://i.ebayimg.com/images/g/sony-camera-a7c-main.png"
    assert not _images_look_similar(deal_image, ebay_image, "Acme")
