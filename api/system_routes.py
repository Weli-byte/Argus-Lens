"""
System API routes — exposes GPU, cluster, model, inference queue, worker,
and semantic search data consumed by the ArgusLens frontend.
"""

from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from monitoring.log_pipeline import logger
from orchestration.gpu_manager import GPUManager
from security.jwt_handler import SecurityHandler
from core.auth_manager import auth_manager

router = APIRouter()
security = HTTPBearer(auto_error=False)

# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------


def _get_optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> dict[str, Any] | None:
    if not credentials:
        return None
    try:
        return SecurityHandler.verify_token(credentials)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Auth endpoints
# ---------------------------------------------------------------------------


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    expires_in: int
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


@router.post("/auth/token", response_model=TokenResponse, tags=["auth"])
async def login(request: LoginRequest) -> TokenResponse:
    """POST /auth/token — exchange credentials for JWT tokens."""
    user = auth_manager.verify_user(request.username, request.password)
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = {"sub": user["username"], "role": user["role"], "permissions": user["permissions"]}
    access_token = SecurityHandler.create_access_token(payload)
    refresh_token = SecurityHandler.create_refresh_token(payload)
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=SecurityHandler.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/auth/refresh", response_model=TokenResponse, tags=["auth"])
async def refresh_token(body: RefreshRequest) -> TokenResponse:
    """POST /auth/refresh — rotate tokens using a valid refresh token."""
    try:
        import jwt

        payload = jwt.decode(
            body.refresh_token,
            SecurityHandler.SECRET_KEY,
            algorithms=[SecurityHandler.ALGORITHM],
        )
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid token type")

        new_payload = {
            "sub": payload["sub"],
            "role": payload.get("role", "viewer"),
            "permissions": payload.get("permissions", []),
        }
        access_token = SecurityHandler.create_access_token(new_payload)
        new_refresh = SecurityHandler.create_refresh_token(new_payload)
        return TokenResponse(
            access_token=access_token,
            refresh_token=new_refresh,
            expires_in=SecurityHandler.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )
    except Exception as exc:
        raise HTTPException(status_code=401, detail=str(exc))


# ---------------------------------------------------------------------------
# GPU metrics
# ---------------------------------------------------------------------------


@router.get("/gpu/metrics", tags=["monitoring"])
async def get_gpu_metrics(request: Request) -> dict[str, Any]:
    """GET /gpu/metrics — VRAM, utilisation, temperature for all GPUs."""
    try:
        basic = GPUManager.get_memory_stats()
        controller = getattr(request.app.state, "gpu_controller", None)
        vram_status = controller.get_vram_status() if controller else {}
        queue_depth = controller.get_queue_depth() if controller else {}

        device_info: dict[str, Any] = {
            "device_id": 0,
            "name": basic.get("device", "CPU"),
            "vram_used_mb": vram_status.get("used_mb", basic.get("allocated_gb", 0) * 1024),
            "vram_total_mb": vram_status.get("total_mb", basic.get("total_gb", 0) * 1024),
            "utilization_percent": basic.get("utilization_percent", 0),
            "temperature_celsius": 0,  # populated by NVML if available
        }

        try:
            import pynvml

            pynvml.nvmlInit()
            handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            device_info["temperature_celsius"] = pynvml.nvmlDeviceGetTemperature(
                handle, pynvml.NVML_TEMPERATURE_GPU
            )
            util = pynvml.nvmlDeviceGetUtilizationRates(handle)
            device_info["utilization_percent"] = util.gpu
        except Exception:
            pass

        return {
            "devices": [device_info],
            "total_vram_used_mb": device_info["vram_used_mb"],
            "total_vram_total_mb": device_info["vram_total_mb"],
            "avg_utilization": device_info["utilization_percent"],
            "queue_depth": queue_depth,
        }
    except Exception as exc:
        logger.error("GPU metrics error: {}", exc)
        return {
            "devices": [],
            "total_vram_used_mb": 0,
            "total_vram_total_mb": 0,
            "avg_utilization": 0,
            "queue_depth": {},
        }


