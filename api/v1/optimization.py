"""
Optimization API — Phase 4 endpoints for self-optimization subsystem.

Endpoints:
  GET  /api/v1/optimization/performance         — per-component performance summaries
  GET  /api/v1/optimization/performance/alerts  — recent regression alerts
  GET  /api/v1/optimization/workload/forecast   — predicted request rate
  GET  /api/v1/optimization/scheduler/config    — current adaptive scheduler config
  GET  /api/v1/optimization/scheduler/decisions — recent scheduling decisions
  GET  /api/v1/optimization/autoscaler/stats    — auto-scaler state
  GET  /api/v1/optimization/hardware            — detected hardware profile
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/optimization", tags=["optimization"])


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------

def get_analyzer(request: Request) -> Any:
    a = getattr(request.app.state, "performance_analyzer", None)
    if a is None:
        raise HTTPException(status_code=503, detail="PerformanceAnalyzer not initialized")
    return a


def get_predictor(request: Request) -> Any:
    p = getattr(request.app.state, "workload_predictor", None)
    if p is None:
        raise HTTPException(status_code=503, detail="WorkloadPredictor not initialized")
    return p


def get_scheduler(request: Request) -> Any:
    s = getattr(request.app.state, "adaptive_scheduler", None)
    if s is None:
        raise HTTPException(status_code=503, detail="AdaptiveScheduler not initialized")
    return s


def get_scaler(request: Request) -> Any:
    sc = getattr(request.app.state, "auto_scaler", None)
    if sc is None:
        raise HTTPException(status_code=503, detail="AutoScaler not initialized")
    return sc


def get_loader(request: Request) -> Any:
    loader = getattr(request.app.state, "adaptive_loader", None)
    if loader is None:
        raise HTTPException(status_code=503, detail="AdaptiveModelLoader not initialized")
    return loader


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/performance")
async def performance_summary(
    analyzer: Any = Depends(get_analyzer),
) -> dict[str, Any]:
    return {"summaries": analyzer.all_summaries()}


@router.get("/performance/alerts")
async def performance_alerts(
    n: int = 20,
    analyzer: Any = Depends(get_analyzer),
) -> dict[str, Any]:
    return {"alerts": analyzer.recent_alerts(n)}


@router.get("/workload/forecast")
async def workload_forecast(
    steps: int = 3,
    predictor: Any = Depends(get_predictor),
) -> dict[str, Any]:
    forecast = predictor.forecast(steps_ahead=steps)
    return forecast.to_dict()


@router.get("/scheduler/config")
async def scheduler_config(
    scheduler: Any = Depends(get_scheduler),
) -> dict[str, Any]:
    return scheduler.config.to_dict()


@router.get("/scheduler/decisions")
async def scheduler_decisions(
    n: int = 10,
    scheduler: Any = Depends(get_scheduler),
) -> dict[str, Any]:
    return {"decisions": scheduler.recent_decisions(n)}


@router.get("/autoscaler/stats")
async def autoscaler_stats(
    scaler: Any = Depends(get_scaler),
) -> dict[str, Any]:
    return scaler.stats()


@router.get("/hardware")
async def hardware_profile(
    loader: Any = Depends(get_loader),
) -> dict[str, Any]:
    caps = loader.capabilities
    if caps is None:
        raise HTTPException(status_code=503, detail="Hardware not profiled yet")
    return caps.to_dict()


@router.get("/models")
async def model_status(
    loader: Any = Depends(get_loader),
) -> dict[str, Any]:
    return loader.status()
