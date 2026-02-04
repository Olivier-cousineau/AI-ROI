"""Utilities for stable deal key construction."""
from __future__ import annotations


def make_deal_key(
    source: str,
    sku: str | None,
    url: str | None,
    normalized_title: str | None,
) -> str:
    """Create a stable key for deal de-duplication and joins."""
    source_prefix = source.strip().lower() if source else "unknown"
    if source_prefix == "canadian tire":
        if sku:
            return f"ct|sku:{sku}"
        if url:
            return f"ct|url:{url}"
        title_value = normalized_title or ""
        return f"ct|title:{title_value}"

    if sku:
        return f"{source_prefix}|sku:{sku}"
    if url:
        return f"{source_prefix}|url:{url}"
    title_value = normalized_title or ""
    return f"{source_prefix}|title:{title_value}"
