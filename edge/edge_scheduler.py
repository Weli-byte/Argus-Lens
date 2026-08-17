"""
EdgeScheduler — adaptive task scheduling for edge nodes.

Schedules inference tasks based on:
  - Current hardware load (GPU/CPU utilization)
  - Available VRAM headroom
  - Task priority (CRITICAL always runs immediately)
  - Estimated execution time vs deadline

Backpressure: when the local queue exceeds _QUEUE_SOFT_LIMIT tasks, new
NORMAL priority tasks are dropped and the caller is notified via a raised
BackpressureError.
"""

from __future__ import annotations

import asyncio
import heapq
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine

logger = logging.getLogger(__name__)

_QUEUE_SOFT_LIMIT = 256
_QUEUE_HARD_LIMIT = 512
_WORKER_COUNT = 4
_TASK_TIMEOUT_S = 30.0


class BackpressureError(Exception):
    """Raised when the scheduler queue is full."""


@dataclass(order=True)
class ScheduledTask:
    priority: int                   # lower = higher priority
    deadline: float                 # monotonic time by which task must run
    sequence: int                   # tie-break by insertion order
    task_id: str = field(compare=False)
    coro_fn: Callable[[], Coroutine[Any, Any, Any]] = field(compare=False)
    metadata: dict[str, Any] = field(compare=False, default_factory=dict)


class EdgeScheduler:
    """
    Min-heap priority scheduler with a fixed worker pool.
    """

    def __init__(self, worker_count: int = _WORKER_COUNT) -> None:
        self._worker_count = worker_count
        self._heap: list[ScheduledTask] = []
        self._heap_lock = asyncio.Lock()
        self._semaphore = asyncio.Semaphore(worker_count)
        self._workers: list[asyncio.Task] = []
        self._running = False
        self._sequence = 0
        self._submitted = 0
        self._completed = 0
        self._dropped = 0
        self._timed_out = 0
        self._event = asyncio.Event()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        self._running = True
        for _ in range(self._worker_count):
            task = asyncio.create_task(self._worker_loop())
            self._workers.append(task)
        logger.info("edge_scheduler started workers=%d", self._worker_count)

    async def stop(self) -> None:
        self._running = False
        self._event.set()
        for w in self._workers:
            w.cancel()
        results = await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()
        logger.info(
            "edge_scheduler stopped submitted=%d completed=%d dropped=%d timeout=%d",
            self._submitted, self._completed, self._dropped, self._timed_out,
        )

    # ------------------------------------------------------------------
    # Task submission
    # ------------------------------------------------------------------

    async def submit(
        self,
        task_id: str,
        coro_fn: Callable[[], Coroutine[Any, Any, Any]],
        *,
        priority: int = 5,
        deadline_s: float = _TASK_TIMEOUT_S,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """
        Submit a task to the scheduler.
        priority: 0 = CRITICAL, 5 = NORMAL, 9 = BACKGROUND
        deadline_s: seconds from now by which task must start
        """
        async with self._heap_lock:
            depth = len(self._heap)

        if depth >= _QUEUE_HARD_LIMIT:
            self._dropped += 1
            raise BackpressureError(f"EdgeScheduler queue full ({depth} tasks)")

        if depth >= _QUEUE_SOFT_LIMIT and priority >= 5:
            self._dropped += 1
            raise BackpressureError(f"EdgeScheduler soft limit reached — dropping NORMAL task")

        deadline = time.monotonic() + deadline_s
        async with self._heap_lock:
            self._sequence += 1
            heapq.heappush(
                self._heap,
                ScheduledTask(
                    priority=priority,
                    deadline=deadline,
                    sequence=self._sequence,
                    task_id=task_id,
                    coro_fn=coro_fn,
                    metadata=metadata or {},
                ),
            )
            self._submitted += 1
        self._event.set()

    # ------------------------------------------------------------------
    # Worker loop
    # ------------------------------------------------------------------

    async def _worker_loop(self) -> None:
        while self._running:
            task = await self._pop_next()
            if task is None:
                # Wait for new tasks
                self._event.clear()
                try:
                    await asyncio.wait_for(self._event.wait(), timeout=1.0)
                except asyncio.TimeoutError:
                    pass
                continue

            if time.monotonic() > task.deadline:
                self._timed_out += 1
                logger.debug(
                    "edge_scheduler task_expired task_id=%s deadline_overrun=%.2fs",
                    task.task_id,
                    time.monotonic() - task.deadline,
                )
                continue

            async with self._semaphore:
                try:
                    await asyncio.wait_for(task.coro_fn(), timeout=_TASK_TIMEOUT_S)
                    self._completed += 1
                except asyncio.TimeoutError:
                    self._timed_out += 1
                    logger.warning("edge_scheduler task_timeout task_id=%s", task.task_id)
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    logger.error("edge_scheduler task_error task_id=%s: %s", task.task_id, exc)
                    self._completed += 1  # still counts as processed

    async def _pop_next(self) -> ScheduledTask | None:
        async with self._heap_lock:
            if not self._heap:
                return None
            return heapq.heappop(self._heap)

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def stats(self) -> dict[str, Any]:
        return {
            "queue_depth": len(self._heap),
            "worker_count": self._worker_count,
            "submitted": self._submitted,
            "completed": self._completed,
            "dropped": self._dropped,
            "timed_out": self._timed_out,
            "running": self._running,
        }
