"""
API Resilience Middleware — circuit breaker, retry, per-endpoint timeouts,
graceful degradation, and a composite health-score endpoint.
"""

from __future__ import annotations

import asyncio
import time
from collections import defaultdict
from enum import Enum
from typing import Any, Callable, Coroutine, Optional

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from loguru import logger
from prometheus_client import Counter, Gauge
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

# ---------------------------------------------------------------------------
# Prometheus
# ---------------------------------------------------------------------------

_CB_OPEN = Gauge(
    "arguslens_circuit_breaker_open",
    "1 if circuit breaker is OPEN for the endpoint",
    ["endpoint"],
)
_TIMEOUT_TOTAL = Counter(
    "arguslens_api_timeout_total",
    "Total number of API requests that timed out",
    ["endpoint"],
)
_RETRY_TOTAL = Counter(
    "arguslens_api_retry_total",
    "Total number of automatic request retries",
    ["endpoint"],
)

# ---------------------------------------------------------------------------
# Per-endpoint timeout configuration (seconds)
# ---------------------------------------------------------------------------

_ENDPOINT_TIMEOUTS: dict[str, Optional[float]] = {
    "/api/v1/detect": 60.0,
    "/api/v1/temporal/analyze": 30.0,
    "/api/v1/stream/live": None,   # streaming — no timeout
}
_DEFAULT_TIMEOUT = 30.0


def _get_timeout(path: str) -> Optional[float]:
    for pattern, timeout in _ENDPOINT_TIMEOUTS.items():
        if path.startswith(pattern):
            return timeout
    return _DEFAULT_TIMEOUT


# ---------------------------------------------------------------------------
# Circuit Breaker
# ---------------------------------------------------------------------------


class _CBState(str, Enum):
    CLOSED = "CLOSED"       # normal — requests flow through
    OPEN = "OPEN"           # tripped — requests fail fast
    HALF_OPEN = "HALF_OPEN" # probing — limited requests allowed


class _EndpointCircuit:
    """Per-endpoint circuit breaker state machine."""

    def __init__(
        self,
        failure_threshold: int,
        recovery_timeout: float,
        half_open_max_calls: int,
    ) -> None:
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls

        self.state = _CBState.CLOSED
        self.failure_count = 0
        self.half_open_calls = 0
        self.opened_at: Optional[float] = None

    def record_success(self) -> None:
        if self.state == _CBState.HALF_OPEN:
            self.half_open_calls += 1
            if self.half_open_calls >= self.half_open_max_calls:
                self._close()
        elif self.state == _CBState.CLOSED:
            self.failure_count = max(0, self.failure_count - 1)

    def record_failure(self) -> None:
        self.failure_count += 1
        if self.state == _CBState.HALF_OPEN:
            self._open()
        elif (
            self.state == _CBState.CLOSED
            and self.failure_count >= self.failure_threshold
        ):
            self._open()

    def is_allowed(self) -> bool:
        if self.state == _CBState.CLOSED:
            return True
        if self.state == _CBState.OPEN:
            if time.monotonic() - (self.opened_at or 0) >= self.recovery_timeout:
                self._half_open()
                return True
            return False
        # HALF_OPEN: allow one probe
        return True

    def _open(self) -> None:
        self.state = _CBState.OPEN
        self.opened_at = time.monotonic()
        self.half_open_calls = 0
        logger.warning("Circuit OPEN for endpoint")

    def _half_open(self) -> None:
        self.state = _CBState.HALF_OPEN
        self.half_open_calls = 0
        logger.info("Circuit HALF_OPEN — probing recovery")

    def _close(self) -> None:
        self.state = _CBState.CLOSED
        self.failure_count = 0
        self.opened_at = None
        logger.info("Circuit CLOSED — service recovered")