# ---------------------------------------------------------------------------
# Inference queue
# ---------------------------------------------------------------------------


@router.get("/inference/queue-status", tags=["monitoring"])
async def get_inference_queue_status(request: Request) -> dict[str, Any]:
    """GET /inference/queue-status — priority queue depths and processing count."""
    controller = getattr(request.app.state, "gpu_controller", None)
    if not controller:
        return {"depth": 0, "priority_counts": {}, "avg_wait_ms": 0, "processing_count": 0}

    queue_depth = controller.get_queue_depth()
    total = sum(queue_depth.values())
    return {
        "depth": total,
        "priority_counts": queue_depth,
        "avg_wait_ms": 0,
        "processing_count": 0,
    }


# ---------------------------------------------------------------------------
# Cluster / worker health
# ---------------------------------------------------------------------------


@router.get("/cluster/health", tags=["monitoring"])
async def get_cluster_health(request: Request) -> dict[str, Any]:
    """GET /cluster/health — full cluster snapshot from FailoverManager."""
    failover = getattr(request.app.state, "failover_manager", None)
    if not failover:
        return {
            "total_workers": 0,
            "healthy_workers": 0,
            "degraded_workers": 0,
            "dead_workers": 0,
            "workers": [],
        }
    try:
        health = await failover.get_cluster_health()
    except Exception as exc:
        logger.warning("cluster_health unavailable (Redis down?): {}", exc)
        return {
            "total_workers": 0,
            "healthy_workers": 0,
            "degraded_workers": 0,
            "dead_workers": 0,
            "cluster_status": "degraded",
            "workers": [],
        }
    # Flatten workers dict to list
    workers_list = [
        {
            "worker_id": wid,
            "state": info.get("state", "idle"),
            "current_load": info.get("current_load", 0) or 0,
            "capabilities": [],
            "active_tasks": 0,
            "queued_tasks": 0,
            "completed_tasks": info.get("inference_count", 0),
            "failed_tasks": info.get("error_count", 0),
            "inference_count": info.get("inference_count", 0),
            "error_count": info.get("error_count", 0),
        }
        for wid, info in health.get("workers", {}).items()
    ]
    total = health.get("total_workers", len(workers_list))
    healthy = health.get("healthy_workers", 0)
    dead = health.get("dead_workers", 0)
    cluster_status = "critical" if healthy == 0 and total > 0 else "degraded" if dead > 0 else "healthy"
    return {
        "total_workers": total,
        "healthy_workers": healthy,
        "degraded_workers": 0,
        "dead_workers": dead,
        "cluster_status": cluster_status,
        "workers": workers_list,
    }


@router.get("/workers", tags=["monitoring"])
async def list_workers(request: Request) -> list[dict[str, Any]]:
    """GET /workers — list all registered workers."""
    cluster = await get_cluster_health(request)
    return cluster["workers"]


# ---------------------------------------------------------------------------
# Model management
# ---------------------------------------------------------------------------


@router.get("/models", tags=["models"])
async def list_models(request: Request) -> list[dict[str, Any]]:
    """GET /models — list all loaded model versions."""
    lifecycle = getattr(request.app.state, "model_lifecycle", None)
    model_health_monitor = getattr(request.app.state, "model_health", None)

    if lifecycle:
        report = lifecycle.get_lifecycle_report()
    else:
        # Return the preloaded DINO engine as a synthetic entry
        report = {
            "grounding_dino": {
                "version_id": "v1.0",
                "model_path": "grounding_dino",
                "loaded_at": time.time(),
                "is_active": True,
                "checksum": "n/a",
                "inference_count": 0,
                "in_flight": 0,
                "has_staging": False,
            }
        }

    models = []
    for model_id, data in report.items():
        health_score = 1.0
        if model_health_monitor:
            hr = model_health_monitor.get_health_report()
            health_score = hr.get(model_id, {}).get("health_score", 1.0)

        models.append(
            {
                "version_id": data.get("version_id", "unknown"),
                "model_id": model_id,
                "model_path": data.get("model_path", ""),
                "loaded_at": data.get("loaded_at", time.time()),
                "inference_count": data.get("inference_count", 0),
                "is_active": data.get("is_active", True),
                "health_score": health_score,
            }
        )
    return models


