"""
AnomalyAgent — multi-source anomaly validation and escalation.
Prevents false-positive escalation via cross-validation before acting.
"""

from __future__ import annotations

import logging
from typing import Any

import redis.asyncio as aioredis

from agents.base_agent import BaseAgent
from intelligence.multimodal_router import MultimodalRouter
from intelligence.types import AgentState, AgentTask, InsightSeverity, MemoryEntry, MemoryType
from memory.long_term_memory import LongTermMemory
from memory.retrieval_manager import RetrievalManager

logger = logging.getLogger(__name__)

_FALSE_POSITIVE_THRESHOLD = 0.6  # if history says >60% were FP, don't escalate


class AnomalyAgent(BaseAgent):
    """
    Validates and escalates anomalies confirmed by multiple sources.
    Stores outcomes to LTM for future false-positive avoidance.
    """

    def __init__(
        self,
        agent_id: str,
        redis_client: aioredis.Redis,
        multimodal_router: MultimodalRouter,
        retrieval_manager: RetrievalManager,
        long_term_memory: LongTermMemory,
    ) -> None:
        super().__init__(agent_id, "anomaly_agent", redis_client)
        self._router = multimodal_router
        self._retrieval = retrieval_manager
        self._ltm = long_term_memory

    async def execute(self, task: AgentTask) -> AgentTask:
        task.add_trace("anomaly_agent.execute start")
        await self._update_state(AgentState.ANALYZING)

        session_id: str = task.input_data.get("session_id", "unknown")
        anomaly: dict[str, Any] = task.input_data.get("anomaly", {})
        source: str = task.input_data.get("source", "unknown")

        task.add_trace(
            f"anomaly_agent.received source={source} "
            f"severity={anomaly.get('severity', '?')}"
        )

        # Cross-validate
        await self._update_state(AgentState.REASONING)
        validated, confidence = await self._cross_validate_anomaly(anomaly, session_id)
        task.add_trace(
            f"anomaly_agent.cross_validate validated={validated} confidence={confidence:.3f}"
        )

        if not validated:
            task.output_data = {
                "validated": False,
                "reason": "Insufficient cross-source confirmation",
                "confidence": confidence,
            }
            logger.info(
                "anomaly_agent.not_validated session=%s source=%s confidence=%.3f",
                session_id,
                source,
                confidence,
            )
            return task

        # Escalate: re-process with AGENTIC mode
        await self._update_state(AgentState.ACTING)
        from intelligence.types import ReasoningMode
        result = await self._router.process(
            session_id=session_id,
            temporal_metrics=task.input_data.get("window_analysis"),
            force_mode=ReasoningMode.AGENTIC,
        )
        task.output_data = result

        # Store to LTM for outcome tracking
        entry = MemoryEntry(
            memory_type=MemoryType.EPISODIC,
            content=(
                f"Validated anomaly: {anomaly.get('title', 'Unknown')} "
                f"(confidence={confidence:.2f}) from {source}"
            ),
            importance_score=min(1.0, confidence * 1.2),
            tags=["anomaly", source, anomaly.get("severity", "unknown")],
            source="anomaly_agent",
            metadata={
                "session_id": session_id,
                "original_severity": anomaly.get("severity"),
                "validated": True,
                "confidence": confidence,
            },
        )
        await self._retrieval.store_to_stm(session_id, entry)
        await self._retrieval.consolidate_to_ltm(session_id, entry)

        task.add_trace(
            f"anomaly_agent.escalated insight_id="
            f"{result.get('insight', {}).get('insight_id', '?')}"
        )
        logger.warning(
            "anomaly_agent.escalated session=%s source=%s confidence=%.3f",
            session_id,
            source,
            confidence,
        )
        return task

    async def _cross_validate_anomaly(
        self, anomaly: dict[str, Any], session_id: str
    ) -> tuple[bool, float]:
        """
        Check Redis for concurrent anomaly signals from other sources.
        An anomaly is validated if at least one other active signal exists.
        """
        try:
            vision_key = f"argus:anomaly:active:{session_id}:vision"
            temporal_key = f"argus:anomaly:active:{session_id}:temporal"

            vision_active = await self._redis.exists(vision_key)
            temporal_active = await self._redis.exists(temporal_key)
            source_count = int(vision_active) + int(temporal_active)

            # Check LTM for historical false-positive rate
            history = await self._ltm.semantic_search(
                query=f"false positive anomaly {anomaly.get('title', '')}",
                top_k=5,
                min_similarity=0.6,
            )
            fp_ratio = 0.0
            if history:
                fp_entries = [
                    e for e, _ in history if "false_positive" in e.tags
                ]
                fp_ratio = len(fp_entries) / len(history)

            if fp_ratio > _FALSE_POSITIVE_THRESHOLD:
                return False, 1.0 - fp_ratio

            # Validate if severity is high enough or multi-source
            severity = anomaly.get("severity", "")
            if severity == InsightSeverity.EMERGENCY.value:
                return True, 0.95
            if severity == InsightSeverity.CRITICAL.value and source_count >= 1:
                return True, 0.85
            if source_count >= 2:
                return True, 0.75

            # Single source warning — lower confidence
            return False, 0.40

        except Exception as exc:
            logger.warning("anomaly_agent.cross_validate error: %s", exc)
            # Default to validating on exception to avoid suppressing real alerts
            return True, 0.5
