"""
BaseAgent — foundation for all ArgusLens agents.
Provides: task queue, async state machine, structured logging, metrics hooks.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any

import redis.asyncio as aioredis

from intelligence.types import AgentState, AgentTask

logger = logging.getLogger(__name__)


class BaseAgent:
    """
    All agents inherit from this class.
    Subclasses implement `execute(task) -> AgentTask`.
    """

    def __init__(
        self,
        agent_id: str,
        agent_type: str,
        redis_client: aioredis.Redis,
    ) -> None:
        self.agent_id = agent_id
        self.agent_type = agent_type
        self.state: AgentState = AgentState.IDLE
        self.task_queue: asyncio.Queue[AgentTask] = asyncio.Queue(maxsize=100)
        self._running = False
        self._current_task: AgentTask | None = None
        self._redis = redis_client
        self._loop_task: asyncio.Task | None = None
        self._stats: dict[str, int] = {
            "tasks_processed": 0,
            "tasks_failed": 0,
            "tasks_skipped": 0,
        }

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._loop_task = asyncio.create_task(
            self._task_loop(), name=f"agent-{self.agent_id}"
        )
        await self._update_state(AgentState.IDLE)
        logger.info("agent.start id=%s type=%s", self.agent_id, self.agent_type)

    async def stop(self) -> None:
        self._running = False
        if self._loop_task:
            self._loop_task.cancel()
            try:
                await self._loop_task
            except asyncio.CancelledError:
                pass
        await self._update_state(AgentState.IDLE)
        logger.info(
            "agent.stop id=%s processed=%d failed=%d",
            self.agent_id,
            self._stats["tasks_processed"],
            self._stats["tasks_failed"],
        )

    async def submit_task(self, task: AgentTask) -> bool:
        """Enqueue a task. Returns False if queue is full."""
        try:
            self.task_queue.put_nowait(task)
            logger.debug(
                "agent.submit id=%s task_id=%s priority=%d qsize=%d",
                self.agent_id,
                task.task_id,
                task.priority,
                self.task_queue.qsize(),
            )
            return True
        except asyncio.QueueFull:
            self._stats["tasks_skipped"] += 1
            logger.warning(
                "agent.queue_full id=%s type=%s — task_id=%s dropped",
                self.agent_id,
                self.agent_type,
                task.task_id,
            )
            return False

    # ------------------------------------------------------------------
    # Internal loop
    # ------------------------------------------------------------------

    async def _task_loop(self) -> None:
        logger.debug("agent.loop_start id=%s", self.agent_id)
        while self._running:
            try:
                task = await asyncio.wait_for(self.task_queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break

            self._current_task = task
            task.state = AgentState.ANALYZING
            task.started_at = datetime.utcnow()
            await self._update_state(AgentState.ANALYZING)
            task.add_trace(f"agent.{self.agent_type}.picked_up")

            try:
                completed = await self.execute(task)
                completed.state = AgentState.IDLE
                completed.completed_at = datetime.utcnow()
                self._stats["tasks_processed"] += 1
                logger.info(
                    "agent.task_done id=%s task_id=%s duration_ms=%.1f",
                    self.agent_id,
                    task.task_id,
                    (
                        (completed.completed_at - completed.started_at).total_seconds() * 1000
                        if completed.started_at
                        else 0
                    ),
                )
            except Exception as exc:
                task.state = AgentState.ERROR
                task.error = str(exc)
                task.completed_at = datetime.utcnow()
                self._stats["tasks_failed"] += 1
                logger.error(
                    "agent.task_error id=%s task_id=%s error=%s",
                    self.agent_id,
                    task.task_id,
                    exc,
                    exc_info=True,
                )
            finally:
                self._current_task = None
                self.task_queue.task_done()
                await self._update_state(AgentState.IDLE)

    # ------------------------------------------------------------------
    # Subclass interface
    # ------------------------------------------------------------------

    async def execute(self, task: AgentTask) -> AgentTask:
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement execute()"
        )

    # ------------------------------------------------------------------
    # Status & state
    # ------------------------------------------------------------------

    def get_status(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "agent_type": self.agent_type,
            "state": self.state.value,
            "queue_depth": self.task_queue.qsize(),
            "current_task": self._current_task.task_id if self._current_task else None,
            "stats": dict(self._stats),
        }

    async def _update_state(self, new_state: AgentState) -> None:
        old = self.state
        self.state = new_state
        if old != new_state:
            logger.debug(
                "agent.state_change id=%s %s → %s",
                self.agent_id,
                old.value,
                new_state.value,
            )
            # Redis state publish for external monitoring
            try:
                await self._redis.setex(
                    f"argus:agent:{self.agent_id}:state",
                    300,
                    new_state.value,
                )
            except Exception:
                pass
