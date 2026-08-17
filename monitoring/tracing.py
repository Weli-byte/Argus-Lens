"""
Distributed Tracer — in-process span tracking with optional Jaeger export
over HTTP (Thrift/JSON collector API).
"""

from __future__ import annotations

import asyncio
import json
import os
import time
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator, Callable, Optional

from loguru import logger

try:
    import httpx

    _HTTPX_AVAILABLE = True
except ImportError:
    _HTTPX_AVAILABLE = False

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_JAEGER_ENDPOINT = os.getenv(
    "JAEGER_COLLECTOR_ENDPOINT",
    "http://jaeger:14268/api/traces",
)
_SERVICE_NAME = os.getenv("JAEGER_SERVICE_NAME", "arguslens")
_JAEGER_ENABLED = os.getenv("JAEGER_ENABLED", "false").lower() == "true"

# ---------------------------------------------------------------------------
# Domain types
# ---------------------------------------------------------------------------


@dataclass
class RequestTrace:
    trace_id: str
    span_id: str
    operation: str
    start_time: float               # monotonic
    parent_span_id: Optional[str] = None
    end_time: Optional[float] = None
    success: Optional[bool] = None
    tags: dict[str, Any] = field(default_factory=dict)
    logs: list[dict[str, Any]] = field(default_factory=list)

    @property
    def duration_ms(self) -> Optional[float]:
        if self.end_time is None:
            return None
        return round((self.end_time - self.start_time) * 1000, 2)

    def log(self, message: str, **fields: Any) -> None:
        self.logs.append({"ts": time.monotonic(), "message": message, **fields})


# ---------------------------------------------------------------------------
# Tracer
# ---------------------------------------------------------------------------


