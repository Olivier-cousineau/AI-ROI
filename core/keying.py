"""Utilities for generating deal keys."""
from __future__ import annotations


def make_deal_key(
    source: str,
    part_number: str | None,
    url: str | None,
    normalized_title: str | None,
) -> str:
    """Build a stable deal key for enrichment joins."""
    source_key = source.strip().lower()
    if source_key in {"canadian tire", "canadiantire", "ct"}:
        source_key = "ct"

    if part_number:
        return f"{source_key}|pn:{part_number}"
    if url:
        return f"{source_key}|url:{url}"
    normalized = normalized_title or ""
    return f"{source_key}|title:{normalized}"
