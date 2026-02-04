"""Market enrichment orchestrator."""
from __future__ import annotations

import logging

from lib.enrich.amazon_paapi import get_amazon_price
from lib.enrich.ebay_browse import get_ebay_active_median_price


LOGGER = logging.getLogger(__name__)


def enrich_market(items: list[dict[str, str | None]]) -> list[dict[str, float | None]]:
    """Enrich market items with Amazon/eBay pricing when configured."""
    enriched: list[dict[str, float | None]] = []
    for item in items:
        amazon_query = item.get("amazon_query") if isinstance(item, dict) else None
        ebay_query = item.get("ebay_query") if isinstance(item, dict) else None
        amazon_price = get_amazon_price(amazon_query)
        ebay_price = get_ebay_active_median_price(ebay_query)
        enriched.append({"amazon_price": amazon_price, "ebay_price": ebay_price})
    return enriched
