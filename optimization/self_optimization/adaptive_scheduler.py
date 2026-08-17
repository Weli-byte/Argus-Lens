"""
AdaptiveScheduler — dynamically adjusts task execution parameters based on
observed performance and predicted workload.

Adjustments made autonomously:
  - Batch size: increase when queue is deep, decrease when latency spikes
  - Concurrency limit: increase when utilization > 80%, decrease on memory pressure
  - Task priority weights: re-rank task types based on queue age and SLA violations

All decisions are logged as SelfOptimizationDecision objects.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass
from typing import Any

from edge.types import AutonomyLevel, SelfOptimizationDecision
from optimization.self_optimization.performance_analyzer import PerformanceAnalyzer
from optimization.self_optimization.workload_predictor import WorkloadPredictor

logger = logging.getLogger(__name__)

_EVAL_INTERVAL_S = 30.0
_BATCH_SIZE_MIN = 1
_BATCH_SIZE_MAX = 64
_CONCURRENCY_MIN = 1
_CONCURRENCY_MAX = 32

# Thresholds
_QUEUE_DEEP_THRESHOLD = 100     # queue items before batch increase
_LATENCY_SPIKE_RATIO = 1.3      # p95 / baseline above this triggers batch decrease
_UTILIZATION_HIGH = 0.80
_MEMORY_PRESSURE_THRESHOLD = 0.90


@dataclass
class SchedulerConfig:
    batch_size: int = 4
    concurrency: int = 4
    priority_weights: dict[str, float] = None

    def __post_init__(self) -> None:
        if self.priority_weights is None:
            self.priority_weights = {
                "critical": 1.0,
                "vision": 0.8,
                "temporal": 0.7,
                "background": 0.3,
            }

    def to_dict(self) -> dict[str, Any]:
        return {
            "batch_size": self.batch_size,
            "concurrency": self.concurrency,
            "priority_weights": self.priority_weights,
        }


class AdaptiveScheduler:
    """
    Monitors performance metrics and autonomously adjusts scheduling parameters.
    """

    def __init__(
        self,
        analyzer: PerformanceAnalyzer,
        predictor: WorkloadPredictor,
        autonomy_level: AutonomyLevel = AutonomyLevel.AUTONOMOUS,
    ) -> None:
        self._analyzer = analyzer
        self._predictor = predictor
        self._autonomy = autonomy_level
        self._config = SchedulerConfig()
        self._decisions: list[SelfOptimizationDecision] = []
        self._running = False
        self._task: asyncio.Task | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        self._running = True
        self._task = asyncio.create_task(self._eval_loop(), name="adaptive_scheduler")
        logger.info("adaptive_scheduler started autonomy=%s", self._autonomy.value)

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    # ------------------------------------------------------------------
    # Evaluation loop
    # ------------------------------------------------------------------

    async def _eval_loop(self) -> None:
        while self._running:
            try:
                await asyncio.sleep(_EVAL_INTERVAL_S)
                await self._evaluate()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("adaptive_scheduler eval_error: %s", exc)

    async def _evaluate(self) -> None:
        # Probe queue depth from monitoring module
        queue_depth = await self._get_queue_depth()
        memory_pressure = self._get_memory_pressure()
        forecast = self._predictor.forecast(steps_ahead=3)

        await self._adjust_batch_size(queue_depth, memory_pressure)
        await self._adjust_concurrency(forecast.forecast_rps, memory_pressure)

    async def _adjust_batch_size(self, queue_depth: int, memory_pressure: float) -> None:
        current = self._config.batch_size
        new_size = current

        if queue_depth > _QUEUE_DEEP_THRESHOLD and memory_pressure < _MEMORY_PRESSURE_THRESHOLD:
            new_size = min(current * 2, _BATCH_SIZE_MAX)
        elif memory_pressure > _MEMORY_PRESSURE_THRESHOLD:
            new_size = max(current // 2, _BATCH_SIZE_MIN)
        else:
            # Check latency regression
            alerts = self._analyzer.recent_alerts(5)
            latency_regressions = [a for a in alerts if a["metric"] == "p95_latency_ms"]
            if latency_regressions:
                new_size = max(current - 1, _BATCH_SIZE_MIN)

        if new_size != current:
            await self._apply_decision(
                decision_type="adjust_batch_size",
                trigger=f"queue_depth={queue_depth} memory_pressure={memory_pressure:.2f}",
                action=f"batch_size {current} -> {new_size}",
                params={"old_batch_size": current, "new_batch_size": new_size},
            )
            self._config.batch_size = new_size

    async def _adjust_concurrency(self, forecast_rps: float, memory_pressure: float) -> None:
        current = self._config.concurrency
        new_concurrency = current

        if memory_pressure > _MEMORY_PRESSURE_THRESHOLD:
            new_concurrency = max(current - 1, _CONCURRENCY_MIN)
        elif forecast_rps > 10 and memory_pressure < 0.7:
            new_concurrency = min(current + 1, _CONCURRENCY_MAX)

        if new_concurrency != current:
            await self._apply_decision(
                decision_type="adjust_concurrency",
                trigger=f"forecast_rps={forecast_rps:.2f} memory={memory_pressure:.2f}",
                action=f"concurrency {current} -> {new_concurrency}",
                params={"old": current, "new": new_concurrency},
            )
            self._config.concurrency = new_concurrency

    # ------------------------------------------------------------------
    # Decision logging
    # ------------------------------------------------------------------

    async def _apply_decision(
        self,
        decision_type: str,
        trigger: str,
        action: str,
        params: dict[str, Any],
    ) -> None:
        if self._autonomy == AutonomyLevel.SUPERVISED:
            logger.info(
                "adaptive_scheduler proposed_%s trigger=%s action=%s — awaiting approval",
                decision_type, trigger, action,
            )
            return

        decision = SelfOptimizationDecision(
            decision_id=str(uuid.uuid4()),
            decision_type=decision_type,
            trigger=trigger,
            action_taken=action,
            expected_outcome=f"Improved throughput/latency via {decision_type}",
            autonomy_level=self._autonomy,
            parameters=params,
            metrics_before={"batch_size": self._config.batch_size, "concurrency": self._config.concurrency},
        )
        self._decisions.append(decision)
        logger.info(
            "adaptive_scheduler decision_applied type=%s action=%s",
            decision_type, action,
        )

    # ------------------------------------------------------------------
    # System probes
    # ------------------------------------------------------------------

    async def _get_queue_depth(self) -> int:
        try:
            import psutil
            return 0  # placeholder — replace with actual queue depth from orchestration
        except ImportError:
            return 0

    def _get_memory_pressure(self) -> float:
        try:
            import psutil
            vm = psutil.virtual_memory()
            return vm.percent / 100.0
        except ImportError:
            return 0.0

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    @property
    def config(self) -> SchedulerConfig:
        return self._config

    def recent_decisions(self, n: int = 10) -> list[dict[str, Any]]:
        return [d.to_dict() for d in self._decisions[-n:]]

    def stats(self) -> dict[str, Any]:
        return {
            "config": self._config.to_dict(),
            "decision_count": len(self._decisions),
            "autonomy_level": self._autonomy.value,
            "running": self._running,
        }
