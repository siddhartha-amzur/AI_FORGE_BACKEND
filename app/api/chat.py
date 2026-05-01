from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.services.chatbot import chatbot_service


router = APIRouter()


class ChatRequest(BaseModel):
    """Request model for chat endpoint"""
    message: str


class ChatResponse(BaseModel):
    """Response model for chat endpoint"""
    response: str


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Chat endpoint - sends user message to Gemini and returns AI response
    
    Args:
        request: ChatRequest containing user message
        
    Returns:
        ChatResponse with AI-generated response
    """
    if not request.message or not request.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")
    
    try:
        ai_response = await chatbot_service.get_response(request.message)
        return ChatResponse(response=ai_response)
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
