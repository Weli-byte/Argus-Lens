"""
EdgeSyncManager — uploads buffered offline events to the cloud and downloads
updated model weights / config.

Priority queue ordering (highest first):
  1. CRITICAL / EMERGENCY health events
  2. Federated learning gradient updates
  3. Vision / temporal inference results
  4. Metrics and telemetry

Cloud communication uses aiohttp.  On transient failure (5xx / timeout),
events are re-queued with exponential back-off up to _MAX_RETRIES.
"""

from __future__ import annotations

import asyncio
import heapq
import logging
import time
from dataclasses import dataclass, field
from typing import Any

from edge.offline_mode import OfflineEvent, OfflineMode

logger = logging.getLogger(__name__)

_MAX_RETRIES = 5
_BASE_BACKOFF_S = 2.0
_MAX_BACKOFF_S = 120.0
_SYNC_BATCH_SIZE = 100
_SYNC_INTERVAL_S = 30.0

_PRIORITY_MAP: dict[str, int] = {
    "health_critical": 0,
    "health_emergency": 0,
    "federated_update": 1,
    "vision_result": 2,
    "temporal_result": 2,
    "inference_result": 2,
    "metric": 3,
    "telemetry": 3,
}
_DEFAULT_PRIORITY = 2


@dataclass(order=True)
class _PriorityItem:
    priority: int
    sequence: int
    event: OfflineEvent = field(compare=False)


class EdgeSyncManager:
    """
    Manages cloud sync for a single edge node.

    Usage:
        mgr = EdgeSyncManager(cloud_url, offline_mode)
        await mgr.start()
        ...
        await mgr.stop()
    """

    def __init__(
        self,
        cloud_url: str,
        offline_mode: OfflineMode,
        node_id: str = "",
        auth_token: str = "",
        sync_interval_s: float = _SYNC_INTERVAL_S,
    ) -> None:
        self._cloud_url = cloud_url.rstrip("/")
        self._offline_mode = offline_mode
        self._node_id = node_id
        self._auth_token = auth_token
        self._sync_interval_s = sync_interval_s

        # Min-heap priority queue: (priority, sequence, OfflineEvent)
        self._heap: list[_PriorityItem] = []
        self._sequence = 0
        self._lock = asyncio.Lock()
        self._task: asyncio.Task | None = None
        self._running = False
        self._synced_count = 0
        self._failed_count = 0

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        self._running = True
        self._task = asyncio.create_task(self._sync_loop(), name="edge_sync")
        logger.info("edge_sync started node=%s cloud=%s", self._node_id, self._cloud_url)

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("edge_sync stopped synced=%d failed=%d", self._synced_count, self._failed_count)

    # ------------------------------------------------------------------
    # Event submission
    # ------------------------------------------------------------------

    async def submit(self, event: OfflineEvent) -> None:
        priority = _PRIORITY_MAP.get(event.event_type, _DEFAULT_PRIORITY)
        async with self._lock:
            self._sequence += 1
            heapq.heappush(self._heap, _PriorityItem(priority, self._sequence, event))

    # ------------------------------------------------------------------
    # Sync loop
    # ------------------------------------------------------------------

    async def _sync_loop(self) -> None:
        while self._running:
            try:
                await asyncio.sleep(self._sync_interval_s)
                if self._offline_mode.is_offline:
                    continue
                await self._drain_offline_buffer()
                await self._flush_priority_queue()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("edge_sync loop_error: %s", exc)

    async def _drain_offline_buffer(self) -> None:
        """Move events from OfflineMode buffer into the priority queue."""
        events = await self._offline_mode.drain(max_items=_SYNC_BATCH_SIZE)
        if not events:
            return
        async with self._lock:
            for ev in events:
                priority = _PRIORITY_MAP.get(ev.event_type, _DEFAULT_PRIORITY)
                self._sequence += 1
                heapq.heappush(self._heap, _PriorityItem(priority, self._sequence, ev))
        logger.debug("edge_sync drained offline_buffer count=%d", len(events))

    async def _flush_priority_queue(self) -> None:
        """Send queued events to cloud in priority order."""
        batch: list[OfflineEvent] = []
        async with self._lock:
            while self._heap and len(batch) < _SYNC_BATCH_SIZE:
                item = heapq.heappop(self._heap)
                batch.append(item.event)

        if not batch:
            return

        for ev in batch:
            success = await self._upload_event(ev)
            if success:
                self._synced_count += 1
            else:
                ev.retry_count += 1
                if ev.retry_count < _MAX_RETRIES:
                    # Re-queue with lower priority (allow others through)
                    priority = _PRIORITY_MAP.get(ev.event_type, _DEFAULT_PRIORITY) + ev.retry_count
                    async with self._lock:
                        self._sequence += 1
                        heapq.heappush(self._heap, _PriorityItem(priority, self._sequence, ev))
                else:
                    self._failed_count += 1
                    logger.warning(
                        "edge_sync event_dropped event_id=%s retries=%d",
                        ev.event_id, ev.retry_count,
                    )

    async def _upload_event(self, ev: OfflineEvent) -> bool:
        """POST a single event to the cloud. Returns True on success."""
        try:
            import aiohttp
        except ImportError:
            logger.warning("edge_sync aiohttp_not_installed — cannot upload")
            return False

        url = f"{self._cloud_url}/api/v1/edge/ingest"
        headers = {"Content-Type": "application/json"}
        if self._auth_token:
            headers["Authorization"] = f"Bearer {self._auth_token}"

        backoff = _BASE_BACKOFF_S
        for attempt in range(_MAX_RETRIES):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        url,
                        json={
                            "node_id": self._node_id,
                            "event_id": ev.event_id,
                            "event_type": ev.event_type,
                            "payload": ev.payload,
                            "session_id": ev.session_id,
                            "timestamp": ev.timestamp.isoformat(),
                        },
                        timeout=aiohttp.ClientTimeout(total=10),
                        headers=headers,
                    ) as resp:
                        if resp.status in (200, 201, 202):
                            return True
                        if resp.status < 500:
                            # 4xx — non-retryable
                            logger.warning(
                                "edge_sync upload_4xx event_id=%s status=%d",
                                ev.event_id, resp.status,
                            )
                            return False
                        # 5xx → retry
            except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
                logger.debug("edge_sync upload_error attempt=%d: %s", attempt + 1, exc)

            await asyncio.sleep(min(backoff, _MAX_BACKOFF_S))
            backoff *= 2

        return False

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def stats(self) -> dict[str, Any]:
        return {
            "cloud_url": self._cloud_url,
            "queue_depth": len(self._heap),
            "synced_count": self._synced_count,
            "failed_count": self._failed_count,
            "running": self._running,
        }
