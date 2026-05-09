from pathlib import Path
from typing import Dict, List, Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.attachment import Attachment


async def create_attachment(
    db: AsyncSession,
    *,
    user_id: UUID,
    thread_id: UUID,
    original_filename: str,
    stored_filename: str,
    mime_type: str,
    file_size: int,
    file_path: str,
) -> Attachment:
    attachment = Attachment(
        user_id=user_id,
        thread_id=thread_id,
        original_filename=original_filename,
        stored_filename=stored_filename,
        mime_type=mime_type,
        file_size=file_size,
        file_path=file_path,
    )
    db.add(attachment)
    await db.commit()
    await db.refresh(attachment)
    return attachment


async def get_attachment_by_id(db: AsyncSession, attachment_id: UUID, user_id: UUID) -> Attachment | None:
    result = await db.execute(
        select(Attachment).where(
            Attachment.id == attachment_id,
            Attachment.user_id == user_id,
        )
    )
    return result.scalar_one_or_none()


async def get_thread_attachments(db: AsyncSession, thread_id: UUID, user_id: UUID) -> List[Attachment]:
    result = await db.execute(
        select(Attachment)
        .where(
            Attachment.thread_id == thread_id,
            Attachment.user_id == user_id,
        )
        .order_by(Attachment.created_at.asc())
    )
    return result.scalars().all()


async def get_attachments_by_ids(
    db: AsyncSession,
    attachment_ids: Sequence[UUID],
    user_id: UUID,
    thread_id: UUID,
) -> List[Attachment]:
    if not attachment_ids:
        return []

    result = await db.execute(
        select(Attachment).where(
            Attachment.id.in_(attachment_ids),
            Attachment.user_id == user_id,
            Attachment.thread_id == thread_id,
        )
    )
    attachments = result.scalars().all()
    attachment_map = {attachment.id: attachment for attachment in attachments}
    return [attachment_map[attachment_id] for attachment_id in attachment_ids if attachment_id in attachment_map]


async def assign_attachments_to_message(
    db: AsyncSession,
    attachment_ids: Sequence[UUID],
    user_id: UUID,
    thread_id: UUID,
    message_id: int,
) -> None:
    attachments = await get_attachments_by_ids(db, attachment_ids, user_id, thread_id)
    if len(attachments) != len(attachment_ids):
        raise ValueError("One or more attachments are invalid for this thread")

    for attachment in attachments:
        attachment.message_id = message_id


def delete_file_if_exists(file_path: str) -> None:
    path = Path(file_path)
    if path.exists():
        path.unlink()