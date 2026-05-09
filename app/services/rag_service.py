from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.services import memory_service, document_service
from app.services.chatbot import chatbot_service


def _load_rag_modules() -> Optional[tuple]:
    """Load optional RAG modules lazily.

    RAG depends on chromadb and related packages that may be optional in some
    environments. Importing lazily keeps core chat/upload flows available even
    when those packages are missing.
    """
    try:
        from app.ai.rag.rag_chain import build_rag_prompt, format_sources
        from app.ai.rag.retrieval import retrieve_chunks
        return build_rag_prompt, format_sources, retrieve_chunks
    except ModuleNotFoundError as exc:
        print(f"[rag_service] RAG disabled, missing dependency: {exc}")
        return None


async def retrieve_context_for_question(
    db: AsyncSession,
    *,
    user_id: UUID,
    thread_id: UUID,
    question: str,
) -> Dict[str, object]:
    settings = get_settings()
    print("[rag_service] retrieval started for thread:", thread_id)

    rag_modules = _load_rag_modules()
    if not rag_modules:
        return {"enabled": False, "chunks": [], "sources": ""}
    _, format_sources, retrieve_chunks = rag_modules

    has_documents = await document_service.has_completed_documents(db, user_id, thread_id)
    if not has_documents:
        print("[rag_service] no completed documents found for thread")
        return {"enabled": False, "chunks": [], "sources": ""}

    chunks = retrieve_chunks(
        user_id=user_id,
        query=question,
        top_k=settings.RAG_TOP_K,
        thread_id=thread_id,
    )
    sources = format_sources(chunks)
    return {
        "enabled": True,
        "chunks": chunks,
        "sources": sources,
    }


async def generate_rag_answer(
    db: AsyncSession,
    *,
    user_id: UUID,
    thread_id: UUID,
    question: str,
    retrieved_chunks: List[Dict[str, object]],
) -> str:
    rag_modules = _load_rag_modules()
    if not rag_modules:
        return "RAG is temporarily unavailable. Falling back to standard chat response."
    build_rag_prompt, format_sources, _ = rag_modules

    conversations = await memory_service.get_recent_conversations(db, thread_id, user_id, limit=5)
    conversation_context = memory_service.build_conversation_history(conversations or [])

    if not retrieved_chunks:
        return "I could not find relevant information in the uploaded documents."

    rag_prompt = build_rag_prompt(
        retrieved_chunks=retrieved_chunks,
        conversation_history=conversation_context,
        question=question,
    )

    answer = await chatbot_service.get_rag_response(rag_prompt)
    sources = format_sources(retrieved_chunks)

    if sources:
        answer = f"Answer generated from uploaded documents.\n\n{answer}\n\nSource:\n{sources}"
    else:
        answer = f"Answer generated from uploaded documents.\n\n{answer}"

    return answer
