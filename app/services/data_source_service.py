from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.models.data_source import DataSource


async def create_data_source(
    db: AsyncSession,
    *,
    user_id: UUID,
    thread_id: UUID,
    source_type: str,
    display_name: str,
    location_ref: str,
    row_count: int,
    status: str = "ready",
    meta_json: str = "{}",
) -> DataSource:
    item = DataSource(
        user_id=user_id,
        thread_id=thread_id,
        source_type=source_type,
        display_name=display_name,
        location_ref=location_ref,
        row_count=row_count,
        status=status,
        meta_json=meta_json,
    )
    db.add(item)
    await db.flush()
    await db.refresh(item)
    return item


async def list_data_sources(db: AsyncSession, *, user_id: UUID, thread_id: UUID) -> list[DataSource]:
    result = await db.execute(
        select(DataSource)
        .where(DataSource.user_id == user_id, DataSource.thread_id == thread_id)
        .order_by(DataSource.created_at.desc())
    )
    return result.scalars().all()


async def get_data_source(db: AsyncSession, *, source_id: UUID, user_id: UUID, thread_id: UUID) -> DataSource | None:
    result = await db.execute(
        select(DataSource).where(
            DataSource.id == source_id,
            DataSource.user_id == user_id,
            DataSource.thread_id == thread_id,
        )
    )
    return result.scalar_one_or_none()


async def delete_data_source(db: AsyncSession, *, source_id: UUID, user_id: UUID, thread_id: UUID) -> bool:
    source = await get_data_source(db, source_id=source_id, user_id=user_id, thread_id=thread_id)
    if not source:
        return False
    await db.execute(
        delete(DataSource).where(
            DataSource.id == source_id,
            DataSource.user_id == user_id,
            DataSource.thread_id == thread_id,
        )
    )
    return True
