from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.sql.relevant_table_selector import pick_relevant_tables
from app.ai.sql.schema_cache import schema_cache


async def _load_public_tables(db: AsyncSession) -> list[str]:
    query = text(
        """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
        ORDER BY table_name
        """
    )
    rows = (await db.execute(query)).all()
    return [row[0] for row in rows]


async def _load_columns_for_tables(db: AsyncSession, tables: list[str]) -> dict[str, list[str]]:
    if not tables:
        return {}

    query = text(
        """
        SELECT table_name, column_name, data_type
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = ANY(:table_names)
        ORDER BY table_name, ordinal_position
        """
    )
    rows = (await db.execute(query, {"table_names": tables})).all()

    result: dict[str, list[str]] = {table: [] for table in tables}
    for table_name, column_name, data_type in rows:
        result[table_name].append(f"{column_name} ({data_type})")
    return result


async def _load_foreign_keys_for_tables(db: AsyncSession, tables: list[str]) -> dict[str, list[str]]:
    if not tables:
        return {}

    query = text(
        """
        SELECT
            tc.table_name,
            kcu.column_name,
            ccu.table_name AS foreign_table_name,
            ccu.column_name AS foreign_column_name
        FROM information_schema.table_constraints AS tc
        JOIN information_schema.key_column_usage AS kcu
            ON tc.constraint_name = kcu.constraint_name
           AND tc.table_schema = kcu.table_schema
        JOIN information_schema.constraint_column_usage AS ccu
            ON ccu.constraint_name = tc.constraint_name
           AND ccu.table_schema = tc.table_schema
        WHERE tc.constraint_type = 'FOREIGN KEY'
          AND tc.table_schema = 'public'
          AND tc.table_name = ANY(:table_names)
        ORDER BY tc.table_name, kcu.column_name
        """
    )
    rows = (await db.execute(query, {"table_names": tables})).all()

    result: dict[str, list[str]] = {table: [] for table in tables}
    for table_name, column_name, foreign_table_name, foreign_column_name in rows:
        result[table_name].append(
            f"{column_name} -> {foreign_table_name}.{foreign_column_name}"
        )
    return result


async def build_relevant_schema_context(db: AsyncSession, *, question: str, cache_key: str) -> str:
    cached = schema_cache.get(cache_key)
    if cached:
        return cached

    all_tables = await _load_public_tables(db)
    selected = pick_relevant_tables(question, all_tables)
    column_map = await _load_columns_for_tables(db, selected)
    foreign_key_map = await _load_foreign_keys_for_tables(db, selected)

    lines = ["Relevant database schema:"]
    for table in selected:
        lines.append(f"- {table}")
        for column in column_map.get(table, []):
            lines.append(f"  - {column}")
        relationships = foreign_key_map.get(table, [])
        if relationships:
            lines.append("  - foreign_keys:")
            for relationship in relationships:
                lines.append(f"    - {relationship}")

    context = "\n".join(lines)
    schema_cache.set(cache_key, context)
    return context
