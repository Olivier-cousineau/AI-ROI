"""Canadian Tire-specific extractors."""
from __future__ import annotations

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
