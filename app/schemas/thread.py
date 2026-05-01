from pydantic import BaseModel
from datetime import datetime
from uuid import UUID
from typing import Optional


class ThreadCreate(BaseModel):
    """Schema for creating a new thread"""
    title: Optional[str] = "New Chat"


class ThreadUpdate(BaseModel):
    """Schema for updating a thread"""
    title: str


class ThreadResponse(BaseModel):
    """Schema for thread response"""
    id: UUID
    user_id: UUID
    title: str
    created_at: datetime
    
    class Config:
        from_attributes = True


class MessageResponse(BaseModel):
    """Schema for message response"""
    id: int
    thread_id: UUID
    message: str
    response: str
    created_at: datetime
    
    class Config:
        from_attributes = True
