from typing import List, Dict
from uuid import UUID

from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.ai.rag.chroma_client import get_user_collection
from app.services.embedding_service import embed_texts


def split_pages_into_chunks(pages: List[Dict[str, str | int]], chunk_size: int = 1000, chunk_overlap: int = 200) -> List[Dict[str, str | int]]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )

    all_chunks: List[Dict[str, str | int]] = []
    for page_item in pages:
        page_number = int(page_item["page"])
        text = str(page_item["text"])
        splits = splitter.split_text(text)
        for index, chunk in enumerate(splits):
            cleaned = chunk.strip()
            if not cleaned:
                continue
            all_chunks.append({
                "page": page_number,
                "chunk_index": index,
                "text": cleaned,
            })

    print("[rag_ingestion] chunk count:", len(all_chunks))
    return all_chunks


def ingest_document_chunks(
    *,
    user_id: UUID,
    document_id: UUID,
    thread_id: UUID | None,
    filename: str,
    chunks: List[Dict[str, str | int]],
) -> int:
    if not chunks:
        return 0

    collection = get_user_collection(user_id)

    texts = [str(item["text"]) for item in chunks]
    embeddings = embed_texts(texts)

    ids = [f"{document_id}_{idx}" for idx in range(len(chunks))]
    metadatas = []
    for item in chunks:
        metadatas.append(
            {
                "user_id": str(user_id),
                "document_id": str(document_id),
                "thread_id": str(thread_id) if thread_id else "",
                "filename": filename,
                "page": int(item["page"]),
                "chunk_index": int(item["chunk_index"]),
            }
        )

    collection.add(
        ids=ids,
        documents=texts,
        embeddings=embeddings,
        metadatas=metadatas,
    )
    print("[rag_ingestion] embeddings stored successfully for document:", document_id)
    return len(chunks)
