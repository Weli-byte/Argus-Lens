"""
SharedContext — distributed shared memory across ArgusLens nodes.

Uses Redis as the backing store.  Each node can read and write to a
shared context namespace identified by session_id.  Writes are versioned
to detect concurrent modifications and support conflict resolution.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

import redis.asyncio as aioredis

logger = logging.getLogger(__name__)

_CONTEXT_KEY = "argus:cognition:ctx:{session_id}"
_VERSION_KEY = "argus:cognition:ver:{session_id}"
_CTX_TTL_S = 300        # 5 minutes
_LOCK_TTL_S = 10        # optimistic write lock


@dataclass
class ContextEntry:
    key: str
    value: Any
    written_by: str
    version: int
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "value": self.value,
            "written_by": self.written_by,
            "version": self.version,
            "timestamp": self.timestamp,
        }


class SharedContext:
    """
    Provides distributed key-value context visible to all nodes in a session.
    Conflict resolution: last-write-wins with version tracking.
    """

    def __init__(self, redis_client: aioredis.Redis, node_id: str) -> None:
        self._redis = redis_client
        self._node_id = node_id

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    async def set(
        self,
        session_id: str,
        key: str,
        value: Any,
        *,
        ttl: int = _CTX_TTL_S,
    ) -> int:
        """Write a context entry. Returns the new version number."""
        ctx_key = _CONTEXT_KEY.format(session_id=session_id)
        ver_key = _VERSION_KEY.format(session_id=session_id)

        # Atomic version increment
        version = await self._redis.incr(ver_key)
        await self._redis.expire(ver_key, ttl)

        entry = ContextEntry(
            key=key,
            value=value,
            written_by=self._node_id,
            version=version,
        )

        # Merge into context hash
        await self._redis.hset(ctx_key, key, json.dumps(entry.to_dict()))
        await self._redis.expire(ctx_key, ttl)
        return version

    async def set_many(
        self,
        session_id: str,
        entries: dict[str, Any],
        ttl: int = _CTX_TTL_S,
    ) -> int:
        """Write multiple keys atomically (single version increment)."""
        if not entries:
            return 0
        ctx_key = _CONTEXT_KEY.format(session_id=session_id)
        ver_key = _VERSION_KEY.format(session_id=session_id)
        version = await self._redis.incr(ver_key)
        await self._redis.expire(ver_key, ttl)

        mapping: dict[str, str] = {}
        for k, v in entries.items():
            entry = ContextEntry(key=k, value=v, written_by=self._node_id, version=version)
            mapping[k] = json.dumps(entry.to_dict())

        await self._redis.hset(ctx_key, mapping=mapping)
        await self._redis.expire(ctx_key, ttl)
        return version

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    async def get(self, session_id: str, key: str) -> Any | None:
        ctx_key = _CONTEXT_KEY.format(session_id=session_id)
        raw = await self._redis.hget(ctx_key, key)
        if raw is None:
            return None
        try:
            entry = json.loads(raw)
            return entry.get("value")
        except json.JSONDecodeError:
            return None

    async def get_all(self, session_id: str) -> dict[str, Any]:
        ctx_key = _CONTEXT_KEY.format(session_id=session_id)
        raw_map = await self._redis.hgetall(ctx_key)
        result: dict[str, Any] = {}
        for k, raw in raw_map.items():
            try:
                entry = json.loads(raw)
                result[k] = entry.get("value")
            except json.JSONDecodeError:
                pass
        return result

    async def get_entry(self, session_id: str, key: str) -> ContextEntry | None:
        ctx_key = _CONTEXT_KEY.format(session_id=session_id)
        raw = await self._redis.hget(ctx_key, key)
        if raw is None:
            return None
        try:
            data = json.loads(raw)
            return ContextEntry(**data)
        except (json.JSONDecodeError, TypeError, KeyError):
            return None

    async def version(self, session_id: str) -> int:
        ver_key = _VERSION_KEY.format(session_id=session_id)
        raw = await self._redis.get(ver_key)
        return int(raw) if raw else 0

    # ------------------------------------------------------------------
    # Deletion
    # ------------------------------------------------------------------

    async def delete(self, session_id: str, key: str) -> None:
        ctx_key = _CONTEXT_KEY.format(session_id=session_id)
        await self._redis.hdel(ctx_key, key)

    async def clear(self, session_id: str) -> None:
        ctx_key = _CONTEXT_KEY.format(session_id=session_id)
        ver_key = _VERSION_KEY.format(session_id=session_id)
        await self._redis.delete(ctx_key, ver_key)