class CircuitBreakerMiddleware(BaseHTTPMiddleware):
    """
    Per-endpoint circuit breaker.

    Opens after *failure_threshold* consecutive 5xx responses.
    Transitions to HALF_OPEN after *recovery_timeout* seconds.
    Closes after *half_open_max_calls* successful probes.
    """

    def __init__(
        self,
        app: ASGIApp,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        half_open_max_calls: int = 3,
    ) -> None:
        super().__init__(app)
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls
        self._circuits: dict[str, _EndpointCircuit] = defaultdict(
            lambda: _EndpointCircuit(failure_threshold, recovery_timeout, half_open_max_calls)
        )

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        endpoint = request.url.path
        circuit = self._circuits[endpoint]

        if not circuit.is_allowed():
            _CB_OPEN.labels(endpoint=endpoint).set(1)
            logger.warning("Circuit OPEN — fast-failing request to {}", endpoint)
            return JSONResponse(
                status_code=503,
                content={
                    "detail": "Service temporarily unavailable (circuit open)",
                    "retry_after": int(
                        self.recovery_timeout
                        - (time.monotonic() - (circuit.opened_at or 0))
                    ),
                },
                headers={"Retry-After": str(self.recovery_timeout)},
            )

        response = await call_next(request)

        if response.status_code >= 500:
            circuit.record_failure()
            _CB_OPEN.labels(endpoint=endpoint).set(
                1 if circuit.state != _CBState.CLOSED else 0
            )
        else:
            circuit.record_success()
            if circuit.state == _CBState.CLOSED:
                _CB_OPEN.labels(endpoint=endpoint).set(0)

        return response


# ---------------------------------------------------------------------------
# Timeout Middleware
# ---------------------------------------------------------------------------


