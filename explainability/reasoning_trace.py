"""
ReasoningTraceLogger — persists every reasoning step to Redis + DB.
Answers: "why did the system make this decision?"
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from typing import Any

import redis.asyncio as aioredis
from sqlalchemy.ext.asyncio import AsyncSession

from intelligence.types import AIInsight, ReasoningTrace

logger = logging.getLogger(__name__)

_TRACE_TTL = 86400  # 24 hours in Redis
_TRACE_KEY_PREFIX = "argus:trace"


class ReasoningTraceLogger:
    """
    Full audit trail for reasoning pipeline executions.
    Redis: fast recent retrieval.
    DB (optional): long-term audit persistence.
    """

    def __init__(
        self,
        redis_client: aioredis.Redis,
        db_session: AsyncSession | None = None,
    ) -> None:
        self._redis = redis_client
        self._db = db_session

    async def start_trace(
        self, context_id: str, session_id: str
    ) -> str:
        trace_id = str(uuid.uuid4())
        meta = {
            "trace_id": trace_id,
            "context_id": context_id,
            "session_id": session_id,
            "started_at": datetime.utcnow().isoformat(),
            "steps": [],
            "memory_lookups": 0,
            "correlations_found": 0,
        }
        await self._redis.setex(
            f"{_TRACE_KEY_PREFIX}:{trace_id}",
            _TRACE_TTL,
            json.dumps(meta),
        )
        # Index by session
        await self._redis.lpush(f"{_TRACE_KEY_PREFIX}:session:{session_id}", trace_id)
        await self._redis.expire(f"{_TRACE_KEY_PREFIX}:session:{session_id}", _TRACE_TTL)
        logger.debug(
            "trace.start trace_id=%s context_id=%s session=%s",
            trace_id,
            context_id,
            session_id,
        )
        return trace_id

    async def log_step(
        self,
        trace_id: str,
        step_name: str,
        input_data: dict[str, Any],
        output_data: dict[str, Any],
        duration_ms: float,
        success: bool,
    ) -> None:
        step = {
            "step": step_name,
            "duration_ms": round(duration_ms, 2),
            "success": success,
            "ts": datetime.utcnow().isoformat(),
            "input_summary": str(input_data)[:200],
            "output_summary": str(output_data)[:200],
        }
        await self._append_to_trace(trace_id, "steps", step)
        logger.debug(
            "trace.step trace_id=%s step=%s ok=%s ms=%.1f",
            trace_id,
            step_name,
            success,
            duration_ms,
        )

    async def log_memory_lookup(
        self,
        trace_id: str,
        query: str,
        results_count: int,
        top_similarity: float,
    ) -> None:
        step = {
            "step": "memory_lookup",
            "query": query[:100],
            "results": results_count,
            "top_similarity": round(top_similarity, 4),
            "ts": datetime.utcnow().isoformat(),
        }
        await self._append_to_trace(trace_id, "steps", step)
        await self._increment_counter(trace_id, "memory_lookups")

    async def log_correlation(
        self,
        trace_id: str,
        event_a: str,
        event_b: str,
        strength: float,
    ) -> None:
        step = {
            "step": "correlation",
            "event_a": event_a,
            "event_b": event_b,
            "strength": round(strength, 4),
            "ts": datetime.utcnow().isoformat(),
        }
        await self._append_to_trace(trace_id, "steps", step)
        await self._increment_counter(trace_id, "correlations_found")

    async def finish_trace(
        self,
        trace_id: str,
        final_insight: AIInsight,
        total_duration_ms: float,
    ) -> ReasoningTrace:
        raw = await self._redis.get(f"{_TRACE_KEY_PREFIX}:{trace_id}")
        if not raw:
            logger.warning("trace.finish not found trace_id=%s", trace_id)
            return ReasoningTrace(trace_id=trace_id)

        meta: dict[str, Any] = json.loads(raw)
        meta["total_duration_ms"] = round(total_duration_ms, 2)
        meta["finished_at"] = datetime.utcnow().isoformat()
        meta["final_insight_id"] = final_insight.insight_id
        meta["final_severity"] = final_insight.severity.value

        await self._redis.setex(
            f"{_TRACE_KEY_PREFIX}:{trace_id}", _TRACE_TTL, json.dumps(meta)
        )

        trace = ReasoningTrace(
            trace_id=trace_id,
            context_id=meta.get("context_id", ""),
            steps=meta.get("steps", []),
            total_duration_ms=total_duration_ms,
            memory_lookups=meta.get("memory_lookups", 0),
            correlations_found=meta.get("correlations_found", 0),
            final_insight=final_insight,
        )
        logger.info(
            "trace.finish trace_id=%s duration_ms=%.1f steps=%d severity=%s",
            trace_id,
            total_duration_ms,
            len(trace.steps),
            final_insight.severity.value,
        )
        return trace

    async def get_trace(self, trace_id: str) -> ReasoningTrace | None:
        raw = await self._redis.get(f"{_TRACE_KEY_PREFIX}:{trace_id}")
        if not raw:
            return None
        meta: dict[str, Any] = json.loads(raw)
        return ReasoningTrace(
            trace_id=trace_id,
            context_id=meta.get("context_id", ""),
            steps=meta.get("steps", []),
            total_duration_ms=meta.get("total_duration_ms", 0.0),
            memory_lookups=meta.get("memory_lookups", 0),
            correlations_found=meta.get("correlations_found", 0),
        )

    async def get_recent_traces(
        self, session_id: str, limit: int = 10
    ) -> list[ReasoningTrace]:
        raw_ids: list[bytes] = await self._redis.lrange(
            f"{_TRACE_KEY_PREFIX}:session:{session_id}", 0, limit - 1
        )
        traces: list[ReasoningTrace] = []
        for rid in raw_ids:
            trace = await self.get_trace(rid.decode())
            if trace:
                traces.append(trace)
        return traces

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _append_to_trace(
        self, trace_id: str, field: str, item: dict[str, Any]
    ) -> None:
        key = f"{_TRACE_KEY_PREFIX}:{trace_id}"
        raw = await self._redis.get(key)
        if not raw:
            return
        meta: dict[str, Any] = json.loads(raw)
        meta.setdefault(field, []).append(item)
        await self._redis.setex(key, _TRACE_TTL, json.dumps(meta))

    async def _increment_counter(self, trace_id: str, field: str) -> None:
        key = f"{_TRACE_KEY_PREFIX}:{trace_id}"
        raw = await self._redis.get(key)
        if not raw:
            return
        meta: dict[str, Any] = json.loads(raw)
        meta[field] = meta.get(field, 0) + 1
        await self._redis.setex(key, _TRACE_TTL, json.dumps(meta))
