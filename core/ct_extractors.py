"""Canadian Tire-specific extractors."""
from __future__ import annotations

import re
from typing import Any


PART_NUMBER_FIELDS = [
    "part_number",
    "partNumber",
    "partNumberValue",
    "part_no",
    "partNo",
    "productNumber",
    "itemNumber",
    "partnumber",
    "product_number",
]

MODEL_NUMBER_FIELDS = [
    "model_number",
    "modelNumber",
    "modelNo",
    "model_no",
    "model",
    "modelNumberValue",
]


def extract_part_number(raw: dict[str, Any]) -> str | None:
    """Extract a part number from a raw Canadian Tire payload."""
    for field in PART_NUMBER_FIELDS:
        if field not in raw:
            continue
        value = raw.get(field)
        if value is None:
            continue
        if isinstance(value, int):
            return str(value).strip()
        if isinstance(value, str):
            cleaned = value.strip()
            if cleaned:
                return cleaned
    return None


def extract_model_number(raw: dict[str, Any]) -> str | None:
    """Extract a model number from a raw Canadian Tire payload."""
    for field in MODEL_NUMBER_FIELDS:
        if field not in raw:
            continue
        value = raw.get(field)
        if value is None:
            continue
        if isinstance(value, int):
            return str(value).strip()
        if isinstance(value, str):
            cleaned = value.strip()
            if cleaned:
                return cleaned
    return None


def normalize_model_number(value: str | None) -> str | None:
    """Normalize model numbers for matching."""
    if not value:
        return None
    cleaned = re.sub(r"[^A-Z0-9]", "", str(value).strip().upper())
    return cleaned or None
