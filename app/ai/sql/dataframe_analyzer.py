from __future__ import annotations

from collections import Counter
from datetime import datetime
from typing import Any


def detect_column_type(values: list[Any]) -> str:
    non_null = [value for value in values if value not in (None, "")]
    if not non_null:
        return "unknown"

    numeric_count = 0
    date_count = 0
    for value in non_null:
        if isinstance(value, (int, float)):
            numeric_count += 1
            continue
        if isinstance(value, str):
            try:
                float(value)
                numeric_count += 1
                continue
            except ValueError:
                pass
            for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d-%m-%Y"):
                try:
                    datetime.strptime(value, fmt)
                    date_count += 1
                    break
                except ValueError:
                    continue

    ratio_numeric = numeric_count / len(non_null)
    ratio_date = date_count / len(non_null)
    if ratio_numeric >= 0.8:
        return "numeric"
    if ratio_date >= 0.6:
        return "date"
    return "categorical"


def summarize_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {"summary": "No results found", "column_types": {}}

    columns = list(rows[0].keys())
    column_values = {column: [row.get(column) for row in rows] for column in columns}
    column_types = {column: detect_column_type(values) for column, values in column_values.items()}

    highlights = []
    for column, kind in column_types.items():
        if kind == "categorical":
            counter = Counter(value for value in column_values[column] if value not in (None, ""))
            if counter:
                top_value, count = counter.most_common(1)[0]
                highlights.append(f"{column}: most common is {top_value} ({count})")

    summary = " ; ".join(highlights[:3]) or "Analysis complete"
    return {"summary": summary, "column_types": column_types}
