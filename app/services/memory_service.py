"""
Memory Service for loading conversation history from threads.

This service loads the last 5 conversation pairs from a thread and formats them
for inclusion in the LLM prompt.
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID
from typing import List, Optional

from app.models.message import Message
from app.models.thread import Thread


async def validate_thread_ownership(
    db: AsyncSession,
    thread_id: UUID,
    user_id: UUID
) -> bool:
    """
    Validate that a thread belongs to the specified user.
    
    Args:
        db: Database session
        thread_id: ID of the thread
        user_id: ID of the user
        
    Returns:
        True if thread belongs to user, False otherwise
    """
    result = await db.execute(
        select(Thread).where(
            Thread.id == thread_id,
            Thread.user_id == user_id
        )
    )
    thread = result.scalar_one_or_none()
    return thread is not None


async def get_recent_conversations(
    db: AsyncSession,
    thread_id: UUID,
    user_id: UUID,
    limit: int = 5
) -> Optional[List[dict]]:
    """
    Get the last N conversation pairs from a thread.
    
    Security: Validates thread ownership before returning messages.
    
    Args:
        db: Database session
        thread_id: ID of the thread
        user_id: ID of the authenticated user
        limit: Maximum number of conversation pairs to retrieve (default: 5)
        
    Returns:
        List of conversation dicts with 'message' and 'response' keys,
        ordered chronologically (oldest first).
        Returns None if thread doesn't exist or doesn't belong to user.
    """
    # Validate thread ownership
    thread_exists = await validate_thread_ownership(db, thread_id, user_id)
    if not thread_exists:
        return None
    
    # Query the last N messages from the thread, then restore chronological order.
    result = await db.execute(
        select(Message)
        .where(Message.thread_id == thread_id)
        .order_by(Message.created_at.desc())
        .limit(limit)
    )

    messages = list(reversed(result.scalars().all()))
    
    # Convert to list of conversation dicts
    conversations = []
    for msg in messages:
        conversations.append({
            "message": msg.message,
            "response": msg.response
        })
    
    return conversations


def build_conversation_history(conversations: List[dict]) -> str:
    """
    Build a formatted conversation history string from message pairs.
    
    Args:
        conversations: List of conversation dicts with 'message' and 'response' keys
        
    Returns:
        Formatted conversation history string for LLM prompt
    """
    if not conversations:
        return ""
    
    history_lines = ["Previous conversation:"]
    
    for conv in conversations:
        history_lines.append(f"User: {conv['message']}")
        history_lines.append(f"Assistant: {conv['response']}")
    
    history_lines.append("")  # Add blank line before current message
    
    return "\n".join(history_lines)
