from uuid import UUID

import chromadb

from app.core.config import get_chroma_persist_dir


def _collection_name_for_user(user_id: UUID) -> str:
    return f"user_{str(user_id).replace('-', '_')}"


def get_persistent_client() -> chromadb.PersistentClient:
    persist_dir = get_chroma_persist_dir()
    persist_dir.mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(path=str(persist_dir))


def get_user_collection(user_id: UUID):
    client = get_persistent_client()
    collection_name = _collection_name_for_user(user_id)
    return client.get_or_create_collection(name=collection_name)
