from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.utils.execution_timer import timed_block


async def execute_sql(
    db: AsyncSession,
    *,
    sql: str,
    timeout_ms: int,
    page: int,
    page_size: int,
    max_rows: int,
) -> tuple[list[str], list[dict], int, bool]:
    offset = max(page - 1, 0) * page_size
    limited_page_size = min(page_size, max_rows)
    fetch_limit = limited_page_size + 1

    with timed_block("sql_execution"):
        await db.execute(text(f"SET LOCAL statement_timeout = {timeout_ms}"))
        paged_sql = f"SELECT * FROM ({sql}) AS _q LIMIT :limit OFFSET :offset"
        result = await db.execute(text(paged_sql), {"limit": fetch_limit, "offset": offset})
        rows = result.mappings().all()

    has_more = len(rows) > limited_page_size
    visible_rows = rows[:limited_page_size]
    columns = list(visible_rows[0].keys()) if visible_rows else []
    total_rows_estimate = offset + len(visible_rows) + (1 if has_more else 0)
    return columns, [dict(row) for row in visible_rows], total_rows_estimate, has_more
