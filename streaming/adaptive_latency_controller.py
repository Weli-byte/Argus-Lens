"""
Adaptive Latency Controller — dynamic FPS scaling and frame-drop decisions
based on real-time queue pressure measurements.
"""

from __future__ import annotations

import asyncio
import hashlib
import time
from collections import deque
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

from fastapi import WebSocket
from loguru import logger
from prometheus_client import Counter, Gauge, Histogram

if TYPE_CHECKING:
    pass

# ---------------------------------------------------------------------------
# Prometheus
# ---------------------------------------------------------------------------

_LATENCY_HIST = Histogram(
    "arguslens_frame_processing_latency_ms",
    "End-to-end frame processing latency (ms)",
    buckets=[5, 10, 25, 50, 100, 250, 500, 1000, 2500],
)
_FRAME_DROP = Counter(
    "arguslens_frame_drop_total",
    "Total number of dropped frames",
    ["reason"],
)
_ACTIVE_FPS = Gauge(
    "arguslens_active_fps",
    "Currently active streaming FPS target",
)


# ---------------------------------------------------------------------------
# Domain types
# ---------------------------------------------------------------------------


class StreamDegradationLevel(str, Enum):
    OPTIMAL = "OPTIMAL"
    DEGRADED = "DEGRADED"
    CRITICAL = "CRITICAL"
    EMERGENCY = "EMERGENCY"


@dataclass
class LatencyMetrics:
    queue_depth: int
    avg_latency_ms: float
    drop_rate: float
    current_fps: float


# ---------------------------------------------------------------------------
# Controller
# ---------------------------------------------------------------------------


