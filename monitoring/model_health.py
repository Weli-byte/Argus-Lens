"""
Model Health Monitor — per-model inference counters, error rates,
latency tracking, and liveness heartbeats.
"""

from __future__ import annotations

import asyncio
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Optional

from loguru import logger
from prometheus_client import Gauge

# ---------------------------------------------------------------------------
# Prometheus
# ---------------------------------------------------------------------------

_MODEL_HEALTH = Gauge(
    "arguslens_model_health_score_gauge",
    "Per-model health score [0, 1]",
    ["model_id"],
)
_MODEL_INFERENCE_RATE = Gauge(
    "arguslens_model_inference_rate",
    "Inferences per second (1-minute rolling)",
    ["model_id"],
)

# ---------------------------------------------------------------------------
# Domain types
# ---------------------------------------------------------------------------

_DEAD_THRESHOLD_S = 60.0    # no heartbeat for 60 s → model considered dead
_RATE_WINDOW_S = 60.0       # rolling window for rate calculation


@dataclass
class _ModelStats:
    model_id: str
    inference_count: int = 0
    error_count: int = 0
    last_seen: float = field(default_factory=time.monotonic)
    latency_window: deque[float] = field(default_factory=lambda: deque(maxlen=200))
    timestamps: deque[float] = field(default_factory=lambda: deque(maxlen=500))


# ---------------------------------------------------------------------------
# Monitor
# ---------------------------------------------------------------------------


class ModelHealthMonitor:
    """
    Tracks per-model operational health.  All state is in-process; intended to
    run inside a single API worker.  For multi-worker setups persist stats to
    Redis instead.

    Usage::

        monitor = ModelHealthMonitor()
        await monitor.heartbeat("dino_v2")
        monitor.record_inference("dino_v2", latency_ms=42.5, error=False)
        healthy = monitor.is_model_healthy("dino_v2")
        report  = monitor.get_health_report()
    """

    def __init__(self) -> None:
        self._stats: dict[str, _ModelStats] = {}
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Write path
    # ------------------------------------------------------------------

    async def heartbeat(self, model_id: str) -> None:
        """Update the liveness timestamp for *model_id*.  Create entry if new."""
        async with self._lock:
            if model_id not in self._stats:
                self._stats[model_id] = _ModelStats(model_id=model_id)
                logger.info("ModelHealthMonitor: registered model={}", model_id)
            self._stats[model_id].last_seen = time.monotonic()

    def record_inference(
        self,
        model_id: str,
        latency_ms: float,
        error: bool = False,
    ) -> None:
        """
        Record an inference attempt (synchronous, safe to call from inference
        callbacks without holding the async lock).
        """
        stats = self._stats.get(model_id)
        if stats is None:
            # Auto-register without heartbeat (inference path)
            stats = _ModelStats(model_id=model_id)
            self._stats[model_id] = stats

        stats.inference_count += 1
        stats.last_seen = time.monotonic()
        stats.latency_window.append(latency_ms)
        stats.timestamps.append(time.monotonic())

        if error:
            stats.error_count += 1

    # ------------------------------------------------------------------
    # Read path
    # ------------------------------------------------------------------

    def is_model_healthy(self, model_id: str) -> bool:
        """
        A model is healthy if:
        1. It has sent a heartbeat within *_DEAD_THRESHOLD_S* seconds, AND
        2. Its error rate over the last 200 inferences is below 10 %.
        """
        stats = self._stats.get(model_id)
        if stats is None:
            return False

        age = time.monotonic() - stats.last_seen
        if age > _DEAD_THRESHOLD_S:
            return False

        if stats.inference_count >= 20:
            error_rate = stats.error_count / stats.inference_count
            if error_rate >= 0.10:
                return False

        return True

    def get_avg_latency(self, model_id: str) -> float:
        """Return average latency (ms) over the rolling window."""
        stats = self._stats.get(model_id)
        if not stats or not stats.latency_window:
            return 0.0
        return round(sum(stats.latency_window) / len(stats.latency_window), 2)

    def get_inference_rate(self, model_id: str) -> float:
        """Inferences per second over the last _RATE_WINDOW_S seconds."""
        stats = self._stats.get(model_id)
        if not stats:
            return 0.0
        cutoff = time.monotonic() - _RATE_WINDOW_S
        recent = sum(1 for t in stats.timestamps if t >= cutoff)
        return round(recent / _RATE_WINDOW_S, 3)

    def get_health_report(self) -> dict[str, dict]:
        """
        Return a full health snapshot for all registered models.
        Also updates Prometheus gauges.
        """
        report: dict[str, dict] = {}
        for model_id, stats in self._stats.items():
            age = time.monotonic() - stats.last_seen
            error_rate = (
                stats.error_count / stats.inference_count
                if stats.inference_count > 0
                else 0.0
            )
            healthy = self.is_model_healthy(model_id)
            rate = self.get_inference_rate(model_id)

            # Health score: penalise staleness and error rate
            staleness_penalty = min(age / _DEAD_THRESHOLD_S, 1.0) * 0.5
            error_penalty = min(error_rate / 0.10, 1.0) * 0.5
            health_score = round(max(0.0, 1.0 - staleness_penalty - error_penalty), 4)

            _MODEL_HEALTH.labels(model_id=model_id).set(health_score)
            _MODEL_INFERENCE_RATE.labels(model_id=model_id).set(rate)

            report[model_id] = {
                "healthy": healthy,
                "health_score": health_score,
                "inference_count": stats.inference_count,
                "error_count": stats.error_count,
                "error_rate": round(error_rate, 4),
                "avg_latency_ms": self.get_avg_latency(model_id),
                "inference_rate_per_sec": rate,
                "last_seen_age_s": round(age, 1),
            }

        return report

    async def cleanup_dead_models(self, dead_threshold_s: float = _DEAD_THRESHOLD_S) -> list[str]:
        """Remove entries for models that haven't been seen for *dead_threshold_s* seconds."""
        async with self._lock:
            now = time.monotonic()
            dead = [
                mid
                for mid, stats in self._stats.items()
                if now - stats.last_seen > dead_threshold_s
            ]
            for mid in dead:
                del self._stats[mid]
                logger.info("ModelHealthMonitor: evicted dead model={}", mid)
        return dead
