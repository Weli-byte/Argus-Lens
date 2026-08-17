"""
AnomalyResponse — maps HealthEvent types to concrete response playbooks.

Each playbook is an ordered list of async action callables.  Actions are
executed sequentially; if one fails, the playbook continues (fail-safe).
All executed actions are recorded as SelfOptimizationDecision objects.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from typing import Any, Callable, Coroutine

from edge.types import AutonomyLevel, HealthEvent, SelfOptimizationDecision

logger = logging.getLogger(__name__)

# Type alias: an action is an async callable that takes a HealthEvent
Action = Callable[[HealthEvent], Coroutine[Any, Any, None]]


class AnomalyResponse:
    """
    Executes pre-defined response playbooks for health events.
    """

    def __init__(self, autonomy_level: AutonomyLevel = AutonomyLevel.AUTONOMOUS) -> None:
        self._autonomy = autonomy_level
        self._playbooks: dict[str, list[Action]] = {}
        self._decisions: list[SelfOptimizationDecision] = []
        self._execution_count = 0
        self._failure_count = 0

    # ------------------------------------------------------------------
    # Playbook registration
    # ------------------------------------------------------------------

    def register_playbook(self, event_type: str, actions: list[Action]) -> None:
        self._playbooks[event_type] = actions
        logger.debug("anomaly_response playbook_registered event_type=%s actions=%d", event_type, len(actions))

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    async def respond(self, event: HealthEvent) -> list[SelfOptimizationDecision]:
        playbook = self._playbooks.get(event.event_type) or self._playbooks.get("*")
        if not playbook:
            logger.debug("anomaly_response no_playbook event_type=%s", event.event_type)
            return []

        if self._autonomy == AutonomyLevel.SUPERVISED and event.severity in ("warning", "info"):
            logger.info(
                "anomaly_response supervised_hold event_type=%s — awaiting approval",
                event.event_type,
            )
            return []

        decisions: list[SelfOptimizationDecision] = []
        for action in playbook:
            t0 = time.monotonic()
            action_name = getattr(action, "__name__", str(action))
            try:
                await action(event)
                duration_s = time.monotonic() - t0
                decision = SelfOptimizationDecision(
                    decision_id=str(uuid.uuid4()),
                    decision_type=f"playbook_{event.event_type}",
                    trigger=event.description,
                    action_taken=action_name,
                    expected_outcome="Recovery from health anomaly",
                    autonomy_level=self._autonomy,
                    success=True,
                )
                decision.completed_at = __import__("datetime").datetime.utcnow()
                decisions.append(decision)
                self._decisions.append(decision)
                self._execution_count += 1
                logger.info(
                    "anomaly_response action_ok event_type=%s action=%s duration_s=%.3f",
                    event.event_type, action_name, duration_s,
                )
            except Exception as exc:
                self._failure_count += 1
                logger.error(
                    "anomaly_response action_failed event_type=%s action=%s: %s",
                    event.event_type, action_name, exc,
                )

        return decisions

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def stats(self) -> dict[str, Any]:
        return {
            "registered_playbooks": list(self._playbooks.keys()),
            "execution_count": self._execution_count,
            "failure_count": self._failure_count,
            "autonomy_level": self._autonomy.value,
        }

    def recent_decisions(self, n: int = 10) -> list[dict[str, Any]]:
        return [d.to_dict() for d in self._decisions[-n:]]
