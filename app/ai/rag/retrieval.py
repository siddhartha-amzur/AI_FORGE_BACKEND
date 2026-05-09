from typing import List, Dict
from uuid import UUID

from app.ai.rag.chroma_client import get_user_collection
from app.services.embedding_service import embed_query


def retrieve_chunks(
    *,
    user_id: UUID,
    query: str,
    top_k: int,
    thread_id: UUID | None = None,
) -> List[Dict[str, str | int]]:
    print("[rag_retrieval] retrieval started for user:", user_id)
    collection = get_user_collection(user_id)

    query_embedding = embed_query(query)

    where_filter: dict = {"user_id": str(user_id)}
    if thread_id:
        where_filter = {
            "$and": [
                {"user_id": str(user_id)},
                {"thread_id": str(thread_id)},
            ]
        }

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
        where=where_filter,
    )

    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]

    retrieved: List[Dict[str, str | int]] = []
    for doc, meta, distance in zip(documents, metadatas, distances):
        if not doc or not meta:
            continue
        retrieved.append(
            {
                "text": doc,
                "filename": meta.get("filename", "Unknown document"),
                "page": int(meta.get("page", 0) or 0),
                "distance": float(distance),
                "document_id": meta.get("document_id", ""),
            }
        )

    print("[rag_retrieval] retrieved chunk count:", len(retrieved))
    return retrieved
