from pydantic import BaseModel
from datetime import datetime
from uuid import UUID


class ChatCreate(BaseModel):
    """Schema for creating a chat (used internally)"""
    user_id: UUID
    message: str
    response: str


class ChatResponse(BaseModel):
    """Schema for chat response"""
    id: int
    user_id: UUID
    message: str
    response: str
    created_at: datetime
    
    class Config:
        from_attributes = True