class DistributedTracer:
    """
    Lightweight distributed tracer.

    * Generates UUID4 trace and span IDs (never sequential).
    * Stores active spans in memory (evicted on finish).
    * Exports finished spans to Jaeger via HTTP POST if JAEGER_ENABLED=true.
    * Provides async context managers for inference and WebSocket operations.
    """

    def __init__(self, max_active_traces: int = 10_000) -> None:
        self._active: dict[str, RequestTrace] = {}
        self._lock = asyncio.Lock()
        self.max_active_traces = max_active_traces
        self._http_client: Optional[Any] = None
        if _JAEGER_ENABLED and _HTTPX_AVAILABLE:
            self._http_client = httpx.AsyncClient(timeout=5.0)
            logger.info("DistributedTracer Jaeger export enabled → {}", _JAEGER_ENDPOINT)

    # ------------------------------------------------------------------
    # ID generation
    # ------------------------------------------------------------------

    @staticmethod
    def generate_trace_id() -> str:
        """Return a UUID4 hex string (not sequential — no information leakage)."""
        return uuid.uuid4().hex

    @staticmethod
    def _generate_span_id() -> str:
        return uuid.uuid4().hex[:16]

    # ------------------------------------------------------------------
    # Span lifecycle
    # ------------------------------------------------------------------

    async def start_span(
        self,
        operation: str,
        parent_trace_id: Optional[str] = None,
        tags: Optional[dict[str, Any]] = None,
    ) -> RequestTrace:
        """Open a new span.  Returns the RequestTrace object."""
        trace = RequestTrace(
            trace_id=parent_trace_id or self.generate_trace_id(),
            span_id=self._generate_span_id(),
            operation=operation,
            start_time=time.monotonic(),
            parent_span_id=None,
            tags=tags or {},
        )
        async with self._lock:
            if len(self._active) >= self.max_active_traces:
                # Evict oldest to prevent unbounded growth
                oldest = min(self._active.values(), key=lambda t: t.start_time)
                del self._active[oldest.span_id]
                logger.warning("Max active traces reached — evicted oldest span={}", oldest.span_id)
            self._active[trace.span_id] = trace
        return trace

    async def finish_span(
        self,
        trace: RequestTrace,
        success: bool = True,
        metadata: Optional[dict[str, Any]] = None,
    ) -> None:
        """Close a span and optionally export to Jaeger."""
        trace.end_time = time.monotonic()
        trace.success = success
        if metadata:
            trace.tags.update(metadata)

        async with self._lock:
            self._active.pop(trace.span_id, None)

        logger.debug(
            "Span finished operation={} trace={} span={} duration={}ms success={}",
            trace.operation,
            trace.trace_id[:8],
            trace.span_id[:8],
            trace.duration_ms,
            success,
        )

        if _JAEGER_ENABLED:
            await self.export_to_jaeger(trace)

    # ------------------------------------------------------------------
    # High-level helpers
    # ------------------------------------------------------------------

    async def trace_inference(
        self,
        model_id: str,
        inputs_shape: tuple[int, ...],
        fn: Callable[[], Any],
        parent_trace_id: Optional[str] = None,
    ) -> tuple[Any, RequestTrace]:
        """
        Wrap an inference callable with a span.  Returns (result, trace).
        """
        trace = await self.start_span(
            operation=f"inference.{model_id}",
            parent_trace_id=parent_trace_id,
            tags={"model_id": model_id, "input_shape": str(inputs_shape)},
        )
        success = True
        try:
            result = await asyncio.get_running_loop().run_in_executor(None, fn)
            return result, trace
        except Exception as exc:
            success = False
            trace.log("exception", error=str(exc))
            raise
        finally:
            await self.finish_span(trace, success=success)

    @asynccontextmanager
    async def trace_websocket_message(
        self,
        session_id: str,
        message_type: str,
        parent_trace_id: Optional[str] = None,
    ) -> AsyncGenerator[RequestTrace, None]:
        """
        Async context manager for tracing WebSocket message handling.

        Usage::

            async with tracer.trace_websocket_message(sid, "frame") as span:
                span.log("processing", stage="decode")
                result = await process(frame)
        """
        trace = await self.start_span(
            operation=f"websocket.{message_type}",
            parent_trace_id=parent_trace_id,
            tags={"session_id": session_id, "message_type": message_type},
        )
        success = True
        try:
            yield trace
        except Exception as exc:
            success = False
            trace.log("exception", error=str(exc))
            raise
        finally:
            await self.finish_span(trace, success=success)

    # ------------------------------------------------------------------
    # Jaeger export
    # ------------------------------------------------------------------

    async def export_to_jaeger(self, trace: RequestTrace) -> None:
        """
        POST a single span to the Jaeger HTTP collector in Thrift/JSON format.
        Silently drops spans if Jaeger is unreachable (non-blocking).
        """
        if not self._http_client:
            return

        start_us = int(trace.start_time * 1_000_000)
        duration_us = int((trace.duration_ms or 0) * 1000)

        payload = {
            "data": [
                {
                    "traceID": trace.trace_id,
                    "spans": [
                        {
                            "traceID": trace.trace_id,
                            "spanID": trace.span_id,
                            "operationName": trace.operation,
                            "startTime": start_us,
                            "duration": duration_us,
                            "tags": [
                                {"key": k, "type": "string", "value": str(v)}
                                for k, v in trace.tags.items()
                            ],
                            "logs": [
                                {
                                    "timestamp": int(log["ts"] * 1_000_000),
                                    "fields": [
                                        {"key": k, "type": "string", "value": str(v)}
                                        for k, v in log.items()
                                        if k != "ts"
                                    ],
                                }
                                for log in trace.logs
                            ],
                            "processID": "p1",
                            "warnings": None,
                            "references": (
                                [
                                    {
                                        "refType": "CHILD_OF",
                                        "traceID": trace.trace_id,
                                        "spanID": trace.parent_span_id,
                                    }
                                ]
                                if trace.parent_span_id
                                else []
                            ),
                        }
                    ],
                    "processes": {
                        "p1": {
                            "serviceName": _SERVICE_NAME,
                            "tags": [],
                        }
                    },
                }
            ]
        }

        try:
            resp = await self._http_client.post(
                _JAEGER_ENDPOINT,
                content=json.dumps(payload),
                headers={"Content-Type": "application/json"},
            )
            if resp.status_code not in (200, 202):
                logger.debug("Jaeger export returned status={}", resp.status_code)
        except Exception as exc:
            logger.debug("Jaeger export failed (non-critical): {}", exc)

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def get_active_traces(self) -> list[RequestTrace]:
        return list(self._active.values())

    async def close(self) -> None:
        if self._http_client:
            await self._http_client.aclose()
