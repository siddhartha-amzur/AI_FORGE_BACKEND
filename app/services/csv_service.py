from __future__ import annotations

import csv
from io import StringIO
from typing import Any

from app.ai.sql.dataframe_analyzer import detect_column_type


class CSVProcessingError(ValueError):
    pass


def _looks_like_html(text: str) -> bool:
    probe = text.strip().lower()[:800]
    return (
        probe.startswith("<!doctype html")
        or probe.startswith("<html")
        or "<title>temporary redirect</title>" in probe
        or "gse default error" in probe
    )


def parse_csv_bytes(content: bytes, max_preview_rows: int = 50) -> dict[str, Any]:
    text: str
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        text = content.decode("utf-8", errors="replace")

    if _looks_like_html(text):
        raise CSVProcessingError(
            "Received HTML instead of CSV from Google Sheets. "
            "The sheet may be private, not shared correctly, or the export URL redirected."
        )

    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample)
        delimiter = dialect.delimiter
    except Exception:
        delimiter = ","

    reader = csv.DictReader(StringIO(text), delimiter=delimiter)
    if not reader.fieldnames:
        raise CSVProcessingError("CSV file has no header row")

    rows: list[dict[str, Any]] = []
    total_rows = 0
    for raw in reader:
        total_rows += 1
        if len(rows) < max_preview_rows:
            rows.append({key: (value if value != "" else None) for key, value in raw.items()})

    columns = list(reader.fieldnames)
    column_types = {
        column: detect_column_type([row.get(column) for row in rows]) for column in columns
    }

    return {
        "columns": columns,
        "preview_rows": rows,
        "total_rows": total_rows,
        "delimiter": delimiter,
        "column_types": column_types,
    }
