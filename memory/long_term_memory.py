"""
Long-term memory backed by PostgreSQL + pgvector.
Stores consolidated insights, patterns, and semantic memories
with cosine-similarity retrieval via HNSW index.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta
from typing import Any, Sequence

from sqlalchemy import Column, DateTime, Float, Integer, String, Text, delete, select, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.asyncio import AsyncSession

from intelligence.types import MemoryEntry, MemoryType

logger = logging.getLogger(__name__)

# pgvector extension — imported lazily to avoid hard dep if not installed
try:
    from pgvector.sqlalchemy import Vector  # type: ignore[import]
    _PGVECTOR_AVAILABLE = True
except ImportError:
    Vector = None  # type: ignore[assignment]
    _PGVECTOR_AVAILABLE = False


# ---------------------------------------------------------------------------
# ORM Model
# ---------------------------------------------------------------------------

from sqlalchemy.orm import DeclarativeBase


class _LTMBase(DeclarativeBase):
    pass


class LongTermMemoryRecord(_LTMBase):
    __tablename__ = "ltm_memories"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    memory_id = Column(String(64), unique=True, nullable=False, index=True)
    session_id = Column(String(64), nullable=False, index=True)
    memory_type = Column(String(32), nullable=False)
    content = Column(Text, nullable=False)
    embedding = Column(Vector(384) if _PGVECTOR_AVAILABLE and Vector else Text)
    importance_score = Column(Float, default=0.5)
    access_count = Column(Integer, default=0)
    tags = Column(JSONB, default=list)
    source = Column(String(128), default="")
    extra_metadata = Column(JSONB, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_accessed = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)


# ---------------------------------------------------------------------------
# Manager
# ---------------------------------------------------------------------------


class LongTermMemory:
    """
    Persistent memory with semantic similarity search via pgvector.
    Consolidation threshold: importance_score >= 0.7.
    """

    _CONSOLIDATION_THRESHOLD = 0.7
    _DEFAULT_EMBEDDING_DIM = 384  # all-MiniLM-L6-v2

    def __init__(self, db_session: AsyncSession, embedding_fn: Any | None = None) -> None:
        self._db = db_session
        self._embed = embedding_fn  # callable: str → list[float]

    # ------------------------------------------------------------------
    # Write operations
    # ------------------------------------------------------------------

    async def consolidate(self, entry: MemoryEntry, session_id: str) -> bool:
        """
        Persist a MemoryEntry to long-term storage.
        Only entries with importance_score >= threshold are stored.
        Returns True if stored, False if skipped.
        """
        if entry.importance_score < self._CONSOLIDATION_THRESHOLD:
            logger.debug(
                "ltm.consolidate skip memory_id=%s score=%.3f below_threshold=%.2f",
                entry.memory_id,
                entry.importance_score,
                self._CONSOLIDATION_THRESHOLD,
            )
            return False

        embedding_data = entry.embedding or await self._compute_embedding(entry.content)

        record = LongTermMemoryRecord(
            memory_id=entry.memory_id,
            session_id=session_id,
            memory_type=entry.memory_type.value,
            content=entry.content,
            embedding=embedding_data if _PGVECTOR_AVAILABLE else str(embedding_data),
            importance_score=entry.importance_score,
            access_count=entry.access_count,
            tags=entry.tags,
            source=entry.source,
            extra_metadata=entry.metadata,
            created_at=entry.created_at,
            last_accessed=entry.last_accessed,
            expires_at=entry.expires_at,
        )
        self._db.add(record)
        await self._db.commit()
        logger.info(
            "ltm.consolidated session=%s memory_id=%s type=%s",
            session_id,
            entry.memory_id,
            entry.memory_type.value,
        )
        return True

    async def update_importance(self, memory_id: str, new_score: float) -> bool:
        stmt = select(LongTermMemoryRecord).where(
            LongTermMemoryRecord.memory_id == memory_id
        )
        result = await self._db.execute(stmt)
        record = result.scalar_one_or_none()
        if not record:
            return False
        record.importance_score = max(0.0, min(1.0, new_score))
        await self._db.commit()
        return True

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------

    async def semantic_search(
        self,
        query: str,
        top_k: int = 5,
        min_similarity: float = 0.6,
        session_id: str | None = None,
        memory_type: MemoryType | None = None,
    ) -> list[tuple[MemoryEntry, float]]:
        """
        Retrieve entries by semantic similarity (cosine via pgvector).
        Falls back to empty list if pgvector unavailable.
        """
        if not _PGVECTOR_AVAILABLE:
            logger.warning("ltm.semantic_search pgvector unavailable — returning empty")
            return []

        query_embedding = await self._compute_embedding(query)
        if not query_embedding:
            return []

        embedding_str = "[" + ",".join(str(v) for v in query_embedding) + "]"

        # Build WHERE conditions
        conditions = ["1=1"]
        params: dict[str, Any] = {"embedding": embedding_str, "top_k": top_k}
        if session_id:
            conditions.append("session_id = :session_id")
            params["session_id"] = session_id
        if memory_type:
            conditions.append("memory_type = :memory_type")
            params["memory_type"] = memory_type.value

        where_clause = " AND ".join(conditions)
        sql = text(
            f"""
            SELECT memory_id, memory_type, content, importance_score,
                   access_count, tags, source, extra_metadata,
                   created_at, last_accessed, expires_at,
                   1 - (embedding <=> :embedding::vector) AS similarity
            FROM ltm_memories
            WHERE {where_clause}
            ORDER BY similarity DESC
            LIMIT :top_k
            """
        )
        result = await self._db.execute(sql, params)
        rows = result.fetchall()

        output: list[tuple[MemoryEntry, float]] = []
        for row in rows:
            sim = float(row.similarity)
            if sim < min_similarity:
                continue
            entry = MemoryEntry(
                memory_id=row.memory_id,
                memory_type=MemoryType(row.memory_type),
                content=row.content,
                importance_score=row.importance_score,
                access_count=row.access_count,
                created_at=row.created_at,
                last_accessed=row.last_accessed,
                expires_at=row.expires_at,
                tags=row.tags or [],
                source=row.source or "",
                metadata=row.extra_metadata or {},
            )
            output.append((entry, sim))

        # Update access counts asynchronously
        if output:
            await self._touch_entries([e.memory_id for e, _ in output])

        logger.debug(
            "ltm.semantic_search query_len=%d results=%d",
            len(query),
            len(output),
        )
        return output

    async def retrieve_by_session(
        self, session_id: str, limit: int = 50
    ) -> list[MemoryEntry]:
        stmt = (
            select(LongTermMemoryRecord)
            .where(LongTermMemoryRecord.session_id == session_id)
            .order_by(LongTermMemoryRecord.importance_score.desc())
            .limit(limit)
        )
        result = await self._db.execute(stmt)
        records: Sequence[LongTermMemoryRecord] = result.scalars().all()
        return [self._to_entry(r) for r in records]

    async def prune_expired(self) -> int:
        """Delete records past their expires_at. Returns count deleted."""
        stmt = delete(LongTermMemoryRecord).where(
            LongTermMemoryRecord.expires_at < datetime.utcnow()
        )
        result = await self._db.execute(stmt)
        await self._db.commit()
        count = result.rowcount
        if count:
            logger.info("ltm.prune deleted=%d expired records", count)
        return count

    async def get_statistics(self) -> dict[str, Any]:
        total_sql = text("SELECT COUNT(*) FROM ltm_memories")
        by_type_sql = text(
            "SELECT memory_type, COUNT(*) FROM ltm_memories GROUP BY memory_type"
        )
        avg_sql = text("SELECT AVG(importance_score) FROM ltm_memories")

        total_result = await self._db.execute(total_sql)
        by_type_result = await self._db.execute(by_type_sql)
        avg_result = await self._db.execute(avg_sql)

        return {
            "total_entries": total_result.scalar() or 0,
            "by_type": {row[0]: row[1] for row in by_type_result.fetchall()},
            "avg_importance": float(avg_result.scalar() or 0.0),
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _compute_embedding(self, text_input: str) -> list[float]:
        if self._embed is None:
            return []
        try:
            result = await self._embed(text_input)
            return result if isinstance(result, list) else result.tolist()
        except Exception as exc:
            logger.warning("ltm.embedding failed: %s", exc)
            return []

    async def _touch_entries(self, memory_ids: list[str]) -> None:
        if not memory_ids:
            return
        sql = text(
            """
            UPDATE ltm_memories
            SET access_count = access_count + 1,
                last_accessed = NOW()
            WHERE memory_id = ANY(:ids)
            """
        )
        await self._db.execute(sql, {"ids": memory_ids})
        await self._db.commit()

    @staticmethod
    def _to_entry(record: LongTermMemoryRecord) -> MemoryEntry:
        return MemoryEntry(
            memory_id=record.memory_id,
            memory_type=MemoryType(record.memory_type),
            content=record.content,
            importance_score=record.importance_score,
            access_count=record.access_count,
            created_at=record.created_at,
            last_accessed=record.last_accessed,
            expires_at=record.expires_at,
            tags=record.tags or [],
            source=record.source or "",
            metadata=record.extra_metadata or {},
        )
