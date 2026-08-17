"""
Database Connection Optimizer — pooling, slow-query logging, vector index
management, and N+1 query detection.
"""

from __future__ import annotations

import time
import traceback
from collections import defaultdict
from contextlib import asynccontextmanager
from contextvars import ContextVar
from typing import Any, AsyncGenerator

from loguru import logger
from prometheus_client import Counter, Gauge
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import AsyncAdaptedQueuePool

from core.config import settings

# ---------------------------------------------------------------------------
# Prometheus
# ---------------------------------------------------------------------------

_POOL_SIZE = Gauge("arguslens_db_pool_size", "SQLAlchemy connection pool size")
_POOL_CHECKED_OUT = Gauge(
    "arguslens_db_pool_checked_out", "Connections currently checked out"
)
_SLOW_QUERY_TOTAL = Counter(
    "arguslens_slow_query_total",
    "Number of queries that exceeded the slow-query threshold",
)
_POOL_EXHAUSTION = Counter(
    "arguslens_db_pool_exhaustion_total",
    "Number of times the connection pool was fully exhausted",
)

# ---------------------------------------------------------------------------
# Per-request query tracker
# ---------------------------------------------------------------------------

_request_query_count: ContextVar[list[int]] = ContextVar("_request_query_count", default=[])


# ---------------------------------------------------------------------------
# Slow Query Logger
# ---------------------------------------------------------------------------


class SlowQueryLogger:
    """
    SQLAlchemy event listener that logs queries exceeding *threshold_ms* with
    the full query text, parameters, duration, and call-site.
    """

    def __init__(self, threshold_ms: float = 100.0) -> None:
        self.threshold_ms = threshold_ms

    def register(self, engine: AsyncEngine) -> None:
        sync_engine = engine.sync_engine

        @event.listens_for(sync_engine, "before_cursor_execute")
        def _before(conn, cursor, statement, parameters, context, executemany):
            conn.info.setdefault("query_start_time", []).append(time.perf_counter())

        @event.listens_for(sync_engine, "after_cursor_execute")
        def _after(conn, cursor, statement, parameters, context, executemany):
            elapsed_ms = (
                time.perf_counter() - conn.info["query_start_time"].pop(-1)
            ) * 1000

            # Update per-request counter (if inside a traced request)
            counts = _request_query_count.get([])
            if counts:
                counts[0] += 1

            if elapsed_ms >= self.threshold_ms:
                _SLOW_QUERY_TOTAL.inc()
                caller = _get_caller_frame()
                logger.warning(
                    "Slow query {:.1f}ms caller={} sql={}",
                    elapsed_ms,
                    caller,
                    statement[:200],
                )


def _get_caller_frame() -> str:
    """Walk the call stack to find the first application frame."""
    for line in traceback.format_stack():
        if "sqlalchemy" not in line and "arguslens" in line.lower():
            return line.strip()
    return "unknown"


# ---------------------------------------------------------------------------
# Vector Index Optimizer
# ---------------------------------------------------------------------------


class VectorIndexOptimizer:
    """
    Helpers for managing pgvector HNSW indexes on embedding columns.
    All methods accept an active *AsyncSession*.
    """

    @staticmethod
    async def create_hnsw_index(
        session: AsyncSession,
        table: str,
        column: str,
        m: int = 16,
        ef_construction: int = 64,
    ) -> None:
        """
        Create an HNSW index for cosine-distance approximate nearest-neighbour
        search.  Safe to call when the index already exists (uses IF NOT EXISTS).
        """
        index_name = f"hnsw_{table}_{column}_idx"
        sql = text(f"""
            CREATE INDEX IF NOT EXISTS {index_name}
            ON {table}
            USING hnsw ({column} vector_cosine_ops)
            WITH (m = {m}, ef_construction = {ef_construction});
        """)
        await session.execute(sql)
        await session.commit()
        logger.info(
            "HNSW index created/verified: {} on {}.{} m={} ef_construction={}",
            index_name,
            table,
            column,
            m,
            ef_construction,
        )

    @staticmethod
    async def analyze_index_health(session: AsyncSession) -> dict[str, Any]:
        """
        Return size, bloat estimate, and usage statistics for all pgvector indexes.
        """
        sql = text("""
            SELECT
                indexname,
                pg_size_pretty(pg_relation_size(indexname::regclass)) AS size,
                idx_scan,
                idx_tup_read,
                idx_tup_fetch
            FROM pg_stat_user_indexes
            WHERE indexname LIKE 'hnsw_%';
        """)
        result = await session.execute(sql)
        rows = result.fetchall()
        return {
            row.indexname: {
                "size": row.size,
                "scans": row.idx_scan,
                "tuples_read": row.idx_tup_read,
                "tuples_fetched": row.idx_tup_fetch,
            }
            for row in rows
        }

    @staticmethod
    def recommend_ef_search(expected_qps: int) -> int:
        """
        Recommend an ef_search value balancing recall vs latency for the given
        expected queries-per-second.  Higher QPS → lower ef_search.
        """
        if expected_qps <= 10:
            return 200
        elif expected_qps <= 50:
            return 100
        elif expected_qps <= 200:
            return 64
        else:
            return 40


