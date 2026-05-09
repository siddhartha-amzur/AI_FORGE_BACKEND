from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class AttachmentResponse(BaseModel):
    id: UUID
    thread_id: UUID
    message_id: Optional[int] = None
    original_filename: str
    stored_filename: str
    mime_type: str
    file_size: int
    file_path: str
    created_at: datetime

    class Config:
        from_attributes = True