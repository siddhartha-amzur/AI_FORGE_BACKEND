from __future__ import annotations

import json
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.models.active_data_context import ActiveDataContext


async def set_active_context(
    db: AsyncSession,
    *,
    user_id: UUID,
    thread_id: UUID,
    source_type: str,
    source_ref: str,
    context: dict,
) -> ActiveDataContext:
    result = await db.execute(
        select(ActiveDataContext).where(
            ActiveDataContext.user_id == user_id,
            ActiveDataContext.thread_id == thread_id,
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        existing.source_type = source_type
        existing.source_ref = source_ref
        existing.context_json = json.dumps(context)
        existing.updated_at = datetime.utcnow()
        await db.flush()
        await db.refresh(existing)
        return existing

    created = ActiveDataContext(
        user_id=user_id,
        thread_id=thread_id,
        source_type=source_type,
        source_ref=source_ref,
        context_json=json.dumps(context),
    )
    db.add(created)
    await db.flush()
    await db.refresh(created)
    return created


async def get_active_context(db: AsyncSession, *, user_id: UUID, thread_id: UUID) -> ActiveDataContext | None:
    result = await db.execute(
        select(ActiveDataContext).where(
            ActiveDataContext.user_id == user_id,
            ActiveDataContext.thread_id == thread_id,
        )
    )
    return result.scalar_one_or_none()