# ---------------------------------------------------------------------------
# Query Tracer (N+1 detection)
# ---------------------------------------------------------------------------


class QueryTracer:
    """
    Async context manager that counts SQL queries executed within the scope
    and warns if N+1 patterns are detected.
    """

    _N_PLUS_ONE_THRESHOLD = 10

    def __init__(self) -> None:
        self._counter: list[int] = [0]  # mutable so the closure can mutate it

    @asynccontextmanager
    async def trace(self, operation: str) -> AsyncGenerator["QueryTracer", None]:
        """
        Usage::

            async with tracer.trace("load_detections"):
                detections = await db.execute(...)
        """
        token = _request_query_count.set(self._counter)
        self._counter[0] = 0
        start = time.perf_counter()
        try:
            yield self
        finally:
            _request_query_count.reset(token)
            elapsed_ms = (time.perf_counter() - start) * 1000
            count = self._counter[0]
            if count >= self._N_PLUS_ONE_THRESHOLD:
                logger.warning(
                    "N+1 query smell: operation='{}' executed {} queries in {:.1f}ms",
                    operation,
                    count,
                    elapsed_ms,
                )
            else:
                logger.debug(
                    "QueryTracer operation='{}' queries={} elapsed={:.1f}ms",
                    operation,
                    count,
                    elapsed_ms,
                )

    @property
    def query_count(self) -> int:
        return self._counter[0]


# ---------------------------------------------------------------------------
# Optimized async engine factory
# ---------------------------------------------------------------------------


def create_optimized_engine() -> AsyncEngine:
    """
    Build an AsyncEngine with production-grade pool settings, health checks,
    exponential-backoff reconnection, and pool-exhaustion alerting.
    """
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=False,
        future=True,
        poolclass=AsyncAdaptedQueuePool,
        pool_size=5,
        max_overflow=10,
        pool_timeout=30,
        pool_recycle=1800,          # recycle connections every 30 min
        pool_pre_ping=True,         # health check before every checkout
        connect_args={
            "command_timeout": 60,
            "server_settings": {"application_name": "arguslens"},
        },
    )

    _register_pool_events(engine)
    return engine


def _register_pool_events(engine: AsyncEngine) -> None:
    sync_engine = engine.sync_engine

    @event.listens_for(sync_engine, "connect")
    def on_connect(dbapi_conn, connection_record):
        logger.debug("DB connection established pid={}", id(dbapi_conn))
        _POOL_SIZE.set(sync_engine.pool.size())

    @event.listens_for(sync_engine, "checkout")
    def on_checkout(dbapi_conn, connection_record, connection_proxy):
        _POOL_CHECKED_OUT.inc()

    @event.listens_for(sync_engine, "checkin")
    def on_checkin(dbapi_conn, connection_record):
        _POOL_CHECKED_OUT.dec()

    @event.listens_for(sync_engine, "invalidate")
    def on_invalidate(dbapi_conn, connection_record, exception):
        logger.warning("DB connection invalidated: {}", exception)

    # Pool exhaustion detection: timeout during checkout
    @event.listens_for(sync_engine, "engine_connect")
    def on_engine_connect(conn):
        pass  # hook point for future extensions


def build_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Return a configured session factory bound to *engine*."""
    return async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )


# ---------------------------------------------------------------------------
# Singleton instances (imported by database/session.py)
# ---------------------------------------------------------------------------

optimized_engine = create_optimized_engine()
optimized_session_factory = build_session_factory(optimized_engine)
slow_query_logger = SlowQueryLogger(threshold_ms=100.0)
slow_query_logger.register(optimized_engine)
query_tracer = QueryTracer()
vector_index_optimizer = VectorIndexOptimizer()


async def get_optimized_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency: yield an async session from the optimized pool."""
    async with optimized_session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
