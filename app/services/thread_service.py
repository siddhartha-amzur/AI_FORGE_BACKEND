from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from typing import List
from uuid import UUID

from app.models.thread import Thread
from app.models.message import Message
from app.schemas.thread import ThreadCreate, ThreadUpdate


async def create_thread(db: AsyncSession, user_id: UUID, title: str = "New Chat") -> Thread:
    """Create a new thread"""
    new_thread = Thread(
        user_id=user_id,
        title=title
    )
    
    db.add(new_thread)
    await db.commit()
    await db.refresh(new_thread)
    
    return new_thread


async def get_user_threads(db: AsyncSession, user_id: UUID) -> List[Thread]:
    """Get all threads for a user, ordered by created_at desc"""
    result = await db.execute(
        select(Thread)
        .where(Thread.user_id == user_id)
        .order_by(Thread.created_at.desc())
    )
    return result.scalars().all()


async def get_thread_by_id(db: AsyncSession, thread_id: UUID, user_id: UUID) -> Thread:
    """Get a thread by ID (with user verification)"""
    result = await db.execute(
        select(Thread)
        .where(Thread.id == thread_id, Thread.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def update_thread(db: AsyncSession, thread_id: UUID, user_id: UUID, title: str) -> Thread:
    """Update thread title"""
    thread = await get_thread_by_id(db, thread_id, user_id)
    
    if not thread:
        return None
    
    thread.title = title
    await db.commit()
    await db.refresh(thread)
    
    return thread


async def delete_thread(db: AsyncSession, thread_id: UUID, user_id: UUID) -> bool:
    """Delete a thread and all its messages"""
    thread = await get_thread_by_id(db, thread_id, user_id)
    
    if not thread:
        return False
    
    await db.delete(thread)
    await db.commit()
    
    return True


async def get_thread_messages(db: AsyncSession, thread_id: UUID, user_id: UUID) -> List[Message]:
    """Get all messages in a thread"""
    # First verify thread belongs to user
    thread = await get_thread_by_id(db, thread_id, user_id)
    
    if not thread:
        return None
    
    result = await db.execute(
        select(Message)
        .where(Message.thread_id == thread_id)
        .order_by(Message.created_at.asc())
    )
    return result.scalars().all()


async def save_message(db: AsyncSession, thread_id: UUID, message: str, response: str) -> Message:
    """Save a message to a thread"""
    new_message = Message(
        thread_id=thread_id,
        message=message,
        response=response
    )
    
    db.add(new_message)
    await db.commit()
    await db.refresh(new_message)
    
    return new_message


def generate_thread_title(first_message: str, max_length: int = 40) -> str:
    """Generate thread title from first message"""
    if len(first_message) <= max_length:
        return first_message
    
    # Trim to max_length and add ellipsis
    return first_message[:max_length - 3].strip() + "..."
