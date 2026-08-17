"""
NodeMemorySync — synchronizes short-term memory snapshots between edge nodes.

When a node goes back online after offline mode, it may have accumulated
local STM entries that differ from what other nodes observed.  This module
reconciles differences using a vector-clock-based merge strategy:
  - Each entry carries a (node_id, monotonic_counter) vector clock
  - On merge, the entry with the higher sum of vector clock values wins
  - If clocks are equal, the entry from the authoritative node wins
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any

import redis.asyncio as aioredis

logger = logging.getLogger(__name__)

_SYNC_CHANNEL = "argus:cognition:mem_sync"
_ENTRY_KEY = "argus:cognition:mem:{session_id}:{key}"
_SYNC_TTL_S = 600   # 10 minutes
_BATCH_SIZE = 50


@dataclass
class MemoryEntry:
    key: str
    value: Any
    session_id: str
    node_id: str
    vector_clock: dict[str, int] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def clock_sum(self) -> int:
        return sum(self.vector_clock.values())

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "value": self.value,
            "session_id": self.session_id,
            "node_id": self.node_id,
            "vector_clock": self.vector_clock,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MemoryEntry":
        return cls(
            key=data["key"],
            value=data["value"],
            session_id=data["session_id"],
            node_id=data["node_id"],
            vector_clock=data.get("vector_clock", {}),
            timestamp=data.get("timestamp", time.time()),
        )


class NodeMemorySync:
    """
    Publishes local memory entries and merges incoming entries from other nodes.
    """

    def __init__(
        self,
        redis_client: aioredis.Redis,
        node_id: str,
        authoritative: bool = False,
    ) -> None:
        self._redis = redis_client
        self._node_id = node_id
        self._authoritative = authoritative
        self._clock: dict[str, int] = {node_id: 0}
        self._running = False
        self._task: asyncio.Task | None = None
        self._merged_count = 0
        self._published_count = 0

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        self._running = True
        self._task = asyncio.create_task(self._listen_loop(), name="node_memory_sync")
        logger.info("node_memory_sync started node=%s authoritative=%s", self._node_id, self._authoritative)

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    # ------------------------------------------------------------------
    # Publish
    # ------------------------------------------------------------------

    async def publish(
        self,
        session_id: str,
        key: str,
        value: Any,
    ) -> None:
        self._clock[self._node_id] = self._clock.get(self._node_id, 0) + 1
        entry = MemoryEntry(
            key=key,
            value=value,
            session_id=session_id,
            node_id=self._node_id,
            vector_clock=dict(self._clock),
        )
        await self._store_local(entry)
        try:
            await self._redis.publish(_SYNC_CHANNEL, json.dumps(entry.to_dict()))
            self._published_count += 1
        except Exception as exc:
            logger.debug("node_memory_sync publish_error: %s", exc)

    async def publish_batch(
        self,
        session_id: str,
        entries: dict[str, Any],
    ) -> None:
        for key, value in entries.items():
            await self.publish(session_id, key, value)

    # ------------------------------------------------------------------
    # Subscribe / merge
    # ------------------------------------------------------------------

    async def _listen_loop(self) -> None:
        pubsub = self._redis.pubsub()
        await pubsub.subscribe(_SYNC_CHANNEL)
        try:
            async for message in pubsub.listen():
                if not self._running:
                    break
                if message["type"] != "message":
                    continue
                try:
                    data = json.loads(message["data"])
                    incoming = MemoryEntry.from_dict(data)
                    if incoming.node_id == self._node_id:
                        continue  # skip own messages
                    await self._merge(incoming)
                except Exception as exc:
                    logger.debug("node_memory_sync merge_error: %s", exc)
        except asyncio.CancelledError:
            pass
        finally:
            await pubsub.unsubscribe(_SYNC_CHANNEL)

    async def _merge(self, incoming: MemoryEntry) -> None:
        # Update local clock with max of each component
        for node, ts in incoming.vector_clock.items():
            self._clock[node] = max(self._clock.get(node, 0), ts)

        existing = await self._fetch_local(incoming.session_id, incoming.key)
        if existing is None:
            await self._store_local(incoming)
            self._merged_count += 1
            return

        # Conflict resolution: higher clock sum wins; tie → authoritative node wins
        if incoming.clock_sum() > existing.clock_sum():
            await self._store_local(incoming)
            self._merged_count += 1
        elif incoming.clock_sum() == existing.clock_sum():
            if self._authoritative:
                pass  # keep local
            else:
                await self._store_local(incoming)
                self._merged_count += 1

    # ------------------------------------------------------------------
    # Local storage
    # ------------------------------------------------------------------

    async def _store_local(self, entry: MemoryEntry) -> None:
        key = _ENTRY_KEY.format(session_id=entry.session_id, key=entry.key)
        await self._redis.setex(key, _SYNC_TTL_S, json.dumps(entry.to_dict()))

    async def _fetch_local(self, session_id: str, key: str) -> MemoryEntry | None:
        redis_key = _ENTRY_KEY.format(session_id=session_id, key=key)
        raw = await self._redis.get(redis_key)
        if raw is None:
            return None
        try:
            return MemoryEntry.from_dict(json.loads(raw))
        except Exception:
            return None

    async def get(self, session_id: str, key: str) -> Any | None:
        entry = await self._fetch_local(session_id, key)
        return entry.value if entry else None

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def stats(self) -> dict[str, Any]:
        return {
            "node_id": self._node_id,
            "authoritative": self._authoritative,
            "published_count": self._published_count,
            "merged_count": self._merged_count,
            "vector_clock": dict(self._clock),
            "running": self._running,
        }
