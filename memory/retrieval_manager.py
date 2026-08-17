"""
RetrievalManager — coordinates STM (Redis) and LTM (pgvector) lookups
into a unified, relevance-ranked result set.

Strategy:
  1. Query STM for recent entries (fast, in-memory)
  2. If STM results < min_results or query is semantic, hit LTM
  3. Merge, deduplicate, re-rank by (recency × importance × similarity)
  4. Load top-k into ContextWindow
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from intelligence.types import MemoryEntry, MemoryType, ReasoningContext
from memory.context_window import ContextWindow
from memory.long_term_memory import LongTermMemory
from memory.short_term_memory import ShortTermMemory

logger = logging.getLogger(__name__)

_RECENCY_HALF_LIFE_SECONDS = 300.0  # 5 min — STM entries decay in importance


class RetrievalManager:
    """
    Unified retrieval interface over STM + LTM.
    Instantiate once per request; ContextWindow is ephemeral.
    """

    def __init__(
        self,
        stm: ShortTermMemory,
        ltm: LongTermMemory,
        context_window_tokens: int = 4096,
    ) -> None:
        self._stm = stm
        self._ltm = ltm
        self._ctx = ContextWindow(max_tokens=context_window_tokens)

    @property
    def context_window(self) -> ContextWindow:
        return self._ctx

    # ------------------------------------------------------------------
    # Primary retrieval
    # ------------------------------------------------------------------

    async def retrieve_for_context(
        self,
        ctx: ReasoningContext,
        query: str,
        top_k: int = 10,
        min_similarity: float = 0.5,
    ) -> list[MemoryEntry]:
        """
        Full retrieval pipeline for a reasoning context.
        Populates `ctx.memory_context` and the internal ContextWindow.
        Returns the merged, ranked entry list.
        """
        ctx.add_trace(f"retrieval.start query_len={len(query)} top_k={top_k}")

        stm_entries = await self._stm.retrieve_recent(
            ctx.session_id, limit=top_k * 2
        )
        ctx.add_trace(f"retrieval.stm found={len(stm_entries)}")

        ltm_results: list[tuple[MemoryEntry, float]] = []
        if len(stm_entries) < top_k or query:
            ltm_results = await self._ltm.semantic_search(
                query=query,
                top_k=top_k,
                min_similarity=min_similarity,
                session_id=ctx.session_id,
            )
            ctx.add_trace(f"retrieval.ltm found={len(ltm_results)}")

        merged = self._merge_and_rank(stm_entries, ltm_results, top_k=top_k)
        ctx.add_trace(f"retrieval.merged total={len(merged)}")

        # Load into context window and populate ctx.memory_context
        self._ctx.clear()
        for entry, score in merged:
            self._ctx.add(entry, relevance_score=score)

        ctx.memory_context = [e.to_dict() for e, _ in merged]
        return [e for e, _ in merged]

    async def retrieve_by_type(
        self,
        session_id: str,
        memory_type: MemoryType,
        limit: int = 20,
    ) -> list[MemoryEntry]:
        return await self._stm.retrieve_recent(
            session_id, limit=limit, memory_type=memory_type
        )

    async def retrieve_by_tags(
        self,
        session_id: str,
        tags: list[str],
        limit: int = 20,
    ) -> list[MemoryEntry]:
        return await self._stm.retrieve_by_tags(session_id, tags, limit=limit)

    async def store_to_stm(self, session_id: str, entry: MemoryEntry) -> None:
        await self._stm.store(session_id, entry)
        logger.debug(
            "retrieval.store_stm session=%s memory_id=%s", session_id, entry.memory_id
        )

    async def consolidate_to_ltm(self, session_id: str, entry: MemoryEntry) -> bool:
        """Attempt LTM consolidation. Returns True if stored."""
        stored = await self._ltm.consolidate(entry, session_id)
        if stored:
            logger.info(
                "retrieval.ltm_consolidated session=%s memory_id=%s importance=%.3f",
                session_id,
                entry.memory_id,
                entry.importance_score,
            )
        return stored

    async def get_memory_summary(self, session_id: str) -> dict[str, Any]:
        stm_summary = await self._stm.get_session_summary(session_id)
        ltm_stats = await self._ltm.get_statistics()
        return {
            "stm": stm_summary,
            "ltm": ltm_stats,
            "context_window": self._ctx.snapshot(),
        }

    # ------------------------------------------------------------------
    # Merge & rank
    # ------------------------------------------------------------------

    def _merge_and_rank(
        self,
        stm_entries: list[MemoryEntry],
        ltm_results: list[tuple[MemoryEntry, float]],
        top_k: int,
    ) -> list[tuple[MemoryEntry, float]]:
        """
        Combine STM (scored by recency) and LTM (scored by similarity).
        Deduplicate by memory_id, keep higher-scored version.
        """
        scored: dict[str, tuple[MemoryEntry, float]] = {}

        now = datetime.utcnow().timestamp()

        for entry in stm_entries:
            age_s = max(0.0, now - entry.created_at.timestamp())
            recency = 2 ** (-age_s / _RECENCY_HALF_LIFE_SECONDS)
            score = entry.importance_score * recency
            scored[entry.memory_id] = (entry, score)

        for entry, sim in ltm_results:
            combined = entry.importance_score * sim
            if entry.memory_id not in scored or combined > scored[entry.memory_id][1]:
                scored[entry.memory_id] = (entry, combined)

        ranked = sorted(scored.values(), key=lambda t: t[1], reverse=True)
        return ranked[:top_k]