class ReloadRequest(BaseModel):
    checkpoint_path: str


@router.post("/models/{model_id}/reload", tags=["models"])
async def reload_model(model_id: str, body: ReloadRequest, request: Request) -> dict[str, Any]:
    """POST /models/{model_id}/reload — trigger zero-traffic-drop hot reload."""
    lifecycle = getattr(request.app.state, "model_lifecycle", None)
    if not lifecycle:
        raise HTTPException(status_code=503, detail="Model lifecycle manager not initialized")
    try:
        import importlib

        version = await lifecycle.warm_swap(model_id, body.checkpoint_path, lambda p: None)
        return {"status": "success", "version_id": version.version_id}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ---------------------------------------------------------------------------
# Model health / drift
# ---------------------------------------------------------------------------


@router.get("/monitoring/model-health/{model_id}", tags=["monitoring"])
async def get_model_health(model_id: str, request: Request) -> dict[str, Any]:
    """GET /monitoring/model-health/{model_id} — drift detection and health score."""
    monitor = getattr(request.app.state, "model_health", None)
    if not monitor:
        return {
            "model_id": model_id,
            "health_score": 1.0,
            "confidence_trend": [],
            "drift_detected": False,
            "last_drift_at": None,
        }
    report = monitor.get_health_report()
    data = report.get(model_id, {})
    return {
        "model_id": model_id,
        "health_score": data.get("health_score", 1.0),
        "confidence_trend": [],
        "drift_detected": False,
        "last_drift_at": None,
        "inference_count": data.get("inference_count", 0),
        "error_count": data.get("error_count", 0),
        "avg_latency_ms": data.get("avg_latency_ms", 0),
        "error_rate": data.get("error_rate", 0),
    }


# ---------------------------------------------------------------------------
# Semantic search
# ---------------------------------------------------------------------------


class SearchRequest(BaseModel):
    query: str
    top_k: int = 5
    threshold: float = 0.7
    filter: dict[str, Any] | None = None


@router.post("/embeddings/search", tags=["search"])
async def semantic_search(body: SearchRequest) -> list[dict[str, Any]]:
    """POST /embeddings/search — vector similarity search over contextual memory."""
    try:
        from embeddings.retrieval_engine import RetrievalEngine
        from database.connection_optimizer import optimized_session_factory

        engine = RetrievalEngine()
        async with optimized_session_factory() as db:
            results = await engine.search_similar(db, body.query, limit=body.top_k)

        return [
            {
                "id": str(i),
                "content": r["content"],
                "similarity_score": r["similarity"],
                "metadata": {"session_id": r["session_id"]},
                "timestamp": time.time(),
            }
            for i, r in enumerate(results)
            if r["similarity"] >= body.threshold
        ]
    except Exception as exc:
        logger.error("Semantic search error: {}", exc)
        return []


# ---------------------------------------------------------------------------
# System events (recent log entries)
# ---------------------------------------------------------------------------


@router.get("/system/events", tags=["monitoring"])
async def get_system_events() -> list[dict[str, Any]]:
    """GET /system/events — last 20 system log events from the DB."""
    # Reads from SystemLog table; returns empty list if DB unavailable
    try:
        from database.connection_optimizer import optimized_session_factory
        from sqlalchemy import text

        async with optimized_session_factory() as db:
            result = await db.execute(
                text(
                    "SELECT id, timestamp, level, module, message "
                    "FROM system_logs ORDER BY timestamp DESC LIMIT 20"
                )
            )
            rows = result.fetchall()
            return [
                {
                    "id": str(r.id),
                    "timestamp": r.timestamp.timestamp() if hasattr(r.timestamp, "timestamp") else float(r.timestamp),
                    "level": r.level,
                    "module": r.module,
                    "message": r.message,
                }
                for r in rows
            ]
    except Exception:
        return []
