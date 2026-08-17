"""
SemanticCorrelator — measures semantic similarity between events,
builds context embeddings from multimodal data, and detects semantic drift.
"""

from __future__ import annotations

import logging
import math
from typing import Any, Callable

from intelligence.types import (
    CorrelationResult,
    CorrelationStrength,
    ReasoningContext,
)
from memory.long_term_memory import LongTermMemory

logger = logging.getLogger(__name__)


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    mag_a = math.sqrt(sum(x ** 2 for x in a))
    mag_b = math.sqrt(sum(x ** 2 for x in b))
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


def _centroid(embeddings: list[list[float]]) -> list[float]:
    if not embeddings:
        return []
    dim = len(embeddings[0])
    result = [0.0] * dim
    for emb in embeddings:
        for i, v in enumerate(emb):
            result[i] += v
    n = len(embeddings)
    return [v / n for v in result]


def _strength_from_score(score: float) -> CorrelationStrength:
    if score >= 0.9:
        return CorrelationStrength.CAUSAL
    if score >= 0.7:
        return CorrelationStrength.STRONG
    if score >= 0.5:
        return CorrelationStrength.MODERATE
    return CorrelationStrength.WEAK


class SemanticCorrelator:
    """
    Semantic similarity engine.
    Embeds context → searches LTM → scores event pairs → measures drift.
    """

    def __init__(
        self,
        embedder: Callable[[str], Any],
        long_term_memory: LongTermMemory,
    ) -> None:
        self._embed = embedder
        self._ltm = long_term_memory

    async def find_semantic_patterns(
        self,
        current_context: ReasoningContext,
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        """
        Embed the current context → semantic search in LTM.
        Returns structured pattern matches with similarity scores.
        """
        embedding = await self.build_context_embedding(current_context)
        if not embedding:
            return []

        results = await self._ltm.semantic_search(
            query=self._context_to_text(current_context),
            top_k=top_k,
            min_similarity=0.5,
        )
        patterns: list[dict[str, Any]] = []
        for entry, score in results:
            patterns.append(
                {
                    "memory_id": entry.memory_id,
                    "content": entry.content,
                    "similarity": round(score, 4),
                    "memory_type": entry.memory_type.value,
                    "importance": entry.importance_score,
                    "tags": entry.tags,
                    "created_at": entry.created_at.isoformat(),
                }
            )

        current_context.add_trace(
            f"semantic_correlator.patterns found={len(patterns)}"
        )
        logger.debug(
            "find_semantic_patterns context_id=%s results=%d",
            current_context.context_id,
            len(patterns),
        )
        return patterns

    async def correlate_events(
        self,
        event_a: dict[str, Any],
        event_b: dict[str, Any],
        time_window_seconds: float = 300,
    ) -> CorrelationResult:
        """
        Combine semantic similarity + temporal proximity into a single score.
        temporal_proximity = 1 - |lag| / time_window (floored at 0)
        combined = 0.6 * semantic + 0.4 * temporal_proximity
        """
        text_a = self._event_to_text(event_a)
        text_b = self._event_to_text(event_b)

        emb_a = await self._safe_embed(text_a)
        emb_b = await self._safe_embed(text_b)

        semantic_sim = _cosine_similarity(emb_a, emb_b)

        lag_s = abs(event_a.get("timestamp", 0) - event_b.get("timestamp", 0))
        temporal_proximity = max(0.0, 1.0 - lag_s / time_window_seconds)

        combined = 0.6 * semantic_sim + 0.4 * temporal_proximity

        explanation = (
            f"Semantic similarity: {semantic_sim:.3f}. "
            f"Temporal proximity (lag {lag_s:.1f}s): {temporal_proximity:.3f}. "
            f"Combined correlation score: {combined:.3f}."
        )

        result = CorrelationResult(
            event_a=event_a,
            event_b=event_b,
            strength=_strength_from_score(combined),
            score=round(combined, 4),
            lag_seconds=round(lag_s, 2),
            explanation=explanation,
        )
        logger.debug(
            "correlate_events semantic=%.3f temporal=%.3f combined=%.3f strength=%s",
            semantic_sim,
            temporal_proximity,
            combined,
            result.strength.value,
        )
        return result

    async def build_context_embedding(
        self, context: ReasoningContext
    ) -> list[float]:
        """
        Flatten multimodal context fields into a single string → embed.
        """
        text = self._context_to_text(context)
        return await self._safe_embed(text)

    async def compute_semantic_drift(
        self,
        recent_embeddings: list[list[float]],
        baseline_embeddings: list[list[float]],
    ) -> float:
        """
        1 - cosine(baseline_centroid, recent_centroid).
        0.0 = no drift, 1.0 = completely different.
        """
        if not recent_embeddings or not baseline_embeddings:
            return 0.0
        recent_c = _centroid(recent_embeddings)
        baseline_c = _centroid(baseline_embeddings)
        sim = _cosine_similarity(recent_c, baseline_c)
        drift = 1.0 - sim
        logger.debug(
            "compute_semantic_drift recent=%d baseline=%d drift=%.4f",
            len(recent_embeddings),
            len(baseline_embeddings),
            drift,
        )
        return round(drift, 4)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _safe_embed(self, text: str) -> list[float]:
        try:
            result = await self._embed(text)
            return result if isinstance(result, list) else result.tolist()
        except Exception as exc:
            logger.warning("semantic_correlator.embed failed: %s", exc)
            return []

    @staticmethod
    def _context_to_text(ctx: ReasoningContext) -> str:
        parts: list[str] = [f"session:{ctx.session_id}"]

        if ctx.vision_data:
            dets = ctx.vision_data.get("detections", [])
            labels = " ".join(d.get("label", "") for d in dets[:5])
            if labels:
                parts.append(f"vision objects detected: {labels}")

        if ctx.temporal_data:
            for k in ("fatigue_score", "focus_score", "cognitive_load", "risk_level"):
                v = ctx.temporal_data.get(k)
                if v is not None:
                    parts.append(f"{k}={v}")

        for mem in ctx.memory_context[:3]:
            c = mem.get("content", "")
            if c:
                parts.append(c[:100])

        return " | ".join(parts)

    @staticmethod
    def _event_to_text(event: dict[str, Any]) -> str:
        return " ".join(
            f"{k}={v}"
            for k, v in event.items()
            if k not in ("timestamp", "raw_data") and v is not None
        )
