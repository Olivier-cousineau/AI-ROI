"""Utilities for generating deal keys."""
from __future__ import annotations

import re


def _normalize_title(title: str) -> str:
    """Normalize a title for keying."""
    cleaned = re.sub(r"[^a-z0-9]+", " ", title.lower())
    return re.sub(r"\s+", " ", cleaned).strip()


def make_deal_key(
    source: str,
    sku: str | None,
    url: str | None,
    title: str | None = None,
) -> str:
    """Build a stable deal key for enrichment joins."""
    source_key = source.strip().lower()
    if source_key in {"canadian tire", "canadiantire", "ct"}:
        source_key = "ct"

    if sku:
        return f"{source_key}|sku:{sku}"
    if url:
        return f"{source_key}|url:{url}"
    if title:
        normalized = _normalize_title(title)
        return f"{source_key}|title:{normalized}"
    return f"{source_key}|title:unknown"
