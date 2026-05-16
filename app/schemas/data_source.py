from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel
from uuid import UUID


class DataSourceResponse(BaseModel):
    id: UUID
    user_id: UUID
    thread_id: UUID
    source_type: str
    display_name: str
    location_ref: str
    status: str
    row_count: int
    meta_json: str
    created_at: datetime

    class Config:
        from_attributes = True


class GoogleSheetConnectRequest(BaseModel):
    thread_id: UUID
    url: str
