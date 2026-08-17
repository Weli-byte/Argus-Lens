"""
IntelligenceContextManager — assembles a ReasoningContext from raw
multimodal inputs (vision, temporal, telemetry) and enriches it with
memory retrieval before reasoning begins.
"""

from __future__ import annotations

import logging
from typing import Any

from intelligence.types import ReasoningContext, ReasoningMode
from memory.retrieval_manager import RetrievalManager

logger = logging.getLogger(__name__)


class IntelligenceContextManager:
    """
    Builds and enriches ReasoningContext objects.
    Called at the entry point of every reasoning pipeline execution.
    """

    def __init__(self, retrieval_manager: RetrievalManager) -> None:
        self._retrieval = retrieval_manager

    async def build_context(
        self,
        session_id: str,
        vision_data: dict[str, Any] | None = None,
        temporal_data: dict[str, Any] | None = None,
        system_telemetry: dict[str, Any] | None = None,
        reasoning_mode: ReasoningMode = ReasoningMode.REACTIVE,
        metadata: dict[str, Any] | None = None,
    ) -> ReasoningContext:
        """
        Create a new ReasoningContext and optionally enrich it with memory.
        """
        ctx = ReasoningContext(
            session_id=session_id,
            vision_data=vision_data or {},
            temporal_data=temporal_data or {},
            system_telemetry=system_telemetry or {},
            reasoning_mode=reasoning_mode,
            metadata=metadata or {},
        )
        ctx.add_trace(f"context_manager.build mode={reasoning_mode.value}")

        if reasoning_mode in (ReasoningMode.CONTEXTUAL, ReasoningMode.PREDICTIVE, ReasoningMode.AGENTIC):
            await self._enrich_with_memory(ctx)

        logger.info(
            "ctx_manager.built session=%s context_id=%s mode=%s",
            session_id,
            ctx.context_id,
            reasoning_mode.value,
        )
        return ctx

    async def _enrich_with_memory(self, ctx: ReasoningContext) -> None:
        """Pull relevant memories into ctx.memory_context."""
        query = self._build_memory_query(ctx)
        ctx.add_trace(f"context_manager.memory_query len={len(query)}")
        await self._retrieval.retrieve_for_context(ctx, query=query, top_k=8)
        ctx.add_trace(f"context_manager.memory_loaded count={len(ctx.memory_context)}")

    @staticmethod
    def _build_memory_query(ctx: ReasoningContext) -> str:
        """Construct a natural-language query from context data for memory retrieval."""
        parts: list[str] = []

        if ctx.vision_data:
            detections = ctx.vision_data.get("detections", [])
            if detections:
                labels = [d.get("label", "") for d in detections[:3]]
                parts.append(f"vision detections: {', '.join(labels)}")

        if ctx.temporal_data:
            fatigue = ctx.temporal_data.get("fatigue_score")
            if fatigue is not None:
                parts.append(f"fatigue level {fatigue:.2f}")
            risk = ctx.temporal_data.get("risk_level")
            if risk:
                parts.append(f"risk {risk}")

        if ctx.system_telemetry:
            gpu_util = ctx.system_telemetry.get("avg_gpu_utilization")
            if gpu_util is not None:
                parts.append(f"GPU utilization {gpu_util:.0f}%")

        return " | ".join(parts) if parts else "system monitoring event"

    def select_reasoning_mode(
        self,
        has_vision: bool,
        has_temporal: bool,
        anomaly_count: int,
        memory_available: bool,
    ) -> ReasoningMode:
        """
        Heuristic mode selection based on available inputs.
        Caller may override with explicit mode.
        """
        if anomaly_count >= 3:
            return ReasoningMode.AGENTIC
        if memory_available and (has_vision or has_temporal):
            return ReasoningMode.CONTEXTUAL
        if has_temporal and not has_vision:
            return ReasoningMode.PREDICTIVE
        return ReasoningMode.REACTIVE