class TimeoutMiddleware(BaseHTTPMiddleware):
    """
    Per-endpoint request timeout.  Returns HTTP 504 with a structured error
    body when a handler exceeds its time budget.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        timeout = _get_timeout(request.url.path)
        if timeout is None:
            return await call_next(request)

        try:
            return await asyncio.wait_for(call_next(request), timeout=timeout)
        except asyncio.TimeoutError:
            endpoint = request.url.path
            _TIMEOUT_TOTAL.labels(endpoint=endpoint).inc()
            logger.error("Request timeout {}s endpoint={}", timeout, endpoint)
            return JSONResponse(
                status_code=504,
                content={
                    "detail": f"Request timed out after {timeout}s",
                    "endpoint": endpoint,
                },
            )


# ---------------------------------------------------------------------------
# Retry Middleware
# ---------------------------------------------------------------------------


class RetryMiddleware(BaseHTTPMiddleware):
    """
    Automatic retry for transient server errors (503, 504) and network errors.
    Does NOT retry 4xx (client errors).

    Uses exponential back-off: delay = backoff_factor * (2 ** attempt).
    """

    _RETRYABLE_STATUS = {503, 504}

    def __init__(
        self,
        app: ASGIApp,
        max_retries: int = 3,
        backoff_factor: float = 0.5,
    ) -> None:
        super().__init__(app)
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        endpoint = request.url.path
        last_response: Optional[Response] = None

        for attempt in range(self.max_retries + 1):
            try:
                response = await call_next(request)
                if response.status_code not in self._RETRYABLE_STATUS or attempt == self.max_retries:
                    return response
                delay = self.backoff_factor * (2 ** attempt)
                logger.warning(
                    "Retrying endpoint={} attempt={}/{} after {:.2f}s (status={})",
                    endpoint, attempt + 1, self.max_retries, delay, response.status_code,
                )
                _RETRY_TOTAL.labels(endpoint=endpoint).inc()
                await asyncio.sleep(delay)
                last_response = response
            except (ConnectionError, OSError) as exc:
                if attempt == self.max_retries:
                    raise
                delay = self.backoff_factor * (2 ** attempt)
                logger.warning("Network error on {}: {} — retrying in {:.2f}s", endpoint, exc, delay)
                _RETRY_TOTAL.labels(endpoint=endpoint).inc()
                await asyncio.sleep(delay)

        return last_response  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Graceful Degradation Middleware
# ---------------------------------------------------------------------------


class GracefulDegradationMiddleware(BaseHTTPMiddleware):
    """
    When the inference service is down, attempt to return a cached result.
    Falls back to HTTP 503 with Retry-After if no cache is available.
    """

    _INFERENCE_PATHS = {"/api/v1/detect", "/api/v1/temporal/analyze"}

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)

        if (
            response.status_code >= 500
            and request.url.path in self._INFERENCE_PATHS
        ):
            # Attempt cache lookup via app state
            cache = getattr(request.app.state, "inference_cache", None)
            if cache:
                cache_key = f"degraded:{request.url.path}"
                cached = await cache.get_cached_result(cache_key)
                if cached:
                    logger.warning(
                        "Inference service down — returning cached result for {}",
                        request.url.path,
                    )
                    return JSONResponse(
                        content={**cached, "cached": True, "warning": "inference_service_degraded"},
                        status_code=200,
                    )

            return JSONResponse(
                status_code=503,
                content={"detail": "Inference service temporarily unavailable"},
                headers={"Retry-After": "30"},
            )

        return response


# ---------------------------------------------------------------------------
# Health score endpoint
# ---------------------------------------------------------------------------


def register_health_score_endpoint(app: FastAPI) -> None:
    """Add GET /health/score to *app*."""

    @app.get("/health/score", tags=["health"])
    async def health_score(request: Request) -> JSONResponse:
        """
        Composite health score (0–100) across subsystems.
        Weights: GPU 30 %, DB 30 %, Redis 20 %, Workers 20 %.
        """
        components: dict[str, Any] = {}
        issues: list[str] = []

        # -- GPU --
        try:
            gpu_ctrl = getattr(request.app.state, "gpu_controller", None)
            if gpu_ctrl:
                vram = gpu_ctrl.get_vram_status()
                utilisation = (
                    vram["used_mb"] / vram["total_mb"] if vram["total_mb"] > 0 else 0
                )
                gpu_score = max(0.0, 1.0 - utilisation)
                components["gpu"] = {"score": round(gpu_score, 3), "vram": vram}
            else:
                gpu_score = 1.0
                components["gpu"] = {"score": 1.0, "note": "no_gpu_controller"}
        except Exception as exc:
            gpu_score = 0.0
            issues.append(f"gpu: {exc}")
            components["gpu"] = {"score": 0.0}

        # -- DB --
        try:
            from database.connection_optimizer import optimized_engine
            async with optimized_engine.connect() as conn:
                await conn.execute(__import__("sqlalchemy").text("SELECT 1"))
            db_score = 1.0
            components["db"] = {"score": 1.0}
        except Exception as exc:
            db_score = 0.0
            issues.append(f"db: {exc}")
            components["db"] = {"score": 0.0}

        # -- Redis --
        try:
            redis_client = getattr(request.app.state, "redis", None)
            if redis_client:
                await redis_client.ping()
                redis_score = 1.0
                components["redis"] = {"score": 1.0}
            else:
                redis_score = 0.5
                components["redis"] = {"score": 0.5, "note": "no_redis_client"}
        except Exception as exc:
            redis_score = 0.0
            issues.append(f"redis: {exc}")
            components["redis"] = {"score": 0.0}

        # -- Workers --
        try:
            failover = getattr(request.app.state, "failover_manager", None)
            if failover:
                cluster = await failover.get_cluster_health()
                total = cluster.get("total_workers", 0)
                healthy = cluster.get("healthy_workers", 0)
                workers_score = healthy / total if total > 0 else 1.0
                components["workers"] = {"score": round(workers_score, 3), **cluster}
            else:
                workers_score = 1.0
                components["workers"] = {"score": 1.0, "note": "standalone_mode"}
        except Exception as exc:
            workers_score = 0.0
            issues.append(f"workers: {exc}")
            components["workers"] = {"score": 0.0}

        overall = (
            gpu_score * 0.30
            + db_score * 0.30
            + redis_score * 0.20
            + workers_score * 0.20
        ) * 100

        return JSONResponse(
            content={
                "score": round(overall, 1),
                "components": components,
                "issues": issues,
            }
        )
