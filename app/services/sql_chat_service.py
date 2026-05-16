from __future__ import annotations

import json
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.sql.schema_loader import build_relevant_schema_context
from app.ai.sql.sql_executor import execute_sql
from app.ai.sql.sql_explainer import explain_results
from app.ai.sql.sql_generator import generate_sql
from app.ai.sql.sql_retry_service import repair_sql_once
from app.ai.sql.sql_validator import validate_sql
from app.core.config import get_settings
from app.services import (
    data_source_service,
    dataframe_service,
    datasource_context_service,
    query_history_service,
    thread_service,
)
from app.utils.dataframe_serialization import serialize_rows
from app.utils.response_formatter import build_query_result


def _derive_filters_and_aggregations(question: str) -> tuple[dict, dict]:
    lowered = question.lower()
    filters = {}
    aggregations = {}
    if "only from" in lowered:
        filters["only_from"] = lowered.split("only from", 1)[1].strip()
    if "top" in lowered:
        aggregations["top"] = True
    if "sum" in lowered or "total" in lowered:
        aggregations["sum"] = True
    if "count" in lowered:
        aggregations["count"] = True
    return filters, aggregations


async def _run_postgres_sql_flow(
    db: AsyncSession,
    *,
    user_id: UUID,
    thread_id: UUID,
    message: str,
    page: int,
    page_size: int,
) -> dict:
    settings = get_settings()

    recent = await query_history_service.get_recent_sql_history(db, user_id=user_id, thread_id=thread_id)
    memory_context = query_history_service.build_sql_memory_context(recent)
    schema_context = await build_relevant_schema_context(
        db,
        question=message,
        cache_key=f"{thread_id}:{message[:50].lower()}",
    )

    try:
        generated_sql, sql_explanation = await generate_sql(
            question=message,
            schema_context=schema_context,
            memory_context=memory_context,
        )
        generated_sql = validate_sql(generated_sql)
    except Exception:
        generated_sql = "SELECT 'No queryable business tables found for this request.' AS message"
        sql_explanation = "Fallback SQL was used because generation output could not be parsed safely."

    try:
        columns, rows, total_rows, has_more = await execute_sql(
            db,
            sql=generated_sql,
            timeout_ms=settings.SQL_QUERY_TIMEOUT_MS,
            page=page,
            page_size=page_size,
            max_rows=settings.SQL_MAX_RETURN_ROWS,
        )
    except Exception as exc:
        try:
            repaired_sql, repaired_explanation = await repair_sql_once(
                question=message,
                schema_context=schema_context,
                prior_sql=generated_sql,
                db_error=str(exc),
            )
            repaired_sql = validate_sql(repaired_sql)
            columns, rows, total_rows, has_more = await execute_sql(
                db,
                sql=repaired_sql,
                timeout_ms=settings.SQL_QUERY_TIMEOUT_MS,
                page=page,
                page_size=page_size,
                max_rows=settings.SQL_MAX_RETURN_ROWS,
            )
            generated_sql = repaired_sql
            sql_explanation = repaired_explanation or sql_explanation
        except Exception:
            columns = ["message"]
            rows = [{"message": "Query could not be executed safely. Please refine your request."}]
            total_rows = 1
            has_more = False
            sql_explanation = "Automatic retry was attempted once and safely stopped."

    serialized_rows = serialize_rows(rows)
    business_summary = await explain_results(question=message, sql=generated_sql, rows=serialized_rows)

    filters, aggregations = _derive_filters_and_aggregations(message)
    await query_history_service.record_query(
        db,
        user_id=user_id,
        thread_id=thread_id,
        source_type="postgres",
        question=message,
        sql=generated_sql,
        sql_explanation=sql_explanation,
        summary=business_summary,
        filters=filters,
        aggregations=aggregations,
        result_preview=serialized_rows[:10],
    )

    await datasource_context_service.set_active_context(
        db,
        user_id=user_id,
        thread_id=thread_id,
        source_type="postgres",
        source_ref="postgres://default",
        context={"last_sql": generated_sql, "filters": filters, "aggregations": aggregations},
    )

    return build_query_result(
        source_type="postgres",
        generated_sql=generated_sql,
        sql_explanation=sql_explanation,
        summary=business_summary,
        columns=columns,
        rows=serialized_rows,
        total_rows=total_rows,
        page=page,
        page_size=page_size,
        has_more=has_more,
    )


async def _run_dataframe_flow(
    db: AsyncSession,
    *,
    user_id: UUID,
    thread_id: UUID,
    message: str,
    page: int,
    page_size: int,
    source_id: UUID | None,
) -> dict:
    source_rows = []
    source_type = "unknown"

    if source_id:
        source = await data_source_service.get_data_source(db, source_id=source_id, user_id=user_id, thread_id=thread_id)
        if not source:
            raise ValueError("Data source not found")
        source_type = source.source_type
        context_obj = json.loads(source.meta_json or "{}")
        source_rows = context_obj.get("preview_rows", [])
    else:
        active = await datasource_context_service.get_active_context(db, user_id=user_id, thread_id=thread_id)
        if not active:
            raise ValueError("No active data source for this thread")
        source_type = active.source_type
        context_obj = json.loads(active.context_json or "{}")
        source_rows = context_obj.get("preview_rows", [])

    analysis = dataframe_service.apply_safe_dataframe_analysis(source_rows, message)
    rows = serialize_rows(analysis.get("rows", []))
    total_rows = len(rows)
    start = max(page - 1, 0) * page_size
    end = start + page_size
    paged_rows = rows[start:end]
    has_more = total_rows > end

    filters, aggregations = _derive_filters_and_aggregations(message)
    await query_history_service.record_query(
        db,
        user_id=user_id,
        thread_id=thread_id,
        source_type=source_type,
        question=message,
        sql="N/A (dataframe mode)",
        sql_explanation="Dataframe operation",
        summary=analysis.get("summary", "Analysis complete"),
        filters=filters,
        aggregations=aggregations,
        result_preview=paged_rows[:10],
    )

    return build_query_result(
        source_type=source_type,
        generated_sql=None,
        sql_explanation=None,
        summary=analysis.get("summary", "Analysis complete"),
        columns=list(paged_rows[0].keys()) if paged_rows else [],
        rows=paged_rows,
        total_rows=total_rows,
        page=page,
        page_size=page_size,
        has_more=has_more,
    )


async def run_sql_chat(
    db: AsyncSession,
    *,
    user_id: UUID,
    thread_id: UUID,
    message: str,
    page: int,
    page_size: int,
    source_id: UUID | None,
) -> dict:
    thread = await thread_service.get_thread_by_id(db, thread_id, user_id)
    if not thread:
        raise ValueError("Thread not found")

    lowered = message.lower()
    blocked_intents = [
        "delete",
        "drop",
        "truncate",
        "update",
        "insert",
        "alter",
        "exec(",
        "eval(",
        "os.system",
        "__import__(",
    ]
    if any(intent in lowered for intent in blocked_intents):
        raise ValueError("Unsafe operation requested. Only read-only analytics questions are allowed.")

    active = await datasource_context_service.get_active_context(db, user_id=user_id, thread_id=thread_id)
    active_type = active.source_type if active else "postgres"

    if source_id is None and active_type == "postgres":
        return await _run_postgres_sql_flow(
            db,
            user_id=user_id,
            thread_id=thread_id,
            message=message,
            page=page,
            page_size=page_size,
        )

    return await _run_dataframe_flow(
        db,
        user_id=user_id,
        thread_id=thread_id,
        message=message,
        page=page,
        page_size=page_size,
        source_id=source_id,
    )
