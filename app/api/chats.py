from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from app.db.session import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.chat import ChatResponse
from app.services import chat_service

router = APIRouter(prefix="/chats", tags=["Chats"])


@router.get("/", response_model=List[ChatResponse])
async def get_chat_history(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get all chat history for the current user"""
    chats = await chat_service.get_user_chats(db, current_user.id)
    return chats
