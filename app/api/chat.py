from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from typing import Optional

from app.services.chatbot import chatbot_service
from app.db.session import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.services import thread_service


router = APIRouter()


class ChatRequest(BaseModel):
    """Request model for chat endpoint"""
    message: str
    thread_id: Optional[UUID] = None


class ChatResponse(BaseModel):
    """Response model for chat endpoint"""
    response: str
    thread_id: UUID


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Chat endpoint - sends user message to Gemini and returns AI response
    Now requires authentication and saves to thread-based chat history
    
    Args:
        request: ChatRequest containing user message and optional thread_id
        current_user: Authenticated user (from JWT)
        db: Database session
        
    Returns:
        ChatResponse with AI-generated response and thread_id
    """
    if not request.message or not request.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")
    
    try:
        # Get or create thread
        if request.thread_id:
            # Verify thread belongs to user
            thread = await thread_service.get_thread_by_id(db, request.thread_id, current_user.id)
            if not thread:
                raise HTTPException(status_code=404, detail="Thread not found")
        else:
            # Create new thread with title from first message
            title = thread_service.generate_thread_title(request.message)
            thread = await thread_service.create_thread(db, current_user.id, title)
        
        # Get AI response
        ai_response = await chatbot_service.get_response(request.message)
        
        # Save message to thread
        await thread_service.save_message(db, thread.id, request.message, ai_response)
        
        return ChatResponse(response=ai_response, thread_id=thread.id)
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
