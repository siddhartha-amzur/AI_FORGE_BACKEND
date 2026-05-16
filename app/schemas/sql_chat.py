from __future__ import annotations

from pydantic import BaseModel, Field
from uuid import UUID

from app.schemas.query_result import QueryResult


class SQLChatRequest(BaseModel):
    message: str = Field(min_length=1)
    thread_id: UUID
    page: int = 1
    page_size: int = 50
    source_id: UUID | None = None


class SQLChatResponse(BaseModel):
    thread_id: UUID
    result: QueryResult
