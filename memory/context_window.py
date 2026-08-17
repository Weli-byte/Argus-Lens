"""
Context window manager with token-budget enforcement.
Maintains a bounded, prioritized view of memory entries
that fit within a configurable token budget.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from intelligence.types import MemoryEntry, MemoryType

logger = logging.getLogger(__name__)

# Rough heuristic: 1 token ≈ 4 chars for English text
_CHARS_PER_TOKEN = 4


@dataclass
class ContextSlot:
    """One entry in the assembled context window."""

    entry: MemoryEntry
    token_estimate: int
    relevance_score: float = 1.0
    pinned: bool = False  # pinned slots are never evicted


class ContextWindow:
    """
    Token-budget-aware context window.

    Entries are scored by importance × recency × relevance.
    When budget is exceeded, lowest-scored non-pinned slots are evicted first.

    Default budget: 4096 tokens (≈ 16 KB of text).
    """

    def __init__(self, max_tokens: int = 4096) -> None:
        self._max_tokens = max_tokens
        self._slots: list[ContextSlot] = []
        self._used_tokens = 0

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def used_tokens(self) -> int:
        return self._used_tokens

    @property
    def remaining_tokens(self) -> int:
        return self._max_tokens - self._used_tokens

    @property
    def utilization(self) -> float:
        return self._used_tokens / self._max_tokens if self._max_tokens > 0 else 0.0

    # ------------------------------------------------------------------
    # Mutation
    # ------------------------------------------------------------------

    def add(
        self,
        entry: MemoryEntry,
        relevance_score: float = 1.0,
        pinned: bool = False,
    ) -> bool:
        """
        Attempt to add an entry to the context window.
        Evicts lowest-priority non-pinned entries if over budget.
        Returns True if the entry was successfully added.
        """
        token_count = self._estimate_tokens(entry.content)
        if token_count > self._max_tokens:
            logger.warning(
                "ctx_window.add entry too large memory_id=%s tokens=%d budget=%d",
                entry.memory_id,
                token_count,
                self._max_tokens,
            )
            return False

        # Try to free space if needed
        while self._used_tokens + token_count > self._max_tokens:
            evicted = self._evict_one()
            if not evicted:
                logger.debug(
                    "ctx_window.add cannot fit memory_id=%s — all slots pinned",
                    entry.memory_id,
                )
                return False

        slot = ContextSlot(
            entry=entry,
            token_estimate=token_count,
            relevance_score=relevance_score,
            pinned=pinned,
        )
        self._slots.append(slot)
        self._used_tokens += token_count
        logger.debug(
            "ctx_window.add memory_id=%s tokens=%d used=%d/%d",
            entry.memory_id,
            token_count,
            self._used_tokens,
            self._max_tokens,
        )
        return True

    def add_many(
        self,
        entries: list[MemoryEntry],
        relevance_scores: list[float] | None = None,
    ) -> int:
        """Add multiple entries. Returns count successfully added."""
        scores = relevance_scores or [1.0] * len(entries)
        added = 0
        for entry, score in zip(entries, scores):
            if self.add(entry, relevance_score=score):
                added += 1
        return added

    def pin(self, memory_id: str) -> bool:
        """Mark an entry as pinned (never evicted)."""
        for slot in self._slots:
            if slot.entry.memory_id == memory_id:
                slot.pinned = True
                return True
        return False

    def remove(self, memory_id: str) -> bool:
        """Manually remove an entry by memory_id."""
        for i, slot in enumerate(self._slots):
            if slot.entry.memory_id == memory_id:
                self._used_tokens -= slot.token_estimate
                self._slots.pop(i)
                return True
        return False

    def clear(self) -> None:
        self._slots.clear()
        self._used_tokens = 0

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def get_entries(
        self,
        memory_type: MemoryType | None = None,
        min_relevance: float = 0.0,
    ) -> list[MemoryEntry]:
        """Return entries sorted by composite priority (descending)."""
        slots = self._slots
        if memory_type is not None:
            slots = [s for s in slots if s.entry.memory_type == memory_type]
        if min_relevance > 0.0:
            slots = [s for s in slots if s.relevance_score >= min_relevance]
        return [s.entry for s in sorted(slots, key=self._slot_priority, reverse=True)]

    def to_prompt_context(self) -> str:
        """Serialize the context window to a structured string for LLM prompts."""
        lines: list[str] = ["=== MEMORY CONTEXT ==="]
        for slot in sorted(self._slots, key=self._slot_priority, reverse=True):
            e = slot.entry
            lines.append(
                f"[{e.memory_type.value.upper()}] (importance={e.importance_score:.2f}) {e.content}"
            )
        lines.append("=== END CONTEXT ===")
        return "\n".join(lines)

    def snapshot(self) -> dict[str, Any]:
        return {
            "max_tokens": self._max_tokens,
            "used_tokens": self._used_tokens,
            "utilization": round(self.utilization, 3),
            "slot_count": len(self._slots),
            "entries": [
                {
                    "memory_id": s.entry.memory_id,
                    "type": s.entry.memory_type.value,
                    "tokens": s.token_estimate,
                    "relevance": round(s.relevance_score, 3),
                    "pinned": s.pinned,
                }
                for s in self._slots
            ],
        }

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _evict_one(self) -> bool:
        """Remove the lowest-priority non-pinned slot. Returns True if evicted."""
        candidates = [s for s in self._slots if not s.pinned]
        if not candidates:
            return False
        victim = min(candidates, key=self._slot_priority)
        self._used_tokens -= victim.token_estimate
        self._slots.remove(victim)
        logger.debug(
            "ctx_window.evict memory_id=%s priority=%.4f",
            victim.entry.memory_id,
            self._slot_priority(victim),
        )
        return True

    @staticmethod
    def _slot_priority(slot: ContextSlot) -> float:
        """Composite score: importance × relevance (both 0–1)."""
        return slot.entry.importance_score * slot.relevance_score

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        return max(1, len(text) // _CHARS_PER_TOKEN)
