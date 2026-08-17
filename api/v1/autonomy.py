"""
Autonomy API — Phase 4 endpoints for self-healing and health orchestration.

Endpoints:
  GET  /api/v1/autonomy/health           — current health status across all probes
  POST /api/v1/autonomy/health/event     — inject a manual health event
  GET  /api/v1/autonomy/healing/stats    — self-healing statistics
  GET  /api/v1/autonomy/healing/decisions — recent autonomous decisions
  GET  /api/v1/autonomy/recovery/log    — recovery action log
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from edge.types import HealthEvent

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/autonomy", tags=["autonomy"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class InjectEventRequest(BaseModel):
    source: str = "api_manual"
    event_type: str
    severity: str = "warning"
    description: str = ""
    affected_components: list[str] = []
    metrics: dict[str, float] = {}
    recoverable: bool = True


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------

def get_healing(request: Request) -> Any:
    healing = getattr(request.app.state, "self_healing", None)
    if healing is None:
        raise HTTPException(status_code=503, detail="Self-healing system not initialized")
    return healing


def get_orchestrator(request: Request) -> Any:
    orch = getattr(request.app.state, "health_orchestrator", None)
    if orch is None:
        raise HTTPException(status_code=503, detail="Health orchestrator not initialized")
    return orch


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/health")
async def health_status(
    orchestrator: Any = Depends(get_orchestrator),
) -> dict[str, Any]:
    return orchestrator.stats()


@router.post("/health/event", status_code=202)
async def inject_event(
    body: InjectEventRequest,
    orchestrator: Any = Depends(get_orchestrator),
) -> dict[str, Any]:
    event = HealthEvent(
        source=body.source,
        event_type=body.event_type,
        severity=body.severity,
        description=body.description,
        affected_components=body.affected_components,
        metrics=body.metrics,
        recoverable=body.recoverable,
    )
    await orchestrator.emit_event(event)
    return {"injected": True, "event_id": event.event_id}


@router.get("/healing/stats")
async def healing_stats(
    healing: Any = Depends(get_healing),
) -> dict[str, Any]:
    return healing.stats()


@router.get("/healing/decisions")
async def healing_decisions(
    n: int = 20,
    healing: Any = Depends(get_healing),
) -> dict[str, Any]:
    return {
        "decisions": healing.recent_decisions(n),
        "count": n,
    }


@router.get("/recovery/log")
async def recovery_log(
    n: int = 20,
    healing: Any = Depends(get_healing),
) -> dict[str, Any]:
    return {
        "log": healing._recovery.recent_log(n),
        "stats": healing._recovery.stats(),
    }
