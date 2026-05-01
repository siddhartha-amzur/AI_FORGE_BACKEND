from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.chatbot import chatbot_service
from app.db.session import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.chat import ChatCreate
from app.services import chat_service


router = APIRouter()


class ChatRequest(BaseModel):
    """Request model for chat endpoint"""
    message: str


class ChatResponse(BaseModel):
    """Response model for chat endpoint"""
    response: str


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Chat endpoint - sends user message to Gemini and returns AI response
    Now requires authentication and saves chat history to database
    
    Args:
        request: ChatRequest containing user message
        current_user: Authenticated user (from JWT)
        db: Database session
        
    Returns:
        ChatResponse with AI-generated response
    """
    if not request.message or not request.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")
    
    try:
        # Get AI response
        ai_response = await chatbot_service.get_response(request.message)
        
        # Save chat to database
        chat_data = ChatCreate(
            user_id=current_user.id,
            message=request.message,
            response=ai_response
        )
        await chat_service.save_chat(db, chat_data)
        
        return ChatResponse(response=ai_response)
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
