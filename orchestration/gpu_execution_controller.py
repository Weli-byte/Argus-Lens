"""
GPU Execution Controller — priority-queued, VRAM-budgeted, stream-pooled inference scheduler.
"""

from __future__ import annotations

import asyncio
import gc
import hashlib
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Callable

from loguru import logger
from prometheus_client import Counter, Gauge

try:
    import torch

    _CUDA = torch.cuda.is_available()
except ImportError:  # pragma: no cover
    _CUDA = False

# ---------------------------------------------------------------------------
# Prometheus
# ---------------------------------------------------------------------------

_QUEUE_DEPTH = Gauge(
    "arguslens_inference_queue_depth",
    "Current number of items waiting in the inference priority queue",
    ["priority"],
)
_VRAM_USED = Gauge(
    "arguslens_vram_used_mb",
    "VRAM currently allocated by PyTorch (MB)",
)
_TIMEOUT_TOTAL = Counter(
    "arguslens_inference_timeout_total",
    "Total number of inference requests that timed out",
)


# ---------------------------------------------------------------------------
# Domain types
# ---------------------------------------------------------------------------


class InferencePriority(IntEnum):
    CRITICAL = 1
    HIGH = 2
    NORMAL = 3
    LOW = 4
    BATCH = 5


@dataclass
class VRAMReservation:
    reservation_id: str
    model_id: str
    reserved_mb: float
    expiry: float  # monotonic timestamp


@dataclass(order=False)
class _QueueItem:
    """Internal queue entry.  Ordered by (priority, sequence) for strict FIFO within tier."""

    priority: InferencePriority
    sequence: int  # monotonically increasing, used as tiebreaker
    model_fn: Callable[..., Any]
    args: tuple[Any, ...]
    kwargs: dict[str, Any]
    timeout: float
    future: asyncio.Future[Any]

    def __lt__(self, other: "_QueueItem") -> bool:
        return (self.priority, self.sequence) < (other.priority, other.sequence)

    def __le__(self, other: "_QueueItem") -> bool:
        return (self.priority, self.sequence) <= (other.priority, other.sequence)


# ---------------------------------------------------------------------------
# Controller
# ---------------------------------------------------------------------------


