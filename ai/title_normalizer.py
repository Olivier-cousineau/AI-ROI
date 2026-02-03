"""Simple title normalization utilities."""
from __future__ import annotations

import re

MARKETING_WORDS = {
    "new",
    "nouveau",
    "promo",
    "promotion",
    "offre",
    "edition",
    "limited",
    "exclusive",
    "premium",
    "best",
    "lot",
    "pack",
}


def normalize_title(title: str) -> str:
    """Normalize a product title for matching."""
    cleaned = title.strip().lower()
    cleaned = re.sub(r"[^a-z0-9\s]", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    words = [word for word in cleaned.split() if word not in MARKETING_WORDS]
    return " ".join(words)
