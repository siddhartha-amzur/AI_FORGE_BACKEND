from __future__ import annotations

import time
from dataclasses import dataclass


@dataclass
class CacheEntry:
    expires_at: float
    value: str


class SchemaCache:
    def __init__(self, ttl_seconds: int = 300):
        self.ttl_seconds = ttl_seconds
        self._items: dict[str, CacheEntry] = {}

    def get(self, key: str) -> str | None:
        entry = self._items.get(key)
        if not entry:
            return None
        if entry.expires_at < time.time():
            self._items.pop(key, None)
            return None
        return entry.value

    def set(self, key: str, value: str) -> None:
        self._items[key] = CacheEntry(expires_at=time.time() + self.ttl_seconds, value=value)


schema_cache = SchemaCache()
