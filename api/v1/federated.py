"""
Federated Learning API — Phase 4 endpoints.

Endpoints:
  POST /api/v1/federated/register       — register a node for federated rounds
  POST /api/v1/federated/update         — submit a gradient update
  POST /api/v1/federated/round/start    — trigger a federated round (admin)
  GET  /api/v1/federated/round/status   — current round state
  GET  /api/v1/federated/rounds         — history of completed rounds
  POST /api/v1/federated/sync/ack       — node acknowledges model sync
  GET  /api/v1/federated/privacy/stats  — privacy budget consumption
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/federated", tags=["federated"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class RegisterNodeRequest(BaseModel):
    node_id: str
    model_name: str


class GradientUpdateRequest(BaseModel):
    node_id: str
    round_number: int
    model_name: str
    gradient_deltas: dict[str, list[float]] = {}
    n_samples: int
    local_loss: float = 0.0
    local_accuracy: float = 0.0
    noise_applied: bool = False
    privacy_budget_spent: float = 0.0


class StartRoundRequest(BaseModel):
    model_name: str = "grounding_dino"


# ---------------------------------------------------------------------------
# Dependency
# ---------------------------------------------------------------------------

def get_coordinator(request: Request) -> Any:
    coord = getattr(request.app.state, "federated_coordinator", None)
    if coord is None:
        raise HTTPException(status_code=503, detail="Federated coordinator not initialized")
    return coord


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/register")
async def register_node(
    body: RegisterNodeRequest,
    coordinator: Any = Depends(get_coordinator),
) -> dict[str, Any]:
    await coordinator.register_node(body.node_id)
    return {"registered": True, "node_id": body.node_id, "model_name": body.model_name}


@router.post("/update", status_code=202)
async def submit_update(
    body: GradientUpdateRequest,
    coordinator: Any = Depends(get_coordinator),
) -> dict[str, Any]:
    from edge.types import FederatedUpdate
    import uuid

    update = FederatedUpdate(
        update_id=str(uuid.uuid4()),
        node_id=body.node_id,
        round_number=body.round_number,
        model_name=body.model_name,
        gradient_deltas=body.gradient_deltas,
        n_samples=body.n_samples,
        local_loss=body.local_loss,
        local_accuracy=body.local_accuracy,
        noise_applied=body.noise_applied,
        privacy_budget_spent=body.privacy_budget_spent,
    )
    accepted = await coordinator.submit_update(update)
    if not accepted:
        raise HTTPException(
            status_code=409,
            detail=f"Round {body.round_number} not accepting updates (current state: {coordinator._state.value})",
        )
    return {"accepted": True, "update_id": update.update_id}


@router.post("/round/start")
async def start_round(
    body: StartRoundRequest,
    coordinator: Any = Depends(get_coordinator),
) -> dict[str, Any]:
    import asyncio
    # Start round in background task — returns immediately
    asyncio.create_task(coordinator.run_round())
    return {
        "started": True,
        "model_name": body.model_name,
        "round_number": coordinator._current_round + 1,
    }


@router.get("/round/status")
async def round_status(
    coordinator: Any = Depends(get_coordinator),
) -> dict[str, Any]:
    return {
        "current_round": coordinator._current_round,
        "state": coordinator._state.value,
        "model_name": coordinator._model_name,
    }


@router.get("/rounds")
async def round_history(
    limit: int = 20,
    coordinator: Any = Depends(get_coordinator),
) -> dict[str, Any]:
    results = coordinator.round_results[-limit:]
    return {
        "rounds": [r.to_dict() for r in results],
        "total": len(coordinator.round_results),
    }


@router.get("/privacy/stats")
async def privacy_stats(
    coordinator: Any = Depends(get_coordinator),
) -> dict[str, Any]:
    return coordinator._privacy.stats()


@router.get("/stats")
async def federated_stats(
    coordinator: Any = Depends(get_coordinator),
) -> dict[str, Any]:
    return coordinator.stats()
