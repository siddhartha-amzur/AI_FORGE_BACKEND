from __future__ import annotations

import json
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.models.sql_query_history import SQLQueryHistory


async def record_query(
    db: AsyncSession,
    *,
    user_id: UUID,
    thread_id: UUID,
    source_type: str,
    question: str,
    sql: str,
    sql_explanation: str,
    summary: str,
    filters: dict,
    aggregations: dict,
    result_preview: list[dict],
) -> SQLQueryHistory:
    """Record query to history. Handles transaction rollback on error."""
    try:
        item = SQLQueryHistory(
            user_id=user_id,
            thread_id=thread_id,
            source_type=source_type,
            question=question,
            generated_sql=sql,
            sql_explanation=sql_explanation,
            result_summary=summary,
            filters_json=json.dumps(filters),
            aggregations_json=json.dumps(aggregations),
            result_preview_json=json.dumps(result_preview),
        )
        db.add(item)
        await db.flush()
        await db.refresh(item)
        return item
    except Exception as exc:
        await db.rollback()
        raise


async def get_recent_sql_history(
    db: AsyncSession,
    *,
    user_id: UUID,
    thread_id: UUID,
    limit: int = 5,
) -> list[SQLQueryHistory]:
    result = await db.execute(
        select(SQLQueryHistory)
        .where(SQLQueryHistory.user_id == user_id, SQLQueryHistory.thread_id == thread_id)
        .order_by(SQLQueryHistory.created_at.desc())
        .limit(limit)
    )
    return list(reversed(result.scalars().all()))


def build_sql_memory_context(items: list[SQLQueryHistory]) -> str:
    if not items:
        return ""

    lines = ["Recent SQL memory:"]
    for item in items:
        lines.append(f"Question: {item.question}")
        lines.append(f"SQL: {item.generated_sql}")
        lines.append(f"Explanation: {item.sql_explanation}")
        lines.append(f"Summary: {item.result_summary}")
        lines.append(f"Filters: {item.filters_json}")
        lines.append(f"Aggregations: {item.aggregations_json}")
        lines.append("-")
    return "\n".join(lines)
