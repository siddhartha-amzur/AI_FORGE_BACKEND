from typing import List

from langchain_openai import OpenAIEmbeddings

from app.core.config import get_settings


def _get_api_key() -> str:
    settings = get_settings()
    return settings.LITELLM_API_KEY or settings.LITELLM_VIRTUAL_KEY


def get_embedding_client() -> OpenAIEmbeddings:
    settings = get_settings()
    return OpenAIEmbeddings(
        model=settings.LITELLM_EMBEDDING_MODEL,
        base_url=settings.LITELLM_PROXY_URL,
        api_key=_get_api_key(),
    )


def embed_texts(texts: List[str]) -> List[List[float]]:
    print("[embedding_service] embedding generation started for chunk count:", len(texts))
    embeddings = get_embedding_client().embed_documents(texts)
    print("[embedding_service] embeddings generated successfully")
    return embeddings


def embed_query(query: str) -> List[float]:
    print("[embedding_service] embedding query started")
    embedding = get_embedding_client().embed_query(query)
    print("[embedding_service] query embedding generated")
    return embedding
