"""
OrchestrationAgent — manages and routes between all sub-agents.
Single entry point for external event dispatch.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import redis.asyncio as aioredis

from agents.anomaly_agent import AnomalyAgent
from agents.base_agent import BaseAgent
from agents.monitoring_agent import MonitoringAgent
from agents.temporal_agent import TemporalAgent
from agents.vision_agent import VisionAgent
from intelligence.types import AgentState, AgentTask

logger = logging.getLogger(__name__)

_EVENT_AGENT_MAP = {
    "vision_result": "vision",
    "temporal_anomaly": "temporal",
    "temporal_metrics": "temporal",
    "critical_alert": "anomaly",
    "system_event": "monitoring",
}


class OrchestrationAgent(BaseAgent):
    """
    Top-level agent that:
    - Starts/stops all sub-agents
    - Routes incoming events to the correct agent
    - Reports cluster-wide status
    """

    def __init__(
        self,
        agent_id: str,
        redis_client: aioredis.Redis,
        vision_agent: VisionAgent,
        temporal_agent: TemporalAgent,
        anomaly_agent: AnomalyAgent,
        monitoring_agent: MonitoringAgent,
    ) -> None:
        super().__init__(agent_id, "orchestration_agent", redis_client)
        self._vision = vision_agent
        self._temporal = temporal_agent
        self._anomaly = anomaly_agent
        self._monitoring = monitoring_agent

        # Wire cross-agent references
        self._vision.set_anomaly_agent(anomaly_agent)
        self._temporal.set_anomaly_agent(anomaly_agent)

    @property
    def _sub_agents(self) -> list[BaseAgent]:
        return [self._vision, self._temporal, self._anomaly, self._monitoring]

    async def start(self) -> None:
        logger.info("orchestration_agent.start — launching %d sub-agents", len(self._sub_agents))
        await asyncio.gather(*[agent.start() for agent in self._sub_agents])
        await self._update_state(AgentState.IDLE)

    async def stop(self) -> None:
        logger.info("orchestration_agent.stop — shutting down %d sub-agents", len(self._sub_agents))
        await asyncio.gather(*[agent.stop() for agent in self._sub_agents])
        await self._update_state(AgentState.IDLE)

    async def route_event(
        self,
        event_type: str,
        event_data: dict[str, Any],
        session_id: str,
    ) -> dict[str, Any]:
        """
        Route an event to the appropriate agent.
        Returns routing metadata including whether the task was queued.
        """
        agent_key = _EVENT_AGENT_MAP.get(event_type)
        agent: BaseAgent | None = {
            "vision": self._vision,
            "temporal": self._temporal,
            "anomaly": self._anomaly,
            "monitoring": self._monitoring,
        }.get(agent_key or "")

        if agent is None:
            logger.warning(
                "orchestration_agent.route unknown event_type=%s", event_type
            )
            return {"routed": False, "reason": f"No agent registered for event_type={event_type}"}

        task = AgentTask(
            agent_type=agent.agent_type,
            trigger=event_type,
            priority=self._priority_for_event(event_type),
            input_data={"session_id": session_id, **event_data},
        )

        queued = await agent.submit_task(task)
        logger.debug(
            "orchestration_agent.route event=%s agent=%s queued=%s task_id=%s",
            event_type,
            agent.agent_type,
            queued,
            task.task_id,
        )
        return {
            "routed": queued,
            "agent": agent.agent_type,
            "task_id": task.task_id,
        }

    async def get_cluster_status(self) -> dict[str, Any]:
        agents_status = [agent.get_status() for agent in self._sub_agents]
        healthy = sum(1 for s in agents_status if s["state"] != AgentState.ERROR.value)
        return {
            "orchestrator": self.get_status(),
            "agents": agents_status,
            "cluster_health": {
                "total": len(agents_status),
                "healthy": healthy,
                "degraded": len(agents_status) - healthy,
            },
        }

    async def emergency_shutdown(self, reason: str) -> None:
        logger.critical("orchestration_agent.EMERGENCY_SHUTDOWN reason=%s", reason)
        await self._update_state(AgentState.ERROR)
        await self.stop()

    async def execute(self, task: AgentTask) -> AgentTask:
        # Orchestration agent delegates; it has no own business logic
        task.add_trace("orchestration_agent.execute noop")
        return task

    @staticmethod
    def _priority_for_event(event_type: str) -> int:
        return {
            "critical_alert": 1,
            "vision_result": 3,
            "temporal_anomaly": 2,
            "temporal_metrics": 5,
            "system_event": 8,
        }.get(event_type, 5)
