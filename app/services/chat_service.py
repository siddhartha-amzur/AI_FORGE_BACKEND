from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
from uuid import UUID

from app.models.chat import Chat
from app.schemas.chat import ChatCreate


async def save_chat(db: AsyncSession, chat_data: ChatCreate) -> Chat:
    """Save a chat message and response to database"""
    new_chat = Chat(
        user_id=chat_data.user_id,
        message=chat_data.message,
        response=chat_data.response
    )
    
    db.add(new_chat)
    await db.commit()
    await db.refresh(new_chat)
    
    return new_chat


async def get_user_chats(db: AsyncSession, user_id: UUID) -> List[Chat]:
    """Get all chats for a user, ordered by created_at"""
    result = await db.execute(
        select(Chat)
        .where(Chat.user_id == user_id)
        .order_by(Chat.created_at.asc())
    )
    return result.scalars().all()
