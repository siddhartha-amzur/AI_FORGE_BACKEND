from typing import List, Dict


def build_rag_prompt(
    *,
    retrieved_chunks: List[Dict[str, str | int]],
    conversation_history: str,
    question: str,
) -> str:
    context_lines = []
    for item in retrieved_chunks:
        filename = str(item.get("filename", "Unknown document"))
        page = int(item.get("page", 0) or 0)
        text = str(item.get("text", "")).strip()
        if not text:
            continue
        source_label = f"{filename} (Page {page})" if page > 0 else filename
        context_lines.append(f"[{source_label}]\n{text}")

    retrieved_context = "\n\n".join(context_lines).strip() or "No relevant context found."

    prompt = (
        "You are answering questions based on uploaded documents.\n\n"
        f"Relevant document context:\n{retrieved_context}\n\n"
        f"Conversation history:\n{conversation_history.strip() if conversation_history else 'No previous conversation.'}\n\n"
        f"Current user question:\n{question}\n\n"
        "Rules:\n"
        "- Answer ONLY using provided document context when possible\n"
        "- If answer not found, say exactly: \"I could not find that information in the uploaded document.\"\n"
        "- Keep the answer concise and clear\n"
    )
    print("[rag_chain] RAG prompt generated with context length:", len(retrieved_context))
    return prompt


def format_sources(retrieved_chunks: List[Dict[str, str | int]]) -> str:
    if not retrieved_chunks:
        return ""

    unique_sources = []
    seen = set()
    for item in retrieved_chunks:
        filename = str(item.get("filename", "Unknown document"))
        page = int(item.get("page", 0) or 0)
        source = f"{filename} (Page {page})" if page > 0 else filename
        if source in seen:
            continue
        seen.add(source)
        unique_sources.append(source)

    if not unique_sources:
        return ""

    return "\n".join(f"- {source}" for source in unique_sources)
