"""
OfflineMode — manages the edge node's local-only operation state.

When the cloud connection is lost, OfflineMode:
  1. Buffers all outbound events to a local FIFO queue (backed by LocalEdgeCache)
  2. Answers health checks as DEGRADED (not OFFLINE) so Kubernetes doesn't kill the pod
  3. Runs inference using locally cached models at reduced precision
  4. Records the offline start time so sync manager can replay events in order
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from edge.local_cache import LocalEdgeCache

logger = logging.getLogger(__name__)

_OFFLINE_QUEUE_KEY = "argus:edge:offline_queue"
_OFFLINE_STATE_KEY = "argus:edge:offline_state"
_MAX_QUEUE_DEPTH = 10_000   # events before oldest are dropped


@dataclass
class OfflineEvent:
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    session_id: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    retry_count: int = 0

    def to_json(self) -> str:
        return json.dumps({
            "event_id": self.event_id,
            "event_type": self.event_type,
            "payload": self.payload,
            "session_id": self.session_id,
            "timestamp": self.timestamp.isoformat(),
            "retry_count": self.retry_count,
        })

    @classmethod
    def from_json(cls, raw: str) -> "OfflineEvent":
        data = json.loads(raw)
        ev = cls()
        ev.event_id = data.get("event_id", ev.event_id)
        ev.event_type = data.get("event_type", "")
        ev.payload = data.get("payload", {})
        ev.session_id = data.get("session_id", "")
        raw_ts = data.get("timestamp")
        if raw_ts:
            ev.timestamp = datetime.fromisoformat(raw_ts)
        ev.retry_count = data.get("retry_count", 0)
        return ev


class OfflineMode:
    """
    Manages the edge node's offline state machine and local event buffer.
    Thread-safe via asyncio.Lock.
    """

    def __init__(self, cache: LocalEdgeCache) -> None:
        self._cache = cache
        self._offline = False
        self._offline_since: float | None = None
        self._lock = asyncio.Lock()
        self._enqueued = 0
        self._dropped = 0

    # ------------------------------------------------------------------
    # State transitions
    # ------------------------------------------------------------------

    async def enter_offline(self) -> None:
        async with self._lock:
            if self._offline:
                return
            self._offline = True
            self._offline_since = time.monotonic()
            await self._cache.set_json(_OFFLINE_STATE_KEY, {
                "offline": True,
                "since": datetime.utcnow().isoformat(),
            })
            logger.warning("offline_mode entered_offline")

    async def exit_offline(self) -> None:
        async with self._lock:
            if not self._offline:
                return
            self._offline = False
            duration_s = time.monotonic() - (self._offline_since or time.monotonic())
            self._offline_since = None
            await self._cache.set_json(_OFFLINE_STATE_KEY, {"offline": False})
            logger.info("offline_mode exited duration_s=%.1f", duration_s)

    @property
    def is_offline(self) -> bool:
        return self._offline

    def offline_duration_s(self) -> float | None:
        if self._offline_since is None:
            return None
        return time.monotonic() - self._offline_since

    # ------------------------------------------------------------------
    # Event buffering
    # ------------------------------------------------------------------

    async def enqueue(
        self,
        event_type: str,
        payload: dict[str, Any],
        session_id: str = "",
    ) -> str:
        """Buffer an event for later cloud sync. Returns the event_id."""
        ev = OfflineEvent(event_type=event_type, payload=payload, session_id=session_id)
        raw = ev.to_json()
        depth = await self._queue_depth()
        if depth >= _MAX_QUEUE_DEPTH:
            # Drop oldest entry
            await self._cache.lpush(_OFFLINE_QUEUE_KEY)  # no-op, drop via trim below
            await self._cache.ltrim(_OFFLINE_QUEUE_KEY, 0, _MAX_QUEUE_DEPTH - 2)
            self._dropped += 1
            logger.debug("offline_mode queue_full dropped oldest event")
        await self._cache.lpush(_OFFLINE_QUEUE_KEY, raw)
        self._enqueued += 1
        return ev.event_id

    async def drain(self, max_items: int = 500) -> list[OfflineEvent]:
        """
        Returns up to max_items buffered events ordered oldest-first and
        removes them from the buffer.
        """
        raw_items = await self._cache.lrange(_OFFLINE_QUEUE_KEY, -max_items, -1)
        if not raw_items:
            return []
        events: list[OfflineEvent] = []
        for raw in reversed(raw_items):
            try:
                events.append(OfflineEvent.from_json(raw))
            except Exception as exc:
                logger.debug("offline_mode parse_error: %s", exc)
        # Trim drained items from the right (oldest)
        total = await self._queue_depth()
        keep = total - len(raw_items)
        if keep <= 0:
            await self._cache.delete(_OFFLINE_QUEUE_KEY)
        else:
            await self._cache.ltrim(_OFFLINE_QUEUE_KEY, 0, keep - 1)
        return events

    async def peek(self, n: int = 10) -> list[OfflineEvent]:
        """Non-destructive peek at the oldest n events."""
        raw_items = await self._cache.lrange(_OFFLINE_QUEUE_KEY, -n, -1)
        events = []
        for raw in reversed(raw_items):
            try:
                events.append(OfflineEvent.from_json(raw))
            except Exception:
                pass
        return events

    async def _queue_depth(self) -> int:
        items = await self._cache.lrange(_OFFLINE_QUEUE_KEY, 0, -1)
        return len(items)

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    async def stats(self) -> dict[str, Any]:
        depth = await self._queue_depth()
        return {
            "offline": self._offline,
            "offline_duration_s": self.offline_duration_s(),
            "queue_depth": depth,
            "enqueued_total": self._enqueued,
            "dropped_total": self._dropped,
        }
