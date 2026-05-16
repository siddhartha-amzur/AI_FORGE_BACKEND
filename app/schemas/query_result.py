from __future__ import annotations

from pydantic import BaseModel
from typing import Any


class PaginationMeta(BaseModel):
    page: int
    page_size: int
    total_rows: int
    has_more: bool


class QueryResult(BaseModel):
    source_type: str
    generated_sql: str | None = None
    sql_explanation: str | None = None
    summary: str
    pagination: PaginationMeta
    columns: list[str]
    rows: list[dict[str, Any]]
    chart_hints: dict[str, Any]
