"""Simple title normalization utilities."""
from __future__ import annotations

import re


def normalize_title(title: str) -> str:
    """Normalize a product title for matching."""
    cleaned = title.strip().lower()
    cleaned = re.sub(r"[^a-z0-9\s]", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned
