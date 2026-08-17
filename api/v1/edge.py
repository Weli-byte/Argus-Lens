"""
Edge API — Phase 4 endpoints for edge node management.

Endpoints:
  GET  /api/v1/edge/nodes          — list all registered edge nodes
  GET  /api/v1/edge/nodes/{id}     — single node details
  GET  /api/v1/edge/nodes/{id}/stats — runtime stats
  POST /api/v1/edge/ingest         — receive an offline-buffered event from edge
  POST /api/v1/edge/sync/ack       — node acknowledges model sync
  GET  /api/v1/edge/offline/queue  — peek offline event buffer
"""

from __future__ import annotations

import json
import logging
from typing import Any

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/edge", tags=["edge"])


# ---------------------------------------------------------------------------
# Dependency
# ---------------------------------------------------------------------------

async def get_redis(request: Request) -> aioredis.Redis:
    return request.app.state.redis


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class IngestEventRequest(BaseModel):
    node_id: str
    event_id: str
    event_type: str
    payload: dict[str, Any] = {}
    session_id: str = ""
    timestamp: str = ""


class SyncAckRequest(BaseModel):
    sync_id: str
    node_id: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/nodes")
async def list_nodes(redis: aioredis.Redis = Depends(get_redis)) -> dict[str, Any]:
    try:
        node_ids = await redis.smembers("argus:edge:nodes")
        nodes = []
        for node_id in node_ids:
            raw = await redis.get(f"argus:edge:node:{node_id}")
            if raw:
                try:
                    nodes.append(json.loads(raw))
                except json.JSONDecodeError:
                    pass
        return {"nodes": nodes, "count": len(nodes)}
    except Exception as exc:
        logger.error("edge.list_nodes error: %s", exc)
        raise HTTPException(status_code=503, detail="Redis unavailable")


@router.get("/nodes/{node_id}")
async def get_node(
    node_id: str,
    redis: aioredis.Redis = Depends(get_redis),
) -> dict[str, Any]:
    raw = await redis.get(f"argus:edge:node:{node_id}")
    if not raw:
        raise HTTPException(status_code=404, detail="Node not found")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Corrupt node data")


@router.get("/nodes/{node_id}/stats")
async def node_stats(
    node_id: str,
    request: Request,
    redis: aioredis.Redis = Depends(get_redis),
) -> dict[str, Any]:
    raw = await redis.get(f"argus:edge:node:{node_id}")
    if not raw:
        raise HTTPException(status_code=404, detail="Node not found")

    node_data = json.loads(raw)

    # Try to get runtime from app state if this is the local node
    edge_runtime = getattr(request.app.state, "edge_runtime", None)
    if edge_runtime and edge_runtime.node.node_id == node_id:
        try:
            runtime_stats = await edge_runtime.async_stats()
            return {"node": node_data, "runtime": runtime_stats}
        except Exception:
            pass

    return {"node": node_data, "runtime": None}


@router.post("/ingest", status_code=202)
async def ingest_event(
    body: IngestEventRequest,
    redis: aioredis.Redis = Depends(get_redis),
) -> dict[str, Any]:
    """Receive an event buffered by an edge node during offline mode."""
    try:
        # Publish to the appropriate processing channel
        channel = f"argus:edge:ingest:{body.event_type}"
        await redis.publish(channel, json.dumps({
            "node_id": body.node_id,
            "event_id": body.event_id,
            "event_type": body.event_type,
            "payload": body.payload,
            "session_id": body.session_id,
            "timestamp": body.timestamp,
        }))
        return {"accepted": True, "event_id": body.event_id}
    except Exception as exc:
        logger.error("edge.ingest error: %s", exc)
        raise HTTPException(status_code=503, detail="Ingest failed")


@router.post("/sync/ack")
async def sync_ack(
    body: SyncAckRequest,
    redis: aioredis.Redis = Depends(get_redis),
) -> dict[str, Any]:
    """Edge node acknowledges receipt of a model sync update."""
    ack_key = f"argus:fed:ack:{body.sync_id}:{body.node_id}"
    await redis.setex(ack_key, 3600, "1")
    return {"acknowledged": True, "sync_id": body.sync_id}


@router.get("/offline/queue")
async def peek_offline_queue(
    request: Request,
    n: int = 10,
) -> dict[str, Any]:
    """Peek at the offline event buffer for this node."""
    edge_runtime = getattr(request.app.state, "edge_runtime", None)
    if not edge_runtime:
        raise HTTPException(status_code=503, detail="Edge runtime not available")
    events = await edge_runtime._offline_mode.peek(n)
    return {
        "events": [e.to_json() for e in events],
        "count": len(events),
    }
