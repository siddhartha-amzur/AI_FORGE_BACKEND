from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.sql_chat import SQLChatRequest, SQLChatResponse
from app.services import sql_chat_service


router = APIRouter(prefix="/sql-chat", tags=["SQL Chat"])


@router.post("", response_model=SQLChatResponse)
async def sql_chat(
    payload: SQLChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await sql_chat_service.run_sql_chat(
            db,
            user_id=current_user.id,
            thread_id=payload.thread_id,
            message=payload.message,
            page=payload.page,
            page_size=payload.page_size,
            source_id=payload.source_id,
        )
        await db.commit()
        return SQLChatResponse(thread_id=payload.thread_id, result=result)
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"error": "sql_chat_failed", "message": str(exc)})
    except Exception as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "sql_chat_failed", "message": str(exc)},
        )
