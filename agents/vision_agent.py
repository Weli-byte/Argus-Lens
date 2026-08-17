"""
VisionAgent — processes new inference results through the intelligence pipeline.
Triggers anomaly escalation when severity warrants it.
"""

from __future__ import annotations

import logging

import redis.asyncio as aioredis

from agents.base_agent import BaseAgent
from intelligence.multimodal_router import MultimodalRouter
from intelligence.types import AgentState, AgentTask, InsightSeverity, MemoryEntry, MemoryType
from memory.short_term_memory import ShortTermMemory

logger = logging.getLogger(__name__)

_ESCALATE_SEVERITIES = {InsightSeverity.CRITICAL.value, InsightSeverity.EMERGENCY.value}


class VisionAgent(BaseAgent):
    """
    Triggered by incoming inference results.
    Routes vision data through MultimodalRouter → stores insight → escalates if critical.
    """

    def __init__(
        self,
        agent_id: str,
        redis_client: aioredis.Redis,
        multimodal_router: MultimodalRouter,
        short_term_memory: ShortTermMemory,
        anomaly_agent: "BaseAgent | None" = None,
    ) -> None:
        super().__init__(agent_id, "vision_agent", redis_client)
        self._router = multimodal_router
        self._stm = short_term_memory
        self._anomaly_agent = anomaly_agent

    def set_anomaly_agent(self, agent: "BaseAgent") -> None:
        self._anomaly_agent = agent

    async def execute(self, task: AgentTask) -> AgentTask:
        task.add_trace("vision_agent.execute start")
        await self._update_state(AgentState.REASONING)

        session_id: str = task.input_data.get("session_id", "unknown")
        vision_result: dict = task.input_data.get("vision_result", {})

        # Run through intelligence pipeline
        result = await self._router.process(
            session_id=session_id,
            vision_result=vision_result,
        )

        task.output_data = result
        task.add_trace(
            f"vision_agent.reasoning_done "
            f"severity={result.get('insight', {}).get('severity', 'unknown')} "
            f"confidence={result.get('insight', {}).get('confidence', 0):.3f}"
        )

        # Escalate to anomaly agent if critical
        insight_dict = result.get("insight", {})
        if insight_dict.get("severity") in _ESCALATE_SEVERITIES and self._anomaly_agent:
            escalation_task = AgentTask(
                agent_type="anomaly_agent",
                trigger="vision_escalation",
                priority=1,
                input_data={
                    "session_id": session_id,
                    "anomaly": insight_dict,
                    "source": "vision_agent",
                },
            )
            queued = await self._anomaly_agent.submit_task(escalation_task)
            task.add_trace(
                f"vision_agent.escalated severity={insight_dict.get('severity')} queued={queued}"
            )

        await self._update_state(AgentState.ACTING)
        task.add_trace("vision_agent.execute complete")
        return task
