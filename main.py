"""
ArgusLens Enterprise API — application entry point.

Wires together all middleware, background tasks, and singleton services
that were built across the hardening phases.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

# .env dosyasını os.environ'a yükle. core/config.py bunu yalnızca kendi
# Settings modeline okuyor; GOOGLE_CLIENT_ID gibi doğrudan os.getenv ile
# okunan değerlerin de gelmesi için burada bir kez yüklüyoruz.
from dotenv import load_dotenv

load_dotenv(override=False)

import redis.asyncio as aioredis
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import make_asgi_app

from api.middleware.resilience import (
    CircuitBreakerMiddleware,
    GracefulDegradationMiddleware,
    RetryMiddleware,
    TimeoutMiddleware,
    register_health_score_endpoint,
)
from api.endpoints import router as api_router
from api.system_routes import router as system_router
from api.auth import router as auth_router
from core.config import settings
from core.inference_cache import InferenceCache
from distributed.failover_manager import FailoverManager
from monitoring.log_pipeline import logger, set_correlation_id
from monitoring.model_health import ModelHealthMonitor
from monitoring.prometheus_metrics import start_gpu_telemetry_collector
from monitoring.tracing import DistributedTracer
from orchestration.gpu_execution_controller import GPUExecutionController
from orchestration.gpu_manager import GPUManager
from streaming.websocket_lifecycle import WebSocketLifecycleManager

metrics_app = make_asgi_app()


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("Initializing ArgusLens Enterprise API...")

    # -- Database Tables Self-Healing Initialization --
    try:
        from database.session import engine, Base
        import models.domain  # Wires all models including HealthProfile
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database schemas initialized (self-healing).")
    except Exception as exc:
        logger.error(f"Database schema initialization failed: {exc}")

    # -- Redis client (shared across subsystems) --
    redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True, protocol=2)
    app.state.redis = redis_client

    # -- GPU Execution Controller --
    gpu_ctrl = GPUExecutionController(max_concurrent=3)
    await gpu_ctrl.start()
    app.state.gpu_controller = gpu_ctrl

    # -- WebSocket Lifecycle Manager --
    ws_manager = WebSocketLifecycleManager(
        heartbeat_interval=30.0,
        idle_timeout=300.0,
        max_connections=1000,
    )
    await ws_manager.start()
    app.state.ws_manager = ws_manager

    # -- Failover Manager --
    failover = FailoverManager(redis_client=redis_client)
    await failover.start()
    app.state.failover_manager = failover

    # -- Inference Cache --
    inference_cache = InferenceCache(redis_client=redis_client)
    app.state.inference_cache = inference_cache

    # -- Model Health Monitor --
    app.state.model_health = ModelHealthMonitor()

    # -- Distributed Tracer --
    tracer = DistributedTracer()
    app.state.tracer = tracer

    # -- AI Model preload (non-blocking: instantiate now, load weights in background) --
    try:
        from ai.grounding_dino.inference_engine import GroundingDinoEngine
        import asyncio as _asyncio

        dino_engine = GroundingDinoEngine()
        app.state.dino_engine = dino_engine
        # Load weights in a thread pool so startup is never blocked by a download
        _asyncio.get_event_loop().run_in_executor(None, dino_engine.load)
        logger.info("Grounding DINO engine preload scheduled (non-blocking).")
    except Exception as exc:
        logger.error("Failed to preload Grounding DINO: {}", exc)

    # Pre-warm the /detect pipeline singleton so first request doesn't pay load latency
    try:
        import asyncio as _asyncio
        from api.endpoints import _get_pipeline
        _asyncio.ensure_future(_get_pipeline())
        logger.info("Detect pipeline pre-warm scheduled (non-blocking).")
    except Exception as exc:
        logger.error("Detect pipeline pre-warm failed: {}", exc)

    # -- GPU NVML telemetry (background thread) --
    start_gpu_telemetry_collector(interval_s=5.0)

    # -- Vital Sign Broadcaster Task --
    try:
        from api.vital_routes import start_vital_broadcaster
        import asyncio as _asyncio
        app.state.vital_broadcaster_task = _asyncio.create_task(start_vital_broadcaster())
        logger.info("Vital Sign Broadcaster started successfully (background).")
    except Exception as exc:
        logger.error("Failed to start Vital Sign Broadcaster: {}", exc)

    # -- Phase 3: Intelligence Layer (non-blocking background init) --
    import asyncio as _asyncio

    async def _init_intelligence_bg() -> None:
        """
        Initialise Phase 3 in the background so startup is never blocked by
        SentenceTransformer downloads or database connectivity issues.
        """
        try:
            from intelligence.dependencies import init_intelligence_layer
            from database.session import AsyncSessionLocal

            def _load_st():
                try:
                    from sentence_transformers import SentenceTransformer
                    return SentenceTransformer("all-MiniLM-L6-v2")
                except Exception:
                    return None

            _st_model = await _asyncio.get_event_loop().run_in_executor(None, _load_st)

            async def _embed(text: str) -> list:
                if _st_model is None:
                    return []
                loop = _asyncio.get_event_loop()
                return await loop.run_in_executor(
                    None, lambda: _st_model.encode(text).tolist()
                )

            async with AsyncSessionLocal() as db_session:
                await init_intelligence_layer(redis_client, db_session, _embed)

            app.state.intelligence_ready = True
            logger.info("Phase 3 intelligence layer initialised (background).")
        except Exception as exc:
            logger.error("Intelligence layer background init failed: {}", exc)
            app.state.intelligence_ready = False

    _asyncio.ensure_future(_init_intelligence_bg())
    app.state.intelligence_ready = False  # will be set True by background task

    # -- Phase 4: Adaptive Model Loading + Hardware Profiling --
    hardware_caps = None
    try:
        from model_serving.adaptive_loader import AdaptiveModelLoader
        from model_serving.hardware_profiler import HardwareProfiler
        # Profile hardware synchronously (fast — no downloads)
        hardware_caps = HardwareProfiler().profile()
        adaptive_loader = AdaptiveModelLoader()
        app.state.adaptive_loader = adaptive_loader
        # Load models in background — don't block startup
        async def _init_loader_bg() -> None:
            try:
                caps = await adaptive_loader.initialize()
                logger.info(
                    "Phase 4 adaptive loader ready profile=%s precision=%s",
                    caps.profile.value, caps.recommended_precision.value,
                )
            except Exception as exc:
                logger.error("Adaptive loader background init failed: {}", exc)
        _asyncio.ensure_future(_init_loader_bg())
        logger.info("Phase 4 adaptive loader init scheduled (non-blocking).")
    except Exception as exc:
        logger.error("Adaptive loader failed: {}", exc)
        hardware_caps = None

    # -- Phase 4: Edge Runtime (only when EDGE_NODE=true) --
    try:
        import os
        if os.getenv("EDGE_NODE", "false").lower() == "true":
            from edge.edge_runtime import EdgeRuntime
            from edge.types import InferenceStrategy
            strategy_name = os.getenv("INFERENCE_STRATEGY", "adaptive").upper()
            strategy = InferenceStrategy[strategy_name] if strategy_name in InferenceStrategy.__members__ else InferenceStrategy.ADAPTIVE
            edge_runtime = EdgeRuntime(
                redis_client=redis_client,
                cloud_url=os.getenv("CLOUD_SYNC_URL", ""),
                node_id=os.getenv("NODE_ID", ""),
                strategy=strategy,
                auth_token=os.getenv("EDGE_AUTH_TOKEN", ""),
            )
            if hasattr(app.state, "adaptive_loader"):
                edge_runtime.attach_loader(app.state.adaptive_loader)
            edge_node = await edge_runtime.start(hardware_caps)
            app.state.edge_runtime = edge_runtime
            logger.info("Phase 4 edge runtime started node_id=%s", edge_node.node_id)
        else:
            app.state.edge_runtime = None
    except Exception as exc:
        logger.error("Edge runtime failed: {}", exc)

    # -- Phase 4: Federated Coordinator (when FEDERATED_ENABLED=true) --
    try:
        import os
        if os.getenv("FEDERATED_ENABLED", "false").lower() == "true":
            from federated.federated_coordinator import FederatedCoordinator
            from federated.privacy_layer import PrivacyBudget
            budget = PrivacyBudget(
                epsilon=float(os.getenv("PRIVACY_EPSILON", "1.0")),
                delta=float(os.getenv("PRIVACY_DELTA", "1e-5")),
            )
            fed_coord = FederatedCoordinator(
                redis_client=redis_client,
                model_name="grounding_dino",
                privacy_budget=budget,
                aggregation_method=os.getenv("FEDERATED_AGGREGATION_METHOD", "fedavg"),
            )
            app.state.federated_coordinator = fed_coord
            logger.info("Phase 4 federated coordinator ready")
    except Exception as exc:
        logger.error("Federated coordinator failed: {}", exc)

    # -- Phase 4: Self-Optimization Subsystem --
    try:
        from optimization.self_optimization.performance_analyzer import PerformanceAnalyzer
        from optimization.self_optimization.workload_predictor import WorkloadPredictor
        from optimization.self_optimization.adaptive_scheduler import AdaptiveScheduler
        from optimization.self_optimization.auto_scaler import AutoScaler
        from edge.types import AutonomyLevel
        import os
        autonomy_name = os.getenv("AUTONOMY_LEVEL", "autonomous").upper()
        autonomy = AutonomyLevel[autonomy_name] if autonomy_name in AutonomyLevel.__members__ else AutonomyLevel.AUTONOMOUS

        perf_analyzer = PerformanceAnalyzer()
        workload_predictor = WorkloadPredictor()
        adaptive_scheduler = AdaptiveScheduler(perf_analyzer, workload_predictor, autonomy)
        auto_scaler = AutoScaler(workload_predictor, autonomy_level=autonomy)

        app.state.performance_analyzer = perf_analyzer
        app.state.workload_predictor = workload_predictor
        app.state.adaptive_scheduler = adaptive_scheduler
        app.state.auto_scaler = auto_scaler

        await adaptive_scheduler.start()
        await auto_scaler.start()
        logger.info("Phase 4 self-optimization subsystem started autonomy=%s", autonomy.value)
    except Exception as exc:
        logger.error("Self-optimization failed to start: {}", exc)

    # -- Phase 4: Health Orchestrator + Self-Healing --
    try:
        from autonomy.health_orchestrator import HealthOrchestrator
        from autonomy.self_healing import SelfHealingSystem
        from edge.types import AutonomyLevel
        import os
        autonomy_name = os.getenv("AUTONOMY_LEVEL", "autonomous").upper()
        autonomy = AutonomyLevel[autonomy_name] if autonomy_name in AutonomyLevel.__members__ else AutonomyLevel.AUTONOMOUS

        health_orch = HealthOrchestrator(redis_client)
        self_healing = SelfHealingSystem(redis_client, autonomy_level=autonomy)

        app.state.health_orchestrator = health_orch
        app.state.self_healing = self_healing

        await health_orch.start()
        await self_healing.start()
        logger.info("Phase 4 health orchestrator + self-healing started")
    except Exception as exc:
        logger.error("Health orchestrator failed: {}", exc)

    logger.info("ArgusLens startup complete.")

    yield  # ---- running ----

    # Graceful Shutdown
    logger.info("Initiating graceful shutdown...")

    # -- Phase 4 shutdown --
    for attr in ("self_healing", "health_orchestrator", "adaptive_scheduler", "auto_scaler"):
        component = getattr(app.state, attr, None)
        if component and hasattr(component, "stop"):
            try:
                await component.stop()
            except Exception:
                pass

    vital_task = getattr(app.state, "vital_broadcaster_task", None)
    if vital_task:
        vital_task.cancel()
        try:
            await vital_task
        except Exception:
            pass
        logger.info("Vital Sign Broadcaster task stopped.")

    edge_runtime = getattr(app.state, "edge_runtime", None)
    if edge_runtime:
        try:
            await edge_runtime.stop()
        except Exception:
            pass

    adaptive_loader = getattr(app.state, "adaptive_loader", None)
    if adaptive_loader:
        try:
            await adaptive_loader.shutdown()
        except Exception:
            pass

    # -- Phase 3 shutdown --
    try:
        from intelligence.dependencies import shutdown_intelligence_layer
        await shutdown_intelligence_layer()
    except Exception:
        pass

    await ws_manager.stop()
    await gpu_ctrl.stop()
    await failover.stop()
    await tracer.close()
    await redis_client.aclose()

    # VRAM cleanup
    if hasattr(app.state, "dino_engine"):
        del app.state.dino_engine
    GPUManager.cleanup()

    logger.info("Shutdown complete.")


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.PROJECT_NAME,
        version=settings.VERSION,
        description="ArgusLens Enterprise AI Vision Platform",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # Prometheus metrics endpoint
    app.mount("/metrics", metrics_app)

    # ------------------------------------------------------------------
    # Middleware stack — order matters (outermost = applied last on request,
    # first on response).  We want:
    #   CORS → GracefulDegradation → CircuitBreaker → Timeout → Retry → handler
    # ------------------------------------------------------------------

    # 1. CORS (outermost — always applied)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # tighten to frontend domain in prod
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    # 2. Graceful degradation (returns cached result when inference is down)
    app.add_middleware(GracefulDegradationMiddleware)

    # 3. Circuit breaker (fast-fail on cascading 5xx)
    app.add_middleware(
        CircuitBreakerMiddleware,
        failure_threshold=5,
        recovery_timeout=60.0,
        half_open_max_calls=3,
    )

    # 4. Per-endpoint timeout
    app.add_middleware(TimeoutMiddleware)

    # 5. Retry (transient 503/504 only)
    app.add_middleware(RetryMiddleware, max_retries=3, backoff_factor=0.5)

    # 6. Correlation ID injection (innermost)
    @app.middleware("http")
    async def add_correlation_id(request, call_next):
        cid = request.headers.get("X-Correlation-ID")
        set_correlation_id(cid)
        response = await call_next(request)
        if cid:
            response.headers["X-Correlation-ID"] = cid
        return response

    # ------------------------------------------------------------------
    # Routes
    # ------------------------------------------------------------------

    app.include_router(api_router, prefix=settings.API_V1_STR)
    app.include_router(system_router, prefix=settings.API_V1_STR)
    app.include_router(auth_router, prefix=settings.API_V1_STR)
    from api.vital_routes import router as vital_router
    app.include_router(vital_router, prefix=settings.API_V1_STR)
    from api.chat_routes import router as chat_router
    app.include_router(chat_router, prefix=settings.API_V1_STR)
    from api.profile_routes import router as profile_router
    app.include_router(profile_router, prefix=settings.API_V1_STR)
    register_health_score_endpoint(app)

    # Phase 3: Intelligence + Agent + Knowledge Graph routes
    try:
        from api.v1.intelligence import router as intel_router
        from api.v1.intelligence import agents_router, kg_router
        app.include_router(intel_router)
        app.include_router(agents_router)
        app.include_router(kg_router)
    except ImportError as exc:
        import logging as _log
        _log.getLogger(__name__).warning("Intelligence routes not loaded: %s", exc)

    # Phase 4: Edge, Federated, Autonomy, Optimization routes
    try:
        from api.v1.edge import router as edge_router
        from api.v1.federated import router as fed_router
        from api.v1.autonomy import router as autonomy_router
        from api.v1.optimization import router as opt_router
        app.include_router(edge_router)
        app.include_router(fed_router)
        app.include_router(autonomy_router)
        app.include_router(opt_router)
    except ImportError as exc:
        import logging as _log
        _log.getLogger(__name__).warning("Phase 4 routes not loaded: %s", exc)

    # Legacy health endpoint (kept for backwards compatibility)
    @app.get("/health", tags=["health"])
    def health_check():
        gpu_stats = GPUManager.get_memory_stats()
        return {"status": "healthy", "version": settings.VERSION, "gpu": gpu_stats}

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8090)
