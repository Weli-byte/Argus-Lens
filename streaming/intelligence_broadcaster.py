"""
IntelligenceStreamBroadcaster — routes intelligence layer events to WebSocket clients.

Filtering rules:
  - INFO:    batched, max 1 per 5 seconds per client
  - NOTICE:  batched, max 1 per 5 seconds per client
  - WARNING: immediate
  - CRITICAL/EMERGENCY: immediate, all connected clients
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from fastapi import WebSocket

from intelligence.types import AIInsight, AgentTask, CorrelationResult, InsightSeverity

logger = logging.getLogger(__name__)

_IMMEDIATE_SEVERITIES = {
    InsightSeverity.WARNING,
    InsightSeverity.CRITICAL,
    InsightSeverity.EMERGENCY,
}
_BATCH_INTERVAL = 5.0  # seconds between batched messages


class IntelligenceStreamBroadcaster:
    """
    Decoupled broadcaster: receives intelligence events → pushes to WS clients.
    Clients are keyed by session_id.
    """

    def __init__(self) -> None:
        # session_id → list of WebSocket connections
        self._session_sockets: dict[str, list[WebSocket]] = {}
        # session_id → last batch send time
        self._last_batch: dict[str, float] = {}
        # session_id → pending batched messages
        self._batch_queue: dict[str, list[dict[str, Any]]] = {}

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------

    def register(self, session_id: str, websocket: WebSocket) -> None:
        self._session_sockets.setdefault(session_id, []).append(websocket)
        logger.debug("intel_broadcaster.register session=%s total=%d",
                     session_id, len(self._session_sockets[session_id]))

    def unregister(self, session_id: str, websocket: WebSocket) -> None:
        sockets = self._session_sockets.get(session_id, [])
        if websocket in sockets:
            sockets.remove(websocket)
        if not sockets:
            self._session_sockets.pop(session_id, None)

    # ------------------------------------------------------------------
    # Broadcast methods (called by MultimodalRouter / agents)
    # ------------------------------------------------------------------

    async def broadcast_insight(
        self, insight: AIInsight, session_id: str
    ) -> None:
        message = {
            "type": "ai_insight",
            "payload": insight.to_dict(),
        }
        if insight.severity in _IMMEDIATE_SEVERITIES:
            await self._send_immediate(session_id, message)
            # CRITICAL/EMERGENCY also goes to ALL sessions
            if insight.severity in (InsightSeverity.CRITICAL, InsightSeverity.EMERGENCY):
                await self._broadcast_all(message)
        else:
            self._enqueue_batch(session_id, message)
            await self._maybe_flush_batch(session_id)

    async def broadcast_agent_update(
        self, agent_id: str, state: str, current_task: str | None, session_id: str
    ) -> None:
        message = {
            "type": "agent_update",
            "payload": {
                "agent_id": agent_id,
                "state": state,
                "current_task": current_task,
            },
        }
        await self._send_immediate(session_id, message)

    async def broadcast_correlation(
        self, correlation: CorrelationResult, session_id: str
    ) -> None:
        message = {
            "type": "correlation_found",
            "payload": correlation.to_dict(),
        }
        await self._send_immediate(session_id, message)

    async def broadcast_memory_consolidated(
        self, session_id: str, count: int, patterns: list[str]
    ) -> None:
        message = {
            "type": "memory_consolidated",
            "payload": {
                "session_id": session_id,
                "count": count,
                "important_patterns": patterns,
            },
        }
        self._enqueue_batch(session_id, message)
        await self._maybe_flush_batch(session_id)

    async def broadcast_knowledge_graph_update(
        self, entities_added: int, relations_added: int
    ) -> None:
        message = {
            "type": "knowledge_graph_update",
            "payload": {
                "entities_added": entities_added,
                "relations_added": relations_added,
            },
        }
        await self._broadcast_all(message)

    # ------------------------------------------------------------------
    # Internal send helpers
    # ------------------------------------------------------------------

    async def _send_immediate(
        self, session_id: str, message: dict[str, Any]
    ) -> None:
        sockets = self._session_sockets.get(session_id, [])
        dead: list[WebSocket] = []
        for ws in sockets:
            try:
                await ws.send_json(message)
            except Exception as exc:
                logger.debug("intel_broadcaster.send_error session=%s: %s", session_id, exc)
                dead.append(ws)
        for ws in dead:
            self.unregister(session_id, ws)

    async def _broadcast_all(self, message: dict[str, Any]) -> None:
        for session_id in list(self._session_sockets.keys()):
            await self._send_immediate(session_id, message)

    def _enqueue_batch(self, session_id: str, message: dict[str, Any]) -> None:
        self._batch_queue.setdefault(session_id, []).append(message)

    async def _maybe_flush_batch(self, session_id: str) -> None:
        now = time.monotonic()
        last = self._last_batch.get(session_id, 0.0)
        if now - last < _BATCH_INTERVAL:
            return
        pending = self._batch_queue.pop(session_id, [])
        if not pending:
            return
        self._last_batch[session_id] = now
        # Send last message in batch (most recent state)
        await self._send_immediate(session_id, pending[-1])
        if len(pending) > 1:
            logger.debug(
                "intel_broadcaster.batch_flush session=%s sent=1 dropped=%d",
                session_id,
                len(pending) - 1,
            )

    # ------------------------------------------------------------------
    # Phase 4 broadcast methods
    # ------------------------------------------------------------------

    async def broadcast_edge_node_update(
        self,
        node_id: str,
        state: str,
        session_id: str | None = None,
    ) -> None:
        """Broadcast edge node state change to all sessions or a specific one."""
        message = {
            "type": "edge_node_update",
            "payload": {"node_id": node_id, "state": state},
        }
        if session_id:
            await self._send_immediate(session_id, message)
        else:
            await self._broadcast_all(message)

    async def broadcast_federated_round_update(
        self,
        round_number: int,
        state: str,
        model_name: str,
        participants: int,
    ) -> None:
        """Broadcast federated learning round progress to all sessions."""
        message = {
            "type": "federated_round_update",
            "payload": {
                "round_number": round_number,
                "state": state,
                "model_name": model_name,
                "participants": participants,
            },
        }
        await self._broadcast_all(message)

    async def broadcast_self_healing_action(
        self,
        event_type: str,
        action_taken: str,
        success: bool,
        session_id: str | None = None,
    ) -> None:
        """Notify that an autonomous healing action was taken."""
        message = {
            "type": "self_healing_action",
            "payload": {
                "event_type": event_type,
                "action_taken": action_taken,
                "success": success,
            },
        }
        if session_id:
            await self._send_immediate(session_id, message)
        else:
            await self._broadcast_all(message)

    async def broadcast_scale_event(
        self,
        direction: str,
        from_replicas: int,
        to_replicas: int,
        trigger: str,
    ) -> None:
        """Broadcast auto-scaling events to all connected clients."""
        message = {
            "type": "scale_event",
            "payload": {
                "direction": direction,
                "from_replicas": from_replicas,
                "to_replicas": to_replicas,
                "trigger": trigger,
            },
        }
        await self._broadcast_all(message)

    async def broadcast_offline_mode_change(
        self,
        node_id: str,
        offline: bool,
        session_id: str | None = None,
    ) -> None:
        """Notify clients when an edge node enters or exits offline mode."""
        message = {
            "type": "offline_mode_change",
            "payload": {"node_id": node_id, "offline": offline},
        }
        if session_id:
            await self._send_immediate(session_id, message)
        else:
            await self._broadcast_all(message)

    async def broadcast_model_downgrade(
        self,
        model_name: str,
        from_precision: str,
        to_precision: str,
        reason: str,
        session_id: str | None = None,
    ) -> None:
        """Notify that a model was downgraded to a lower precision."""
        message = {
            "type": "model_downgrade",
            "payload": {
                "model_name": model_name,
                "from_precision": from_precision,
                "to_precision": to_precision,
                "reason": reason,
            },
        }
        if session_id:
            self._enqueue_batch(session_id, message)
            await self._maybe_flush_batch(session_id)
        else:
            await self._broadcast_all(message)

    async def broadcast_consensus_reached(
        self,
        session_id: str,
        agreement_score: float,
        participant_count: int,
        reasoning_summary: str,
    ) -> None:
        """Broadcast distributed cognition consensus result for a session."""
        message = {
            "type": "consensus_reached",
            "payload": {
                "session_id": session_id,
                "agreement_score": agreement_score,
                "participant_count": participant_count,
                "reasoning_summary": reasoning_summary,
            },
        }
        await self._send_immediate(session_id, message)

    async def broadcast_performance_regression(
        self,
        component: str,
        metric: str,
        current_value: float,
        baseline_value: float,
        ratio: float,
    ) -> None:
        """Broadcast a detected performance regression to all sessions."""
        message = {
            "type": "performance_regression",
            "payload": {
                "component": component,
                "metric": metric,
                "current_value": current_value,
                "baseline_value": baseline_value,
                "ratio": ratio,
            },
        }
        await self._broadcast_all(message)
