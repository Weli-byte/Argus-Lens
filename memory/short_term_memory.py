"""
Short-term memory backed by Redis with TTL-based auto-eviction.
Stores the last 15 minutes of session events.
Key format: argus:stm:{session_id}:{memory_id}
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timedelta
from typing import Any

import redis.asyncio as aioredis

from intelligence.types import MemoryEntry, MemoryType

logger = logging.getLogger(__name__)

_STM_TTL_SECONDS = 900  # 15 minutes
_STM_KEY_PREFIX = "argus:stm"
_STM_INDEX_PREFIX = "argus:stm:idx"


class ShortTermMemory:
    """
    Working memory for recent events — last 15 minutes per session.
    All operations are O(1) or O(n) where n is retrieved entries only.
    """

    def __init__(self, redis_client: aioredis.Redis) -> None:
        self._redis = redis_client

    # ------------------------------------------------------------------
    # Internal key helpers
    # ------------------------------------------------------------------

    def _entry_key(self, session_id: str, memory_id: str) -> str:
        return f"{_STM_KEY_PREFIX}:{session_id}:{memory_id}"

    def _session_index_key(self, session_id: str) -> str:
        return f"{_STM_INDEX_PREFIX}:session:{session_id}"

    def _tag_index_key(self, session_id: str, tag: str) -> str:
        return f"{_STM_INDEX_PREFIX}:tag:{session_id}:{tag}"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def store(self, session_id: str, entry: MemoryEntry) -> None:
        """Persist a MemoryEntry; overrides TTL on update."""
        key = self._entry_key(session_id, entry.memory_id)
        payload = json.dumps(entry.to_dict())

        pipe = self._redis.pipeline()
        pipe.setex(key, _STM_TTL_SECONDS, payload)

        # Sorted set index by timestamp (score = unix timestamp)
        score = entry.created_at.timestamp()
        idx_key = self._session_index_key(session_id)
        pipe.zadd(idx_key, {entry.memory_id: score})
        pipe.expire(idx_key, _STM_TTL_SECONDS)

        # Tag indices
        for tag in entry.tags:
            tag_key = self._tag_index_key(session_id, tag)
            pipe.zadd(tag_key, {entry.memory_id: score})
            pipe.expire(tag_key, _STM_TTL_SECONDS)

        await pipe.execute()
        logger.debug(
            "stm.store session=%s memory_id=%s type=%s",
            session_id,
            entry.memory_id,
            entry.memory_type.value,
        )

    async def retrieve_recent(
        self,
        session_id: str,
        limit: int = 20,
        memory_type: MemoryType | None = None,
    ) -> list[MemoryEntry]:
        """Return up to `limit` most-recent entries for a session."""
        idx_key = self._session_index_key(session_id)
        # ZREVRANGE returns highest-score (most recent) first
        raw_ids: list[bytes] = await self._redis.zrevrange(idx_key, 0, limit - 1)
        if not raw_ids:
            return []

        entries = await self._fetch_entries(session_id, [m.decode() for m in raw_ids])
        if memory_type is not None:
            entries = [e for e in entries if e.memory_type == memory_type]
        return entries

    async def retrieve_by_tags(
        self,
        session_id: str,
        tags: list[str],
        limit: int = 20,
    ) -> list[MemoryEntry]:
        """Return entries that have ALL specified tags (intersection)."""
        if not tags:
            return []

        tag_keys = [self._tag_index_key(session_id, t) for t in tags]
        dest_key = f"argus:stm:tmp:{session_id}:{int(time.time())}"

        # ZINTERSTORE computes the intersection
        await self._redis.zinterstore(dest_key, tag_keys)
        await self._redis.expire(dest_key, 10)  # temporary — clean up fast

        raw_ids: list[bytes] = await self._redis.zrevrange(dest_key, 0, limit - 1)
        await self._redis.delete(dest_key)

        if not raw_ids:
            return []
        return await self._fetch_entries(session_id, [m.decode() for m in raw_ids])

    async def get_session_summary(self, session_id: str) -> dict[str, Any]:
        """Aggregate stats for a session — count by type, age, importance."""
        idx_key = self._session_index_key(session_id)
        raw_ids: list[bytes] = await self._redis.zrange(idx_key, 0, -1)
        if not raw_ids:
            return {
                "session_id": session_id,
                "total_entries": 0,
                "by_type": {},
                "oldest_ts": None,
                "newest_ts": None,
                "avg_importance": 0.0,
            }

        entries = await self._fetch_entries(session_id, [m.decode() for m in raw_ids])
        by_type: dict[str, int] = {}
        importance_sum = 0.0
        timestamps: list[float] = []

        for e in entries:
            key = e.memory_type.value
            by_type[key] = by_type.get(key, 0) + 1
            importance_sum += e.importance_score
            timestamps.append(e.created_at.timestamp())

        return {
            "session_id": session_id,
            "total_entries": len(entries),
            "by_type": by_type,
            "oldest_ts": datetime.utcfromtimestamp(min(timestamps)).isoformat() if timestamps else None,
            "newest_ts": datetime.utcfromtimestamp(max(timestamps)).isoformat() if timestamps else None,
            "avg_importance": importance_sum / len(entries) if entries else 0.0,
        }

    async def clear_session(self, session_id: str) -> int:
        """Delete all STM entries for a session. Returns count deleted."""
        idx_key = self._session_index_key(session_id)
        raw_ids: list[bytes] = await self._redis.zrange(idx_key, 0, -1)
        if not raw_ids:
            return 0

        pipe = self._redis.pipeline()
        for mid in raw_ids:
            pipe.delete(self._entry_key(session_id, mid.decode()))
        pipe.delete(idx_key)
        await pipe.execute()

        logger.info("stm.clear session=%s deleted=%d", session_id, len(raw_ids))
        return len(raw_ids)

    async def update_importance(
        self, session_id: str, memory_id: str, new_score: float
    ) -> bool:
        """Update the importance score of an existing entry in-place."""
        key = self._entry_key(session_id, memory_id)
        raw = await self._redis.get(key)
        if not raw:
            return False

        data: dict[str, Any] = json.loads(raw)
        data["importance_score"] = max(0.0, min(1.0, new_score))
        ttl = await self._redis.ttl(key)
        await self._redis.setex(key, max(ttl, 1), json.dumps(data))
        logger.debug(
            "stm.update_importance session=%s memory_id=%s score=%.3f",
            session_id,
            memory_id,
            new_score,
        )
        return True

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _fetch_entries(
        self, session_id: str, memory_ids: list[str]
    ) -> list[MemoryEntry]:
        if not memory_ids:
            return []

        pipe = self._redis.pipeline()
        for mid in memory_ids:
            pipe.get(self._entry_key(session_id, mid))
        results = await pipe.execute()

        entries: list[MemoryEntry] = []
        for raw in results:
            if raw is None:
                continue
            try:
                data: dict[str, Any] = json.loads(raw)
                entry = MemoryEntry(
                    memory_id=data["memory_id"],
                    memory_type=MemoryType(data["memory_type"]),
                    content=data["content"],
                    importance_score=data.get("importance_score", 0.5),
                    access_count=data.get("access_count", 0),
                    created_at=datetime.fromisoformat(data["created_at"]),
                    last_accessed=datetime.fromisoformat(data["last_accessed"]),
                    tags=data.get("tags", []),
                    source=data.get("source", ""),
                    metadata=data.get("metadata", {}),
                )
                entries.append(entry)
            except (KeyError, ValueError) as exc:
                logger.warning("stm.fetch_entries decode error: %s", exc)
        return entries
