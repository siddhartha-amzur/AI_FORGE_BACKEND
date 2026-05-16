from __future__ import annotations

from app.utils.sql_safety import ensure_read_only_sql


def validate_sql(sql: str) -> str:
    return ensure_read_only_sql(sql)