class AdaptiveLatencyController:
    """
    Monitors queue pressure and adjusts streaming FPS dynamically to avoid
    client-side buffering and server-side OOM.

    Degradation tiers (relative to *target_fps*):
        OPTIMAL   → 100 %
        DEGRADED  →  75 %
        CRITICAL  →  50 %
        EMERGENCY →  25 %

    Frame-drop decisions are deterministic: the same frame_id at the same
    drop_rate always produces the same drop/keep decision, enabling consistent
    behaviour across distributed workers.
    """

    # Queue-depth thresholds that trigger level transitions
    _DEGRADED_THRESHOLD = 0.40   # > 40 % of max_queue
    _CRITICAL_THRESHOLD = 0.70   # > 70 %
    _EMERGENCY_THRESHOLD = 0.90  # > 90 %

    def __init__(
        self,
        target_fps: float = 30.0,
        max_queue_depth: int = 100,
    ) -> None:
        self.target_fps = target_fps
        self.max_queue_depth = max_queue_depth
        self._latency_window: deque[float] = deque(maxlen=100)
        self._drop_count = 0
        self._total_frames = 0
        self._current_fps = target_fps
        self._current_level = StreamDegradationLevel.OPTIMAL
        _ACTIVE_FPS.set(target_fps)

    # ------------------------------------------------------------------
    # Queue pressure monitoring
    # ------------------------------------------------------------------

    async def monitor_queue_pressure(
        self, queue: asyncio.Queue[object]
    ) -> StreamDegradationLevel:
        """
        Evaluate the current *queue* size, map it to a degradation level, and
        adjust the active FPS target.  Returns the new degradation level.
        """
        depth = queue.qsize()
        ratio = depth / max(self.max_queue_depth, 1)

        if ratio >= self._EMERGENCY_THRESHOLD:
            level = StreamDegradationLevel.EMERGENCY
        elif ratio >= self._CRITICAL_THRESHOLD:
            level = StreamDegradationLevel.CRITICAL
        elif ratio >= self._DEGRADED_THRESHOLD:
            level = StreamDegradationLevel.DEGRADED
        else:
            level = StreamDegradationLevel.OPTIMAL

        if level != self._current_level:
            logger.info(
                "Stream degradation level {} → {} (queue={}/{})",
                self._current_level,
                level,
                depth,
                self.max_queue_depth,
            )
            self._current_level = level
            self._current_fps = self.calculate_dynamic_fps(level)
            _ACTIVE_FPS.set(self._current_fps)

        return level

    # ------------------------------------------------------------------
    # FPS calculation
    # ------------------------------------------------------------------

    def calculate_dynamic_fps(self, degradation_level: StreamDegradationLevel) -> float:
        """Return the FPS target for the given degradation level."""
        multipliers = {
            StreamDegradationLevel.OPTIMAL: 1.00,
            StreamDegradationLevel.DEGRADED: 0.75,
            StreamDegradationLevel.CRITICAL: 0.50,
            StreamDegradationLevel.EMERGENCY: 0.25,
        }
        fps = self.target_fps * multipliers[degradation_level]
        return max(fps, 1.0)  # never go below 1 FPS

    # ------------------------------------------------------------------
    # Frame drop decision (deterministic)
    # ------------------------------------------------------------------

    def should_drop_frame(self, frame_id: int, drop_rate: float) -> bool:
        """
        Deterministic drop decision: given the same *frame_id* and *drop_rate*
        this always returns the same result, making behaviour reproducible
        across replicas.

        Uses a hash-derived pseudo-random value so dropped frames are spread
        evenly across the sequence rather than clustered.
        """
        if drop_rate <= 0.0:
            return False
        if drop_rate >= 1.0:
            _FRAME_DROP.labels(reason="emergency").inc()
            return True

        digest = hashlib.md5(str(frame_id).encode(), usedforsecurity=False).hexdigest()
        bucket = int(digest[:8], 16) / 0xFFFFFFFF  # float in [0, 1]

        should_drop = bucket < drop_rate
        if should_drop:
            _FRAME_DROP.labels(reason="backpressure").inc()
        return should_drop

    # ------------------------------------------------------------------
    # WebSocket congestion handler
    # ------------------------------------------------------------------

    async def handle_websocket_congestion(
        self,
        websocket: WebSocket,
        backlog_size: int,
    ) -> bool:
        """
        Evaluate WebSocket send-buffer backlog.  If the backlog exceeds the
        max queue depth, send a control message to the client and return True
        (caller should throttle or skip the next frame).
        """
        if backlog_size <= 0:
            return False

        ratio = backlog_size / max(self.max_queue_depth, 1)
        if ratio >= self._EMERGENCY_THRESHOLD:
            try:
                await websocket.send_json(
                    {
                        "type": "stream_control",
                        "action": "throttle",
                        "fps": self.calculate_dynamic_fps(StreamDegradationLevel.EMERGENCY),
                        "reason": "EMERGENCY_CONGESTION",
                    }
                )
            except Exception as exc:
                logger.warning("Could not send congestion control frame: {}", exc)
            _FRAME_DROP.labels(reason="congestion").inc()
            return True

        return False

    # ------------------------------------------------------------------
    # Latency recording
    # ------------------------------------------------------------------

    def record_latency(self, latency_ms: float) -> None:
        """Record a single frame's end-to-end latency measurement."""
        self._latency_window.append(latency_ms)
        _LATENCY_HIST.observe(latency_ms)
        self._total_frames += 1

    # ------------------------------------------------------------------
    # Metrics snapshot
    # ------------------------------------------------------------------

    def get_metrics(self) -> LatencyMetrics:
        """Return a current snapshot of latency and drop metrics."""
        avg = (
            sum(self._latency_window) / len(self._latency_window)
            if self._latency_window
            else 0.0
        )
        drop_rate = (
            self._drop_count / self._total_frames if self._total_frames > 0 else 0.0
        )
        return LatencyMetrics(
            queue_depth=0,  # caller should pass current queue.qsize() if needed
            avg_latency_ms=round(avg, 2),
            drop_rate=round(drop_rate, 4),
            current_fps=self._current_fps,
        )
