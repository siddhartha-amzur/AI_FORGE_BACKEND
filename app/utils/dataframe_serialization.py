from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
import math
from typing import Any


MAX_TEXT_CELL_CHARS = 400


def _truncate_text(value: str) -> str:
    if len(value) <= MAX_TEXT_CELL_CHARS:
        return value
    return value[:MAX_TEXT_CELL_CHARS] + "..."


def to_json_value(value: Any) -> Any:
    if value is None:
        return None

    if isinstance(value, (datetime, date)):
        return value.isoformat()

    if isinstance(value, Decimal):
        return float(value)

    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        return value

    # numpy scalars without importing numpy directly
    value_type = type(value).__name__.lower()
    if "int" in value_type and "numpy" in str(type(value)).lower():
        return int(value)
    if "float" in value_type and "numpy" in str(type(value)).lower():
        as_float = float(value)
        if math.isnan(as_float) or math.isinf(as_float):
            return None
        return as_float

    if isinstance(value, str):
        return _truncate_text(value)

    if isinstance(value, (int, bool)):
        return value

    return _truncate_text(str(value))


def serialize_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{key: to_json_value(val) for key, val in row.items()} for row in rows]
