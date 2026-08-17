"""
LocalEdgeCache — LRU in-memory cache for edge nodes.

Used when Redis is unavailable (offline mode).  Provides the same key/value
interface as the Redis wrappers so callers can swap without branching.
"""

from __future__ import annotations

import asyncio
import json
import time
from collections import OrderedDict
from typing import Any


class LocalEdgeCache:
    """
    Thread-safe async LRU cache with optional TTL per key.
    maxsize=0 means unlimited (no eviction by count).
    """

    def __init__(self, maxsize: int = 2048) -> None:
        self._maxsize = maxsize
        self._store: OrderedDict[str, tuple[Any, float | None]] = OrderedDict()  # key -> (value, expires_at)
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Core operations
    # ------------------------------------------------------------------

    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        expires_at = time.monotonic() + ttl if ttl else None
        async with self._lock:
            if key in self._store:
                self._store.move_to_end(key)
            self._store[key] = (value, expires_at)
            if self._maxsize > 0 and len(self._store) > self._maxsize:
                self._store.popitem(last=False)

    async def get(self, key: str) -> Any | None:
        async with self._lock:
            if key not in self._store:
                return None
            value, expires_at = self._store[key]
            if expires_at is not None and time.monotonic() > expires_at:
                del self._store[key]
                return None
            self._store.move_to_end(key)
            return value

    async def delete(self, key: str) -> None:
        async with self._lock:
            self._store.pop(key, None)

    async def exists(self, key: str) -> bool:
        return await self.get(key) is not None

    # ------------------------------------------------------------------
    # JSON helpers (mirrors Redis json pattern)
    # ------------------------------------------------------------------

    async def set_json(self, key: str, obj: Any, ttl: int | None = None) -> None:
        await self.set(key, json.dumps(obj), ttl=ttl)

    async def get_json(self, key: str) -> Any | None:
        raw = await self.get(key)
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return raw

    # ------------------------------------------------------------------
    # List helpers
    # ------------------------------------------------------------------

    async def lpush(self, key: str, *values: Any) -> None:
        async with self._lock:
            existing, exp = self._store.get(key, ([], None))
            if not isinstance(existing, list):
                existing = []
            for v in values:
                existing.insert(0, v)
            self._store[key] = (existing, exp)

    async def lrange(self, key: str, start: int, stop: int) -> list[Any]:
        async with self._lock:
            item = self._store.get(key)
            if item is None:
                return []
            lst, expires_at = item
            if expires_at is not None and time.monotonic() > expires_at:
                del self._store[key]
                return []
            if not isinstance(lst, list):
                return []
            if stop == -1:
                return lst[start:]
            return lst[start:stop + 1]

    async def ltrim(self, key: str, start: int, stop: int) -> None:
        async with self._lock:
            item = self._store.get(key)
            if item is None:
                return
            lst, exp = item
            if not isinstance(lst, list):
                return
            if stop == -1:
                self._store[key] = (lst[start:], exp)
            else:
                self._store[key] = (lst[start:stop + 1], exp)

    # ------------------------------------------------------------------
    # Maintenance
    # ------------------------------------------------------------------

    async def purge_expired(self) -> int:
        """Remove all expired entries. Returns number removed."""
        now = time.monotonic()
        async with self._lock:
            expired = [k for k, (_, exp) in self._store.items() if exp is not None and now > exp]
            for k in expired:
                del self._store[k]
        return len(expired)

    async def clear(self) -> None:
        async with self._lock:
            self._store.clear()

    def size(self) -> int:
        return len(self._store)

    def stats(self) -> dict[str, Any]:
        return {
            "size": len(self._store),
            "maxsize": self._maxsize,
        }
