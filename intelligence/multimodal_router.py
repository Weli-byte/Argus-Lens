"""
MultimodalRouter — primary entry point for the intelligence layer.
Every external analysis request flows through here.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from intelligence.context_manager import IntelligenceContextManager
from intelligence.insight_generator import InsightGenerator
from intelligence.reasoning_engine import ReasoningEngine
from intelligence.recommendation_engine import RecommendationEngine
from intelligence.types import (
    AIInsight,
    InsightSeverity,
    MemoryEntry,
    MemoryType,
    ReasoningContext,
    ReasoningMode,
)
from memory.retrieval_manager import RetrievalManager
from memory.short_term_memory import ShortTermMemory

logger = logging.getLogger(__name__)

_CONSOLIDATION_SEVERITY = {InsightSeverity.CRITICAL, InsightSeverity.EMERGENCY}


class MultimodalRouter:
    """
    Orchestrates the full multimodal intelligence pipeline:
    gather context → reason → recommend → store → broadcast.
    """

    def __init__(
        self,
        context_manager: IntelligenceContextManager,
        reasoning_engine: ReasoningEngine,
        recommendation_engine: RecommendationEngine,
        retrieval_manager: RetrievalManager,
        short_term_memory: ShortTermMemory,
        ws_broadcaster: Any | None = None,
    ) -> None:
        self._ctx_mgr = context_manager
        self._reasoner = reasoning_engine
        self._recommender = recommendation_engine
        self._retrieval = retrieval_manager
        self._stm = short_term_memory
        self._broadcaster = ws_broadcaster  # injected after ws layer starts

    def set_broadcaster(self, broadcaster: Any) -> None:
        self._broadcaster = broadcaster

    async def process(
        self,
        session_id: str,
        vision_result: dict[str, Any] | None = None,
        temporal_metrics: dict[str, Any] | None = None,
        user_query: str | None = None,
        force_mode: ReasoningMode | None = None,
    ) -> dict[str, Any]:
        """
        Full pipeline execution.
        Returns: {insight, recommendations, trace_id, processing_ms}
        """
        t0 = time.monotonic()

        # 1. Build context
        mode = force_mode or self._infer_mode(vision_result, temporal_metrics)
        context = await self._ctx_mgr.build_context(
            session_id=session_id,
            vision_data=vision_result,
            temporal_data=temporal_metrics,
            reasoning_mode=mode,
        )

        # 2. Reason
        insight, trace = await self._reasoner.reason(context, mode=context.reasoning_mode)

        # 3. Recommendations
        recommendations = await self._recommender.generate_recommendations(
            insight=insight, context=context
        )

        # 4. Store to STM
        stm_entry = self._insight_to_memory(insight, context)
        await self._stm.store(session_id, stm_entry)

        # 5. Consolidate high-severity insights to LTM
        if insight.severity in _CONSOLIDATION_SEVERITY:
            await self._retrieval.consolidate_to_ltm(session_id, stm_entry)

        # 6. Broadcast via WebSocket
        if self._broadcaster is not None:
            try:
                await self._broadcaster.broadcast_insight(insight, session_id)
            except Exception as exc:
                logger.warning("multimodal_router.broadcast failed: %s", exc)

        processing_ms = round((time.monotonic() - t0) * 1000, 2)
        logger.info(
            "multimodal_router.process session=%s mode=%s severity=%s "
            "confidence=%.3f processing_ms=%.1f",
            session_id,
            context.reasoning_mode.value,
            insight.severity.value,
            insight.confidence,
            processing_ms,
        )

        return {
            "insight": insight.to_dict(),
            "recommendations": recommendations,
            "trace_id": trace.trace_id,
            "context_id": context.context_id,
            "processing_ms": processing_ms,
        }

    async def process_batch(
        self, requests: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Parallel processing of multiple requests."""
        tasks = [
            self.process(
                session_id=r.get("session_id", "batch"),
                vision_result=r.get("vision_result"),
                temporal_metrics=r.get("temporal_metrics"),
                user_query=r.get("user_query"),
                force_mode=ReasoningMode(r["mode"]) if r.get("mode") else None,
            )
            for r in requests
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        output: list[dict[str, Any]] = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error("multimodal_router.batch item=%d error: %s", i, result)
                output.append({"error": str(result), "index": i})
            else:
                output.append(result)
        return output

    async def health_check(self) -> dict[str, Any]:
        stm_summary = await self._stm.get_session_summary("health_check")
        return {
            "status": "healthy",
            "components": {
                "context_manager": "ok",
                "reasoning_engine": "ok",
                "recommendation_engine": "ok",
                "short_term_memory": stm_summary,
                "broadcaster": "ok" if self._broadcaster else "not_connected",
            },
        }

    @staticmethod
    def _infer_mode(
        vision_result: dict | None,
        temporal_metrics: dict | None,
    ) -> ReasoningMode:
        has_vision = bool(vision_result)
        has_temporal = bool(temporal_metrics)
        if has_vision and has_temporal:
            return ReasoningMode.CONTEXTUAL
        if has_temporal:
            return ReasoningMode.PREDICTIVE
        return ReasoningMode.REACTIVE

    @staticmethod
    def _insight_to_memory(insight: AIInsight, context: ReasoningContext) -> MemoryEntry:
        importance = min(1.0, insight.confidence * (1 + {
            InsightSeverity.EMERGENCY: 0.5,
            InsightSeverity.CRITICAL: 0.3,
            InsightSeverity.WARNING: 0.1,
            InsightSeverity.NOTICE: 0.0,
            InsightSeverity.INFO: -0.1,
        }.get(insight.severity, 0.0)))

        return MemoryEntry(
            memory_type=MemoryType.EPISODIC,
            content=f"{insight.title}: {insight.summary}",
            importance_score=round(importance, 3),
            tags=[insight.severity.value, context.reasoning_mode.value],
            source="multimodal_router",
            metadata={
                "insight_id": insight.insight_id,
                "severity": insight.severity.value,
                "confidence": insight.confidence,
            },
        )
