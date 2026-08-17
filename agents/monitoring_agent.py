"""
MonitoringAgent — periodic system-health sentinel.
Runs an independent asyncio loop, not the task-queue loop.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any

import redis.asyncio as aioredis

from agents.base_agent import BaseAgent
from intelligence.multimodal_router import MultimodalRouter
from intelligence.types import AgentState, AgentTask

logger = logging.getLogger(__name__)

_GPU_VRAM_WARN = 0.85
_QUEUE_WARN = 0.80
_MODEL_HEALTH_WARN = 0.70
_GHOST_CONN_WARN = 10


class MonitoringAgent(BaseAgent):
    """
    Polls system state every `check_interval` seconds.
    Generates proactive WARNING/CRITICAL insights for operators.
    """

    def __init__(
        self,
        agent_id: str,
        redis_client: aioredis.Redis,
        multimodal_router: MultimodalRouter,
        check_interval: int = 30,
    ) -> None:
        super().__init__(agent_id, "monitoring_agent", redis_client)
        self._router = multimodal_router
        self._interval = check_interval
        self._monitor_task: asyncio.Task | None = None

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._monitor_task = asyncio.create_task(
            self._monitoring_loop(), name=f"monitor-{self.agent_id}"
        )
        await self._update_state(AgentState.IDLE)
        logger.info("monitoring_agent.start id=%s interval=%ds", self.agent_id, self._interval)

    async def stop(self) -> None:
        self._running = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        await self._update_state(AgentState.IDLE)
        logger.info("monitoring_agent.stop id=%s", self.agent_id)

    async def _monitoring_loop(self) -> None:
        while self._running:
            try:
                task = AgentTask(
                    agent_type="monitoring_agent",
                    trigger="periodic_check",
                    priority=8,
                    input_data={"triggered_at": datetime.utcnow().isoformat()},
                )
                await self.execute(task)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("monitoring_agent.loop_error: %s", exc, exc_info=True)
            await asyncio.sleep(self._interval)

    async def execute(self, task: AgentTask) -> AgentTask:
        task.add_trace("monitoring_agent.execute start")
        await self._update_state(AgentState.ANALYZING)

        issues: list[dict[str, Any]] = []
        telemetry: dict[str, Any] = {}

        # 1. GPU VRAM
        gpu_data = await self._get_redis_json("argus:system:gpu")
        if gpu_data:
            vram_pct = gpu_data.get("vram_utilization", 0.0)
            telemetry["avg_gpu_utilization"] = vram_pct
            if vram_pct > _GPU_VRAM_WARN:
                issues.append({
                    "type": "gpu_vram",
                    "value": vram_pct,
                    "severity": "WARNING",
                    "message": f"GPU VRAM at {vram_pct:.0%} — risk of OOM",
                })

        # 2. Inference queue
        queue_data = await self._get_redis_json("argus:system:queue")
        if queue_data:
            queue_pct = queue_data.get("utilization", 0.0)
            telemetry["queue_utilization"] = queue_pct
            if queue_pct > _QUEUE_WARN:
                issues.append({
                    "type": "inference_queue",
                    "value": queue_pct,
                    "severity": "WARNING",
                    "message": f"Inference queue at {queue_pct:.0%}",
                })

        # 3. Worker health
        worker_data = await self._get_redis_json("argus:system:workers")
        if worker_data:
            dead = worker_data.get("dead_workers", 0)
            telemetry["dead_workers"] = dead
            if dead > 0:
                issues.append({
                    "type": "dead_workers",
                    "value": dead,
                    "severity": "CRITICAL",
                    "message": f"{dead} worker(s) unresponsive",
                })

        # 4. Model health
        model_data = await self._get_redis_json("argus:system:models")
        if model_data:
            health = model_data.get("avg_health_score", 1.0)
            if health < _MODEL_HEALTH_WARN:
                issues.append({
                    "type": "model_health",
                    "value": health,
                    "severity": "WARNING",
                    "message": f"Average model health score {health:.2f} below threshold",
                })

        task.output_data = {
            "issues": issues,
            "telemetry": telemetry,
            "checked_at": datetime.utcnow().isoformat(),
        }

        if issues:
            await self._update_state(AgentState.ACTING)
            await self._router.process(
                session_id="system_monitoring",
                temporal_metrics={},
                vision_result={"system_issues": issues},
            )
            task.add_trace(f"monitoring_agent.issues_reported count={len(issues)}")
            logger.warning(
                "monitoring_agent.issues count=%d %s",
                len(issues),
                [i["type"] for i in issues],
            )
        else:
            task.add_trace("monitoring_agent.system_healthy")
            logger.debug("monitoring_agent.healthy")

        await self._update_state(AgentState.IDLE)
        return task

    async def _get_redis_json(self, key: str) -> dict[str, Any] | None:
        try:
            import json
            raw = await self._redis.get(key)
            return json.loads(raw) if raw else None
        except Exception:
            return None
