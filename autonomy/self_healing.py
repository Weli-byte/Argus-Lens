"""
SelfHealingSystem — top-level self-healing coordinator.

Consumes HealthEvents from a queue (published by MonitoringAgent or
HealthOrchestrator), classifies severity, and dispatches to AnomalyResponse
playbooks via RecoveryEngine.

Autonomous action boundaries (governed by AutonomyLevel):
  SUPERVISED:  log + propose, never act
  SEMI_AUTO:   act on INFO/WARNING, escalate CRITICAL/EMERGENCY
  AUTONOMOUS:  act on all severities, log every decision
  EMERGENCY:   bypass cooldowns, act immediately
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

import redis.asyncio as aioredis

from autonomy.anomaly_response import AnomalyResponse
from autonomy.recovery_engine import RecoveryEngine
from edge.types import AutonomyLevel, HealthEvent, SelfOptimizationDecision

logger = logging.getLogger(__name__)

_HEALTH_EVENT_CHANNEL = "argus:health:events"
_ESCALATION_CHANNEL = "argus:health:escalations"
_HEAL_COOLDOWN_S: dict[str, float] = {
    "info": 300.0,
    "warning": 120.0,
    "critical": 60.0,
    "emergency": 0.0,
}


class SelfHealingSystem:
    """
    Subscribes to the health event Redis channel and coordinates recovery.
    """

    def __init__(
        self,
        redis_client: aioredis.Redis,
        autonomy_level: AutonomyLevel = AutonomyLevel.AUTONOMOUS,
    ) -> None:
        self._redis = redis_client
        self._autonomy = autonomy_level
        self._recovery = RecoveryEngine(redis_client)
        self._response = AnomalyResponse(autonomy_level)
        self._running = False
        self._task: asyncio.Task | None = None
        self._event_count = 0
        self._healed_count = 0
        self._escalated_count = 0
        self._cooldowns: dict[str, float] = {}   # event_type -> last_healed_time
        self._decisions: list[SelfOptimizationDecision] = []

        self._register_default_playbooks()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        self._running = True
        self._task = asyncio.create_task(self._event_loop(), name="self_healing")
        logger.info("self_healing started autonomy=%s", self._autonomy.value)

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    # ------------------------------------------------------------------
    # Event loop — Redis pub/sub consumer
    # ------------------------------------------------------------------

    async def _event_loop(self) -> None:
        pubsub = self._redis.pubsub()
        await pubsub.subscribe(_HEALTH_EVENT_CHANNEL)
        try:
            async for message in pubsub.listen():
                if not self._running:
                    break
                if message["type"] != "message":
                    continue
                try:
                    import json
                    data = json.loads(message["data"])
                    event = HealthEvent.from_dict(data)
                    await self._handle_event(event)
                except Exception as exc:
                    logger.error("self_healing parse_error: %s", exc)
        except asyncio.CancelledError:
            pass
        finally:
            await pubsub.unsubscribe(_HEALTH_EVENT_CHANNEL)

    # ------------------------------------------------------------------
    # Event handling
    # ------------------------------------------------------------------

    async def _handle_event(self, event: HealthEvent) -> None:
        self._event_count += 1
        logger.info(
            "self_healing event_received type=%s severity=%s source=%s",
            event.event_type, event.severity, event.source,
        )

        if not self._should_act(event):
            return

        if not self._check_cooldown(event):
            logger.debug("self_healing cooldown_active event_type=%s", event.event_type)
            return

        decisions = await self._response.respond(event)
        self._decisions.extend(decisions)

        if decisions:
            self._healed_count += 1
            self._cooldowns[event.event_type] = time.monotonic()
            logger.info(
                "self_healing healed event_type=%s actions=%d",
                event.event_type, len(decisions),
            )

        if event.severity in ("critical", "emergency"):
            await self._escalate(event)

    def _should_act(self, event: HealthEvent) -> bool:
        if self._autonomy == AutonomyLevel.SUPERVISED:
            logger.info("self_healing supervised_log_only event=%s", event.event_type)
            return False
        if self._autonomy == AutonomyLevel.SEMI_AUTO:
            return event.severity not in ("critical", "emergency")
        return True

    def _check_cooldown(self, event: HealthEvent) -> bool:
        if self._autonomy == AutonomyLevel.EMERGENCY:
            return True
        cooldown = _HEAL_COOLDOWN_S.get(event.severity, 120.0)
        last = self._cooldowns.get(event.event_type, 0.0)
        return time.monotonic() - last >= cooldown

    async def _escalate(self, event: HealthEvent) -> None:
        try:
            import json
            await self._redis.publish(_ESCALATION_CHANNEL, json.dumps(event.to_dict()))
            self._escalated_count += 1
            logger.warning(
                "self_healing escalated event_type=%s severity=%s",
                event.event_type, event.severity,
            )
        except Exception as exc:
            logger.error("self_healing escalation_error: %s", exc)

    # ------------------------------------------------------------------
    # External event injection (for testing / non-pubsub sources)
    # ------------------------------------------------------------------

    async def inject_event(self, event: HealthEvent) -> None:
        """Directly inject a HealthEvent for immediate processing."""
        await self._handle_event(event)

    # ------------------------------------------------------------------
    # Default playbooks
    # ------------------------------------------------------------------

    def _register_default_playbooks(self) -> None:
        async def _restart_inference_worker(event: HealthEvent) -> None:
            await self._recovery.restart_worker("inference_worker")

        async def _flush_inference_cache(event: HealthEvent) -> None:
            await self._recovery.flush_cache("argus:inference:*")

        async def _clear_overflowed_queue(event: HealthEvent) -> None:
            await self._recovery.clear_queue()

        async def _reduce_concurrency(event: HealthEvent) -> None:
            await self._recovery.reduce_load(factor=0.5)

        self._response.register_playbook("worker_crash", [_restart_inference_worker])
        self._response.register_playbook("queue_overflow", [_clear_overflowed_queue, _reduce_concurrency])
        self._response.register_playbook("memory_pressure", [_flush_inference_cache, _reduce_concurrency])
        self._response.register_playbook("gpu_oom", [_flush_inference_cache, _reduce_concurrency])
        self._response.register_playbook("model_error", [_flush_inference_cache])

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def stats(self) -> dict[str, Any]:
        return {
            "autonomy_level": self._autonomy.value,
            "events_received": self._event_count,
            "events_healed": self._healed_count,
            "events_escalated": self._escalated_count,
            "recovery": self._recovery.stats(),
            "response": self._response.stats(),
            "running": self._running,
        }

    def recent_decisions(self, n: int = 10) -> list[dict[str, Any]]:
        return [d.to_dict() for d in self._decisions[-n:]]
