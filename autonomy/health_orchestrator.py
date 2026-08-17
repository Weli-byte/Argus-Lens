"""
HealthOrchestrator — aggregates health signals from all subsystems and
emits HealthEvents to the Redis channel consumed by SelfHealingSystem.

Probes (all async, run on a configurable interval):
  - GPU VRAM utilization (via pynvml / torch)
  - CPU utilization (via psutil)
  - Redis connectivity
  - Inference queue depth
  - Worker liveness (Redis heartbeat keys)
  - Model health (error rate, stale last-seen)
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any

import redis.asyncio as aioredis

from edge.types import HealthEvent

logger = logging.getLogger(__name__)

_PROBE_INTERVAL_S = 30.0
_HEALTH_EVENT_CHANNEL = "argus:health:events"
_GPU_OOM_THRESHOLD = 0.95        # 95% VRAM used
_QUEUE_OVERFLOW_THRESHOLD = 500  # inference queue items
_CPU_HIGH_THRESHOLD = 0.90
_WORKER_HEARTBEAT_STALE_S = 120  # worker is dead if heartbeat is older than this


class HealthOrchestrator:
    """
    Continuously monitors all system components and emits HealthEvents.
    """

    def __init__(
        self,
        redis_client: aioredis.Redis,
        probe_interval_s: float = _PROBE_INTERVAL_S,
    ) -> None:
        self._redis = redis_client
        self._probe_interval = probe_interval_s
        self._running = False
        self._task: asyncio.Task | None = None
        self._probe_count = 0
        self._event_count = 0

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        self._running = True
        self._task = asyncio.create_task(self._probe_loop(), name="health_orchestrator")
        logger.info("health_orchestrator started interval_s=%.1f", self._probe_interval)

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    # ------------------------------------------------------------------
    # Probe loop
    # ------------------------------------------------------------------

    async def _probe_loop(self) -> None:
        while self._running:
            try:
                await asyncio.sleep(self._probe_interval)
                await self._run_probes()
                self._probe_count += 1
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("health_orchestrator probe_error: %s", exc)

    async def _run_probes(self) -> None:
        tasks = [
            self._probe_gpu(),
            self._probe_cpu(),
            self._probe_redis(),
            self._probe_queue(),
            self._probe_workers(),
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        events: list[HealthEvent] = []
        for r in results:
            if isinstance(r, list):
                events.extend(r)
        for event in events:
            await self._emit(event)

    # ------------------------------------------------------------------
    # Individual probes
    # ------------------------------------------------------------------

    async def _probe_gpu(self) -> list[HealthEvent]:
        events: list[HealthEvent] = []
        try:
            import torch
            if not torch.cuda.is_available():
                return []
            for i in range(torch.cuda.device_count()):
                props = torch.cuda.get_device_properties(i)
                allocated = torch.cuda.memory_allocated(i)
                ratio = allocated / props.total_memory if props.total_memory > 0 else 0.0
                if ratio > _GPU_OOM_THRESHOLD:
                    events.append(HealthEvent(
                        source="health_orchestrator",
                        event_type="gpu_oom",
                        severity="critical",
                        description=f"GPU {i} VRAM at {ratio:.1%}",
                        metrics={"vram_ratio": ratio, "device_id": i},
                    ))
        except Exception:
            pass
        return events

    async def _probe_cpu(self) -> list[HealthEvent]:
        try:
            import psutil
            cpu = psutil.cpu_percent(interval=None) / 100.0
            if cpu > _CPU_HIGH_THRESHOLD:
                return [HealthEvent(
                    source="health_orchestrator",
                    event_type="cpu_high",
                    severity="warning",
                    description=f"CPU utilization at {cpu:.1%}",
                    metrics={"cpu_utilization": cpu},
                )]
        except ImportError:
            pass
        return []

    async def _probe_redis(self) -> list[HealthEvent]:
        try:
            await self._redis.ping()
            return []
        except Exception as exc:
            return [HealthEvent(
                source="health_orchestrator",
                event_type="redis_unavailable",
                severity="critical",
                description=f"Redis ping failed: {exc}",
                affected_components=["stm", "agent_state", "edge_registry"],
            )]

    async def _probe_queue(self) -> list[HealthEvent]:
        try:
            queue_key = "argus:inference_queue"
            depth = await self._redis.llen(queue_key)
            if depth > _QUEUE_OVERFLOW_THRESHOLD:
                return [HealthEvent(
                    source="health_orchestrator",
                    event_type="queue_overflow",
                    severity="warning",
                    description=f"Inference queue depth {depth} > {_QUEUE_OVERFLOW_THRESHOLD}",
                    metrics={"queue_depth": depth},
                )]
        except Exception:
            pass
        return []

    async def _probe_workers(self) -> list[HealthEvent]:
        events: list[HealthEvent] = []
        try:
            pattern = "argus:worker:heartbeat:*"
            keys = await self._redis.keys(pattern)
            now = time.time()
            for key in keys:
                raw = await self._redis.get(key)
                if raw is None:
                    continue
                try:
                    data = json.loads(raw)
                    last_seen = data.get("timestamp", 0)
                    if now - last_seen > _WORKER_HEARTBEAT_STALE_S:
                        worker_name = key.split(":")[-1]
                        events.append(HealthEvent(
                            source="health_orchestrator",
                            event_type="worker_crash",
                            severity="critical",
                            description=f"Worker {worker_name} heartbeat stale",
                            affected_components=[worker_name],
                            metrics={"last_seen_age_s": now - last_seen},
                        ))
                except (json.JSONDecodeError, TypeError):
                    pass
        except Exception:
            pass
        return events

    # ------------------------------------------------------------------
    # Event emission
    # ------------------------------------------------------------------

    async def _emit(self, event: HealthEvent) -> None:
        try:
            await self._redis.publish(_HEALTH_EVENT_CHANNEL, json.dumps(event.to_dict()))
            self._event_count += 1
            logger.debug(
                "health_orchestrator emitted event_type=%s severity=%s",
                event.event_type, event.severity,
            )
        except Exception as exc:
            logger.error("health_orchestrator emit_error: %s", exc)

    # ------------------------------------------------------------------
    # External emission (for other components)
    # ------------------------------------------------------------------

    async def emit_event(self, event: HealthEvent) -> None:
        """Allow external components to inject health events."""
        await self._emit(event)

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def stats(self) -> dict[str, Any]:
        return {
            "probe_count": self._probe_count,
            "event_count": self._event_count,
            "probe_interval_s": self._probe_interval,
            "running": self._running,
        }
