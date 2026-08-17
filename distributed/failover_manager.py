"""
Distributed Failover Manager — heartbeat tracking, dead-worker detection,
task requeuing, and backup-worker election via Redis.
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Optional

import redis.asyncio as aioredis
from loguru import logger
from prometheus_client import Counter, Gauge

# ---------------------------------------------------------------------------
# Prometheus
# ---------------------------------------------------------------------------

_HEALTHY_WORKERS = Gauge(
    "arguslens_worker_count_healthy",
    "Number of workers currently in HEALTHY state",
)
_FAILOVER_TOTAL = Counter(
    "arguslens_worker_failover_total",
    "Total number of worker failover events",
    ["reason"],
)

# ---------------------------------------------------------------------------
# Redis key schema
# ---------------------------------------------------------------------------

_HB_KEY = "argus:worker:{id}:heartbeat"
_TASKS_KEY = "argus:worker:{id}:tasks"
_CAPS_KEY = "argus:worker:{id}:capabilities"
_CLUSTER_KEY = "argus:cluster:workers"


# ---------------------------------------------------------------------------
# Domain types
# ---------------------------------------------------------------------------


class WorkerState(str, Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    DEAD = "DEAD"
    RECOVERING = "RECOVERING"


@dataclass
class WorkerHeartbeat:
    worker_id: str
    last_seen: float           # Unix timestamp
    current_load: float        # 0.0 … 1.0
    state: WorkerState
    capabilities: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Manager
# ---------------------------------------------------------------------------


class FailoverManager:
    """
    Distributed worker lifecycle manager backed by Redis.

    Each worker calls ``send_heartbeat`` every *heartbeat_interval* seconds.
    A background task runs ``check_worker_health`` on the same cadence and
    marks / handles any worker that hasn't been seen within *dead_threshold*.

    All worker metadata is stored with a TTL equal to *dead_threshold* × 2, so
    crashed workers are automatically removed from Redis without manual cleanup.
    """

    def __init__(
        self,
        redis_client: aioredis.Redis,
        heartbeat_interval: float = 10.0,
        dead_threshold: float = 30.0,
    ) -> None:
        self._redis = redis_client
        self.heartbeat_interval = heartbeat_interval
        self.dead_threshold = dead_threshold
        self._check_task: asyncio.Task[None] | None = None
        self._running = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        self._running = True
        self._check_task = asyncio.create_task(
            self._health_check_loop(), name="failover_health_check"
        )
        logger.info("FailoverManager started (interval={}s dead={}s)", self.heartbeat_interval, self.dead_threshold)

    async def stop(self) -> None:
        self._running = False
        if self._check_task and not self._check_task.done():
            self._check_task.cancel()

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    async def register_worker(self, worker_id: str, capabilities: list[str]) -> None:
        """Register a new worker and store its capabilities in Redis."""
        caps_key = _CAPS_KEY.format(id=worker_id)
        cluster_key = _CLUSTER_KEY
        ttl = int(self.dead_threshold * 2)

        pipe = self._redis.pipeline()
        pipe.setex(caps_key, ttl, json.dumps(capabilities))
        pipe.sadd(cluster_key, worker_id)
        await pipe.execute()
        logger.info("Worker registered id={} caps={}", worker_id, capabilities)

    # ------------------------------------------------------------------
    # Heartbeat
    # ------------------------------------------------------------------

    async def send_heartbeat(self, worker_id: str, load_metrics: dict[str, Any]) -> None:
        """
        Called by each worker periodically.  Writes a heartbeat record with
        current load and sets a TTL so Redis auto-expires dead entries.
        """
        hb_key = _HB_KEY.format(id=worker_id)
        payload = {
            "worker_id": worker_id,
            "last_seen": time.time(),
            "current_load": float(load_metrics.get("cpu_percent", 0)) / 100.0,
            "state": WorkerState.HEALTHY,
            **load_metrics,
        }
        ttl = int(self.dead_threshold * 2)
        await self._redis.setex(hb_key, ttl, json.dumps(payload, default=str))

    # ------------------------------------------------------------------
    # Health check loop
    # ------------------------------------------------------------------

    async def _health_check_loop(self) -> None:
        while self._running:
            try:
                await asyncio.sleep(self.heartbeat_interval)
                await self.check_worker_health()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("FailoverManager health check error: {}", exc)

    async def check_worker_health(self) -> None:
        """
        Enumerate all registered workers.  Any worker whose heartbeat TTL has
        expired (Redis key missing) is treated as DEAD.
        """
        worker_ids: set[str] = await self._redis.smembers(_CLUSTER_KEY)  # type: ignore[assignment]
        now = time.time()
        healthy_count = 0

        for wid in worker_ids:
            hb_raw = await self._redis.get(_HB_KEY.format(id=wid))
            if hb_raw is None:
                # Heartbeat key expired → worker is dead
                logger.warning("Worker {} heartbeat expired — marking DEAD", wid)
                await self.handle_dead_worker(wid)
            else:
                hb = json.loads(hb_raw)
                age = now - hb.get("last_seen", 0)
                if age > self.dead_threshold:
                    logger.warning("Worker {} stale heartbeat age={}s — marking DEAD", wid, age)
                    await self.handle_dead_worker(wid)
                else:
                    healthy_count += 1

        _HEALTHY_WORKERS.set(healthy_count)

    # ------------------------------------------------------------------
    # Dead worker handling
    # ------------------------------------------------------------------

    async def handle_dead_worker(self, worker_id: str) -> None:
        """
        Full dead-worker response:
        1. Requeue its pending tasks
        2. Notify living workers (Redis pub/sub)
        3. Update cluster set
        4. Trigger local cleanup
        """
        logger.error("Handling dead worker id={}", worker_id)
        _FAILOVER_TOTAL.labels(reason="dead_worker").inc()

        await self._requeue_worker_tasks(worker_id)
        await self._notify_cluster(worker_id)
        await self.cleanup_dead_worker(worker_id)

    async def _requeue_worker_tasks(self, worker_id: str) -> None:
        """Move tasks from the dead worker's list back to a shared pending queue."""
        tasks_key = _TASKS_KEY.format(id=worker_id)
        pending_key = "argus:tasks:pending"

        while True:
            task_raw = await self._redis.lpop(tasks_key)
            if task_raw is None:
                break
            try:
                task = json.loads(task_raw)
                task["requeued_from"] = worker_id
                task["requeue_ts"] = time.time()
                await self._redis.rpush(pending_key, json.dumps(task))
                logger.info("Requeued task={} from dead worker={}", task.get("task_id"), worker_id)
                _FAILOVER_TOTAL.labels(reason="task_requeue").inc()
            except json.JSONDecodeError:
                logger.error("Could not decode task payload from worker={}", worker_id)

    async def _notify_cluster(self, dead_worker_id: str) -> None:
        """Publish a failover event so surviving workers can react."""
        channel = "argus:events:worker_failover"
        message = json.dumps(
            {"event": "worker_dead", "worker_id": dead_worker_id, "ts": time.time()}
        )
        await self._redis.publish(channel, message)

    async def cleanup_dead_worker(self, worker_id: str) -> None:
        """Remove all Redis state for the dead worker."""
        pipe = self._redis.pipeline()
        pipe.delete(_HB_KEY.format(id=worker_id))
        pipe.delete(_TASKS_KEY.format(id=worker_id))
        pipe.delete(_CAPS_KEY.format(id=worker_id))
        pipe.srem(_CLUSTER_KEY, worker_id)
        await pipe.execute()
        logger.info("Cleaned up Redis state for dead worker={}", worker_id)

    # ------------------------------------------------------------------
    # Backup worker election
    # ------------------------------------------------------------------

    async def elect_backup_worker(self, task_type: str) -> Optional[str]:
        """
        Elect the least-loaded HEALTHY worker that supports *task_type*.
        Returns worker_id or None if no suitable worker is available.
        """
        worker_ids: set[str] = await self._redis.smembers(_CLUSTER_KEY)  # type: ignore[assignment]
        candidates: list[tuple[float, str]] = []

        for wid in worker_ids:
            # Check capabilities
            caps_raw = await self._redis.get(_CAPS_KEY.format(id=wid))
            if caps_raw is None:
                continue
            caps = json.loads(caps_raw)
            if task_type not in caps and "*" not in caps:
                continue

            # Check heartbeat
            hb_raw = await self._redis.get(_HB_KEY.format(id=wid))
            if hb_raw is None:
                continue
            hb = json.loads(hb_raw)
            load = float(hb.get("current_load", 1.0))
            candidates.append((load, wid))

        if not candidates:
            logger.warning("No backup worker available for task_type={}", task_type)
            return None

        candidates.sort()  # ascending load
        elected = candidates[0][1]
        logger.info("Elected backup worker={} for task_type={}", elected, task_type)
        return elected

    # ------------------------------------------------------------------
    # Cluster health snapshot
    # ------------------------------------------------------------------

    async def get_cluster_health(self) -> dict[str, Any]:
        """Return a full cluster health snapshot."""
        worker_ids: set[str] = await self._redis.smembers(_CLUSTER_KEY)  # type: ignore[assignment]
        workers: dict[str, dict] = {}
        now = time.time()

        for wid in worker_ids:
            hb_raw = await self._redis.get(_HB_KEY.format(id=wid))
            if hb_raw:
                hb = json.loads(hb_raw)
                age = now - hb.get("last_seen", 0)
                state = WorkerState.HEALTHY if age <= self.dead_threshold else WorkerState.DEAD
            else:
                hb = {}
                state = WorkerState.DEAD

            workers[wid] = {
                "state": state,
                "last_seen_age_s": round(now - hb.get("last_seen", now), 1),
                "current_load": hb.get("current_load", None),
            }

        healthy = sum(1 for w in workers.values() if w["state"] == WorkerState.HEALTHY)
        return {
            "total_workers": len(workers),
            "healthy_workers": healthy,
            "dead_workers": len(workers) - healthy,
            "workers": workers,
        }
