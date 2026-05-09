from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class GenerateImageRequest(BaseModel):
    prompt: str
    thread_id: UUID


class GenerateImageResponse(BaseModel):
    message_type: str = "image_generation"
    image_id: str
    image_url: str
    prompt: str
    thread_id: UUID
    message_id: int


class GeneratedImageRecord(BaseModel):
    id: UUID
    user_id: UUID
    thread_id: UUID
    message_id: Optional[str] = None
    prompt: str
    image_path: str
    mime_type: str
    created_at: datetime

    class Config:
        from_attributes = True
