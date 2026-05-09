from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
from uuid import UUID

from app.services.chatbot import chatbot_service
from app.db.session import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.services import attachment_service, file_parser, memory_service, rag_service, thread_service


router = APIRouter()


class ChatRequest(BaseModel):
    """Request model for chat endpoint"""
    message: str = ""
    thread_id: Optional[UUID] = None
    attachment_ids: List[UUID] = Field(default_factory=list)


class ChatResponse(BaseModel):
    """Response model for chat endpoint"""
    response: str
    thread_id: UUID


def error_detail(error: str, message: str):
    return {"error": error, "message": message}


def merge_attachments(current_attachments, recent_attachments):
    merged = []
    seen_ids = set()

    for attachment in [*current_attachments, *recent_attachments]:
        if attachment.id in seen_ids:
            continue
        seen_ids.add(attachment.id)
        merged.append(attachment)

    return merged


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Chat endpoint - sends user message to Gemini and returns AI response.
    Supports thread-based conversations with memory of last 5 conversations.
    
    Args:
        request: ChatRequest containing user message and optional thread_id
        current_user: Authenticated user (from JWT)
        db: Database session
        
    Returns:
        ChatResponse with AI-generated response and thread_id
    """
    if not request.message.strip() and not request.attachment_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_detail("empty_message", "Message or attachments are required"),
        )

    print("[chat] thread_id:", request.thread_id)
    print("[chat] attachment_ids received:", [str(attachment_id) for attachment_id in request.attachment_ids])
    print("[chat] message:", request.message)
    
    try:
        # Get or create thread
        if request.thread_id:
            # Verify thread exists and belongs to user
            thread = await thread_service.get_thread_by_id(
                db, request.thread_id, current_user.id
            )
            if not thread:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=error_detail("thread_not_found", "Thread not found"),
                )
            thread_id = request.thread_id
        else:
            # Create new thread for new conversation
            thread = await thread_service.create_thread(
                db, current_user.id, "New Chat"
            )
            thread_id = thread.id
        
        # Load previous conversations from this thread
        conversations = await memory_service.get_recent_conversations(
            db, thread_id, current_user.id, limit=5
        )

        attachments = await attachment_service.get_attachments_by_ids(
            db,
            request.attachment_ids,
            current_user.id,
            thread_id,
        )
        print("[chat] validated attachment count:", len(attachments))
        for attachment in attachments:
            print("[chat] attachment loaded:", attachment.id, attachment.original_filename, attachment.file_path)
        if len(attachments) != len(request.attachment_ids):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "invalid_attachments",
                    "message": "Attachments must belong to the authenticated user and current thread",
                },
            )
        
        # Build conversation history
        conversation_context = ""
        if conversations:
            conversation_context = memory_service.build_conversation_history(conversations)
        print("[chat] conversation context length:", len(conversation_context))

        recent_messages = await thread_service.get_thread_messages(db, thread_id, current_user.id)
        recent_thread_attachments = []
        if recent_messages:
            for message in recent_messages[-5:]:
                recent_thread_attachments.extend(message.attachments or [])

        if recent_thread_attachments:
            print("[chat] recent thread attachments available:", len(recent_thread_attachments))

        prompt_attachments = merge_attachments(attachments, recent_thread_attachments)
        print("[chat] prompt attachment count:", len(prompt_attachments))

        attachment_context, image_parts = await file_parser.build_attachment_prompt_parts(prompt_attachments)
        print("[chat] attachment context length:", len(attachment_context))
        print("[chat] image parts generated:", len(image_parts))
        
        # Try RAG retrieval when documents are available for the current thread.
        rag_info = {"enabled": False, "chunks": [], "sources": ""}
        if request.message.strip():
            try:
                rag_info = await rag_service.retrieve_context_for_question(
                    db,
                    user_id=current_user.id,
                    thread_id=thread_id,
                    question=request.message.strip(),
                )
            except Exception as exc:
                print(f"[chat] RAG retrieval failed, using standard chat: {exc}")
                rag_info = {"enabled": False, "chunks": [], "sources": ""}

        if rag_info.get("enabled") and request.message.strip():
            retrieved_chunks = rag_info.get("chunks", [])
            try:
                ai_response = await rag_service.generate_rag_answer(
                    db,
                    user_id=current_user.id,
                    thread_id=thread_id,
                    question=request.message.strip(),
                    retrieved_chunks=retrieved_chunks,
                )
            except Exception as exc:
                print(f"[chat] RAG answer generation failed, using standard chat: {exc}")
                ai_response = await chatbot_service.get_response(
                    request.message,
                    conversation_context=conversation_context,
                    attachment_context=attachment_context,
                    image_parts=image_parts,
                )
        else:
            # Default chat behavior (Projects 1-6) remains unchanged.
            ai_response = await chatbot_service.get_response(
                request.message,
                conversation_context=conversation_context,
                attachment_context=attachment_context,
                image_parts=image_parts,
            )
        
        # Save message to thread
        saved_message = await thread_service.save_message(
            db,
            thread_id,
            request.message.strip() or "[Attachment only message]",
            ai_response,
            commit=False,
        )

        if request.attachment_ids:
            await attachment_service.assign_attachments_to_message(
                db,
                request.attachment_ids,
                current_user.id,
                thread_id,
                saved_message.id,
            )
            print("[chat] attachments linked to message_id:", saved_message.id)

        await db.commit()
        print("[chat] message saved successfully thread_id:", thread_id)
        
        return ChatResponse(response=ai_response, thread_id=thread_id)
    
    except HTTPException:
        # Re-raise HTTP exceptions (like 404)
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_detail("chat_failed", f"Unable to generate chat response: {str(e)}"),
        )
