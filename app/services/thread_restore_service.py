from __future__ import annotations

import json
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.services import data_source_service, datasource_context_service, query_history_service, thread_service


async def get_thread_restore_payload(db: AsyncSession, *, user_id: UUID, thread_id: UUID) -> dict:
    messages = await thread_service.get_thread_messages(db, thread_id, user_id)
    sql_history = await query_history_service.get_recent_sql_history(db, user_id=user_id, thread_id=thread_id, limit=50)
    data_sources = await data_source_service.list_data_sources(db, user_id=user_id, thread_id=thread_id)
    active = await datasource_context_service.get_active_context(db, user_id=user_id, thread_id=thread_id)

    return {
        "messages": [
            {
                "id": message.id,
                "thread_id": str(message.thread_id),
                "message": message.message,
                "response": message.response,
                "created_at": message.created_at.isoformat(),
                "attachments": [
                    {
                        "id": str(attachment.id),
                        "thread_id": str(attachment.thread_id),
                        "message_id": attachment.message_id,
                        "original_filename": attachment.original_filename,
                        "stored_filename": attachment.stored_filename,
                        "mime_type": attachment.mime_type,
                        "file_size": attachment.file_size,
                        "file_path": attachment.file_path,
                        "created_at": attachment.created_at.isoformat(),
                    }
                    for attachment in (message.attachments or [])
                ],
            }
            for message in messages
        ],
        "sql_history": [
            {
                "id": str(item.id),
                "question": item.question,
                "generated_sql": item.generated_sql,
                "sql_explanation": item.sql_explanation,
                "summary": item.result_summary,
                "created_at": item.created_at.isoformat(),
            }
            for item in sql_history
        ],
        "data_sources": [
            {
                "id": str(item.id),
                "user_id": str(item.user_id),
                "thread_id": str(item.thread_id),
                "source_type": item.source_type,
                "display_name": item.display_name,
                "location_ref": item.location_ref,
                "status": item.status,
                "row_count": item.row_count,
                "meta_json": item.meta_json,
                "created_at": item.created_at.isoformat(),
            }
            for item in data_sources
        ],
        "active_context": {
            "source_type": active.source_type,
            "source_ref": active.source_ref,
            "context": json.loads(active.context_json),
        }
        if active
        else None,
    }
