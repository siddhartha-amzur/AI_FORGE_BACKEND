from __future__ import annotations

from typing import Any


def build_query_result(
    *,
    source_type: str,
    generated_sql: str | None,
    sql_explanation: str | None,
    summary: str,
    columns: list[str],
    rows: list[dict[str, Any]],
    total_rows: int,
    page: int,
    page_size: int,
    has_more: bool,
) -> dict[str, Any]:
    return {
        "source_type": source_type,
        "generated_sql": generated_sql,
        "sql_explanation": sql_explanation,
        "summary": summary,
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total_rows": total_rows,
            "has_more": has_more,
        },
        "columns": columns,
        "rows": rows,
        # Future-ready chart contract placeholder.
        "chart_hints": {
            "recommended": [],
            "x_candidates": [],
            "y_candidates": [],
        },
    }