class GPUExecutionController:
    """
    Production-grade GPU execution controller with:

    * Priority-ordered asyncio.PriorityQueue
    * VRAM budget leasing with expiry (auto-reclaimed after 5 minutes)
    * CUDA stream pool (pre-allocated, recycled across requests)
    * Automatic OOM recovery (cache flush + reservation purge)
    * Background GPU health monitor every 5 s
    * Prometheus instrumentation throughout
    * Graceful CPU fallback when CUDA is unavailable
    """

    _VRAM_SAFETY_FACTOR = 0.90  # only lease up to 90 % of detected VRAM

    def __init__(self, max_concurrent: int = 3) -> None:
        self._queue: asyncio.PriorityQueue[_QueueItem] = asyncio.PriorityQueue()
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._seq = 0  # monotonic enqueue counter

        # VRAM budget accounting
        self._total_vram_mb: float = self._detect_total_vram()
        self._vram_budget_mb: float = self._total_vram_mb * self._VRAM_SAFETY_FACTOR
        self._active_reservations: dict[str, VRAMReservation] = {}
        self._reservation_lock = asyncio.Lock()

        # CUDA stream pool
        self._stream_pool: list[Any] = []
        self._stream_lock = asyncio.Lock()
        if _CUDA:
            for _ in range(max_concurrent):
                self._stream_pool.append(torch.cuda.Stream())

        # Priority counters for Prometheus
        self._priority_counts: dict[InferencePriority, int] = defaultdict(int)

        self._running = False
        self._worker_task: asyncio.Task[None] | None = None
        self._monitor_task: asyncio.Task[None] | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Start the queue-worker and GPU health monitor background tasks."""
        self._running = True
        self._worker_task = asyncio.create_task(self._queue_worker(), name="gpu_queue_worker")
        self._monitor_task = asyncio.create_task(self._monitor_gpu_health(), name="gpu_health_monitor")
        logger.info("GPUExecutionController started (CUDA={})", _CUDA)

    async def stop(self) -> None:
        """Signal shutdown and cancel background tasks."""
        self._running = False
        for task in (self._worker_task, self._monitor_task):
            if task and not task.done():
                task.cancel()
        logger.info("GPUExecutionController stopped.")

    # ------------------------------------------------------------------
    # VRAM Reservation API
    # ------------------------------------------------------------------

    async def reserve_vram(
        self,
        model_id: str,
        required_mb: float,
        timeout: float = 30.0,
    ) -> VRAMReservation:
        """
        Block until *required_mb* of VRAM budget is available, then return a
        lease object.  Raises TimeoutError if budget cannot be secured within
        *timeout* seconds.  Reservations auto-expire after 300 s.
        """
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            async with self._reservation_lock:
                self._purge_expired_reservations()
                used = sum(r.reserved_mb for r in self._active_reservations.values())
                if used + required_mb <= self._vram_budget_mb:
                    rid = str(uuid.uuid4())
                    reservation = VRAMReservation(
                        reservation_id=rid,
                        model_id=model_id,
                        reserved_mb=required_mb,
                        expiry=time.monotonic() + 300,
                    )
                    self._active_reservations[rid] = reservation
                    _VRAM_USED.set(used + required_mb)
                    logger.info(
                        "VRAM reserved {:.0f} MB for model={} rid={}",
                        required_mb,
                        model_id,
                        rid,
                    )
                    return reservation
            await asyncio.sleep(0.25)

        raise TimeoutError(
            f"Could not reserve {required_mb:.0f} MB VRAM for '{model_id}' within {timeout}s"
        )

    async def release_vram(self, reservation_id: str) -> None:
        """Release a previously acquired VRAM lease."""
        async with self._reservation_lock:
            if (r := self._active_reservations.pop(reservation_id, None)):
                used = sum(x.reserved_mb for x in self._active_reservations.values())
                _VRAM_USED.set(used)
                logger.info("VRAM released {:.0f} MB rid={}", r.reserved_mb, reservation_id)

    def _purge_expired_reservations(self) -> None:
        now = time.monotonic()
        expired = [rid for rid, r in self._active_reservations.items() if r.expiry < now]
        for rid in expired:
            logger.warning("Auto-expiring stale VRAM reservation rid={}", rid)
            del self._active_reservations[rid]

    # ------------------------------------------------------------------
    # Inference submission
    # ------------------------------------------------------------------

    async def execute_inference(
        self,
        priority: InferencePriority,
        model_fn: Callable[..., Any],
        *args: Any,
        timeout: float = 60.0,
        **kwargs: Any,
    ) -> Any:
        """
        Submit *model_fn* to the priority queue and await its result.
        Raises TimeoutError if the result isn't ready within *timeout* seconds.
        """
        loop = asyncio.get_running_loop()
        future: asyncio.Future[Any] = loop.create_future()

        self._seq += 1
        item = _QueueItem(
            priority=priority,
            sequence=self._seq,
            model_fn=model_fn,
            args=args,
            kwargs=kwargs,
            timeout=timeout,
            future=future,
        )
        await self._queue.put(item)
        self._priority_counts[priority] += 1
        _QUEUE_DEPTH.labels(priority=priority.name).set(self._priority_counts[priority])

        try:
            return await asyncio.wait_for(asyncio.shield(future), timeout=timeout)
        except asyncio.TimeoutError:
            _TIMEOUT_TOTAL.inc()
            logger.error("Inference timeout after {}s priority={}", timeout, priority.name)
            future.cancel()
            raise

    # ------------------------------------------------------------------
    # Queue worker
    # ------------------------------------------------------------------

    async def _queue_worker(self) -> None:
        while self._running:
            try:
                item: _QueueItem = await asyncio.wait_for(self._queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break

            self._priority_counts[item.priority] = max(
                0, self._priority_counts[item.priority] - 1
            )
            _QUEUE_DEPTH.labels(priority=item.priority.name).set(
                self._priority_counts[item.priority]
            )

            if item.future.cancelled():
                self._queue.task_done()
                continue

            # Launch execution without blocking the worker loop
            asyncio.create_task(self._run_item(item), name=f"inference_{item.sequence}")

    async def _run_item(self, item: _QueueItem) -> None:
        async with self._semaphore:
            stream = await self._acquire_stream()
            try:
                result = await asyncio.wait_for(
                    self._dispatch(item.model_fn, item.args, item.kwargs, stream),
                    timeout=item.timeout,
                )
                if not item.future.done():
                    item.future.set_result(result)
            except asyncio.TimeoutError:
                _TIMEOUT_TOTAL.inc()
                if not item.future.done():
                    item.future.set_exception(
                        TimeoutError(f"Inference exceeded {item.timeout}s")
                    )
            except RuntimeError as exc:
                if "out of memory" in str(exc).lower():
                    await self._oom_recovery()
                if not item.future.done():
                    item.future.set_exception(exc)
            except Exception as exc:
                if not item.future.done():
                    item.future.set_exception(exc)
            finally:
                await self._release_stream(stream)
                self._queue.task_done()

    async def _dispatch(
        self,
        fn: Callable[..., Any],
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
        stream: Any,
    ) -> Any:
        """Run *fn* inside a CUDA stream context (if GPU available) via executor."""
        loop = asyncio.get_running_loop()

        if _CUDA and stream is not None:
            def _run() -> Any:
                with torch.cuda.stream(stream):
                    result = fn(*args, **kwargs)
                stream.synchronize()
                return result

            return await loop.run_in_executor(None, _run)

        return await loop.run_in_executor(None, lambda: fn(*args, **kwargs))

    # ------------------------------------------------------------------
    # Stream pool
    # ------------------------------------------------------------------

    async def _acquire_stream(self) -> Any:
        if not _CUDA:
            return None
        async with self._stream_lock:
            return self._stream_pool.pop() if self._stream_pool else torch.cuda.Stream()

    async def _release_stream(self, stream: Any) -> None:
        if stream is None:
            return
        async with self._stream_lock:
            self._stream_pool.append(stream)

    # ------------------------------------------------------------------
    # OOM recovery
    # ------------------------------------------------------------------

    async def _oom_recovery(self) -> None:
        logger.error("OOM detected — flushing CUDA cache and purging VRAM reservations.")
        gc.collect()
        if _CUDA:
            torch.cuda.empty_cache()
            torch.cuda.ipc_collect()
        async with self._reservation_lock:
            self._purge_expired_reservations()
        logger.info("OOM recovery complete.")

    # ------------------------------------------------------------------
    # GPU health monitor (background, every 5 s)
    # ------------------------------------------------------------------

    async def _monitor_gpu_health(self) -> None:
        while self._running:
            try:
                await asyncio.sleep(5)
                stats = self.get_vram_status()
                _VRAM_USED.set(stats["used_mb"])
                logger.debug(
                    "GPU health used={:.0f}MB reserved={:.0f}MB total={:.0f}MB",
                    stats["used_mb"],
                    stats["reserved_mb"],
                    stats["total_mb"],
                )
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.warning("GPU health monitor error: {}", exc)

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def get_queue_depth(self) -> dict[str, int]:
        """Return per-priority queue depths."""
        return {p.name: self._priority_counts[p] for p in InferencePriority}

    def get_vram_status(self) -> dict[str, float]:
        """Return a snapshot of VRAM accounting."""
        reserved_mb = sum(r.reserved_mb for r in self._active_reservations.values())
        if _CUDA:
            dev = torch.cuda.current_device()
            used_mb = torch.cuda.memory_allocated(dev) / (1024 ** 2)
            total_mb = torch.cuda.get_device_properties(dev).total_memory / (1024 ** 2)
        else:
            used_mb = 0.0
            total_mb = 0.0
        return {
            "used_mb": round(used_mb, 1),
            "reserved_mb": round(reserved_mb, 1),
            "budget_mb": round(self._vram_budget_mb, 1),
            "total_mb": round(total_mb, 1),
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _detect_total_vram() -> float:
        if _CUDA:
            return torch.cuda.get_device_properties(0).total_memory / (1024 ** 2)
        return 0.0
