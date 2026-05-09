from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class DocumentResponse(BaseModel):
    id: UUID
    user_id: UUID
    thread_id: Optional[UUID] = None
    filename: str
    original_filename: str
    mime_type: str
    processing_status: str
    created_at: datetime

    class Config:
        from_attributes = True
