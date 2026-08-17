"""
AutoScaler — Kubernetes HPA-compatible auto-scaling for ArgusLens workers.

Scale-up trigger:  CPU util > 70%  OR  inference queue depth > 80 items
Scale-down trigger: CPU util < 30% AND queue depth < 10 for 3+ consecutive checks
Scale limits:       min=2, max=20 replicas
Cooldown:          scale-up: 60s, scale-down: 120s (prevents thrashing)

When running outside Kubernetes, emits structured log events that external
orchestration tools (systemd, docker-compose watchtowers) can consume.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass
from typing import Any

from edge.types import AutonomyLevel, SelfOptimizationDecision
from optimization.self_optimization.workload_predictor import WorkloadPredictor

logger = logging.getLogger(__name__)

_SCALE_UP_CPU_THRESHOLD = 0.70
_SCALE_UP_QUEUE_THRESHOLD = 80
_SCALE_DOWN_CPU_THRESHOLD = 0.30
_SCALE_DOWN_QUEUE_THRESHOLD = 10
_SCALE_DOWN_CONSECUTIVE = 3     # consecutive calm checks before scale-down
_SCALE_UP_COOLDOWN_S = 60.0
_SCALE_DOWN_COOLDOWN_S = 120.0
_MIN_REPLICAS = 2
_MAX_REPLICAS = 20
_EVAL_INTERVAL_S = 30.0


@dataclass
class ScaleEvent:
    event_id: str
    direction: str      # "up" | "down" | "none"
    from_replicas: int
    to_replicas: int
    trigger: str
    timestamp: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "direction": self.direction,
            "from_replicas": self.from_replicas,
            "to_replicas": self.to_replicas,
            "trigger": self.trigger,
            "timestamp": self.timestamp,
        }


class AutoScaler:
    """
    Monitors system load and issues scale decisions.

    Kubernetes integration:
        If kubernetes Python client is installed and KUBECONFIG is set,
        patch the Deployment replica count directly.
        Otherwise log scale events for external consumption.
    """

    def __init__(
        self,
        predictor: WorkloadPredictor,
        deployment_name: str = "arguslens-worker",
        namespace: str = "arguslens",
        autonomy_level: AutonomyLevel = AutonomyLevel.AUTONOMOUS,
        use_k8s: bool = False,
    ) -> None:
        self._predictor = predictor
        self._deployment = deployment_name
        self._namespace = namespace
        self._autonomy = autonomy_level
        self._use_k8s = use_k8s

        self._current_replicas = _MIN_REPLICAS
        self._last_scale_up = 0.0
        self._last_scale_down = 0.0
        self._calm_checks = 0
        self._scale_history: list[ScaleEvent] = []
        self._running = False
        self._task: asyncio.Task | None = None
        self._decisions: list[SelfOptimizationDecision] = []

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        self._running = True
        self._task = asyncio.create_task(self._eval_loop(), name="auto_scaler")
        logger.info(
            "auto_scaler started deployment=%s min=%d max=%d k8s=%s",
            self._deployment, _MIN_REPLICAS, _MAX_REPLICAS, self._use_k8s,
        )

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
                cpu = self._sample_cpu()
                queue_depth = await self._sample_queue_depth()
                await self._evaluate(cpu, queue_depth)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("auto_scaler eval_error: %s", exc)

    async def _evaluate(self, cpu: float, queue_depth: int) -> None:
        forecast = self._predictor.forecast(steps_ahead=2)
        now = time.monotonic()

        should_scale_up = (
            cpu > _SCALE_UP_CPU_THRESHOLD or queue_depth > _SCALE_UP_QUEUE_THRESHOLD
        ) and self._current_replicas < _MAX_REPLICAS

        should_scale_down = (
            cpu < _SCALE_DOWN_CPU_THRESHOLD
            and queue_depth < _SCALE_DOWN_QUEUE_THRESHOLD
            and self._current_replicas > _MIN_REPLICAS
        )

        if should_scale_up:
            self._calm_checks = 0
            if now - self._last_scale_up < _SCALE_UP_COOLDOWN_S:
                return
            new_replicas = min(self._current_replicas + 2, _MAX_REPLICAS)
            trigger = f"cpu={cpu:.2f} queue={queue_depth} forecast_rps={forecast.forecast_rps:.2f}"
            await self._scale(new_replicas, "up", trigger)

        elif should_scale_down:
            self._calm_checks += 1
            if self._calm_checks < _SCALE_DOWN_CONSECUTIVE:
                return
            if now - self._last_scale_down < _SCALE_DOWN_COOLDOWN_S:
                return
            new_replicas = max(self._current_replicas - 1, _MIN_REPLICAS)
            trigger = f"cpu={cpu:.2f} queue={queue_depth} calm_checks={self._calm_checks}"
            await self._scale(new_replicas, "down", trigger)
            self._calm_checks = 0
        else:
            self._calm_checks = 0

    # ------------------------------------------------------------------
    # Scaling action
    # ------------------------------------------------------------------

    async def _scale(self, new_replicas: int, direction: str, trigger: str) -> None:
        if self._autonomy == AutonomyLevel.SUPERVISED:
            logger.info(
                "auto_scaler proposed_scale direction=%s replicas=%d->%d trigger=%s "
                "— awaiting human approval",
                direction, self._current_replicas, new_replicas, trigger,
            )
            return

        event = ScaleEvent(
            event_id=str(uuid.uuid4()),
            direction=direction,
            from_replicas=self._current_replicas,
            to_replicas=new_replicas,
            trigger=trigger,
            timestamp=time.monotonic(),
        )

        if self._use_k8s:
            success = await self._k8s_patch_replicas(new_replicas)
        else:
            success = True
            logger.info(
                "auto_scaler scale_%s replicas=%d->%d trigger=%s",
                direction, self._current_replicas, new_replicas, trigger,
            )

        if success:
            decision = SelfOptimizationDecision(
                decision_type=f"scale_{direction}",
                trigger=trigger,
                action_taken=f"Replicas {self._current_replicas} -> {new_replicas}",
                expected_outcome="Balanced load and latency",
                autonomy_level=self._autonomy,
                parameters={"from": self._current_replicas, "to": new_replicas},
            )
            self._decisions.append(decision)
            self._scale_history.append(event)
            self._current_replicas = new_replicas
            if direction == "up":
                self._last_scale_up = time.monotonic()
            else:
                self._last_scale_down = time.monotonic()

    async def _k8s_patch_replicas(self, replicas: int) -> bool:
        try:
            from kubernetes import client as k8s_client, config as k8s_config
            k8s_config.load_incluster_config()
            apps_v1 = k8s_client.AppsV1Api()
            patch = {"spec": {"replicas": replicas}}
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: apps_v1.patch_namespaced_deployment_scale(
                    self._deployment, self._namespace, patch
                ),
            )
            return True
        except Exception as exc:
            logger.error("auto_scaler k8s_patch_error: %s", exc)
            return False

    # ------------------------------------------------------------------
    # System probes
    # ------------------------------------------------------------------

    def _sample_cpu(self) -> float:
        try:
            import psutil
            return psutil.cpu_percent(interval=None) / 100.0
        except ImportError:
            return 0.0

    async def _sample_queue_depth(self) -> int:
        return 0  # replaced by dependency injection in production

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    def inject_queue_depth_fn(self, fn: Any) -> None:
        """Inject an async callable that returns the current queue depth."""
        self._sample_queue_depth = fn  # type: ignore[method-assign]

    def stats(self) -> dict[str, Any]:
        return {
            "current_replicas": self._current_replicas,
            "min_replicas": _MIN_REPLICAS,
            "max_replicas": _MAX_REPLICAS,
            "deployment": self._deployment,
            "scale_events": len(self._scale_history),
            "last_scale_event": self._scale_history[-1].to_dict() if self._scale_history else None,
            "autonomy_level": self._autonomy.value,
        }
