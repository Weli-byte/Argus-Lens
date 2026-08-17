"""
Intelligence API — Phase 3 endpoints.
All routes use dependency injection via intelligence/dependencies.py.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from intelligence.dependencies import (
    get_multimodal_router,
    get_orchestration_agent,
    get_retrieval_manager,
    get_trace_logger,
)
from intelligence.multimodal_router import MultimodalRouter
from intelligence.types import ReasoningMode
from agents.orchestration_agent import OrchestrationAgent
from explainability.reasoning_trace import ReasoningTraceLogger
from memory.retrieval_manager import RetrievalManager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/intelligence", tags=["intelligence"])
agents_router = APIRouter(prefix="/api/v1/agents", tags=["agents"])
kg_router = APIRouter(prefix="/api/v1/knowledge-graph", tags=["knowledge_graph"])


# ------------------------------------------------------------------
# Request / Response schemas
# ------------------------------------------------------------------


class AnalyzeRequest(BaseModel):
    session_id: str
    vision_result: dict[str, Any] | None = None
    temporal_metrics: dict[str, Any] | None = None
    user_query: str | None = None
    mode: str | None = None


class MemorySearchRequest(BaseModel):
    query: str
    top_k: int = 10
    threshold: float = 0.6
    session_id: str | None = None


class AgentTriggerRequest(BaseModel):
    event_type: str
    event_data: dict[str, Any]
    session_id: str


# ------------------------------------------------------------------
# Intelligence routes
# ------------------------------------------------------------------


@router.post("/analyze")
async def analyze(
    req: AnalyzeRequest,
    router_dep: MultimodalRouter = Depends(get_multimodal_router),
) -> dict[str, Any]:
    """Run the full multimodal intelligence pipeline."""
    try:
        force_mode = ReasoningMode(req.mode) if req.mode else None
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid mode: {req.mode}")

    try:
        result = await router_dep.process(
            session_id=req.session_id,
            vision_result=req.vision_result,
            temporal_metrics=req.temporal_metrics,
            user_query=req.user_query,
            force_mode=force_mode,
        )
        return result
    except Exception as exc:
        logger.error("intelligence.analyze error: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/trace/{trace_id}")
async def get_trace(
    trace_id: str,
    trace_logger: ReasoningTraceLogger = Depends(get_trace_logger),
) -> dict[str, Any]:
    trace = await trace_logger.get_trace(trace_id)
    if not trace:
        raise HTTPException(status_code=404, detail="Trace not found")
    return trace.to_dict()


@router.get("/insights/{session_id}")
async def get_insights(
    session_id: str,
    limit: int = Query(20, ge=1, le=100),
    severity_filter: str | None = None,
    trace_logger: ReasoningTraceLogger = Depends(get_trace_logger),
) -> list[dict[str, Any]]:
    traces = await trace_logger.get_recent_traces(session_id, limit=limit)
    results = []
    for t in traces:
        if t.final_insight:
            d = t.final_insight.to_dict()
            if severity_filter and d.get("severity") != severity_filter:
                continue
            results.append(d)
    return results


@router.get("/memory/{session_id}")
async def get_memory(
    session_id: str,
    type: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    retrieval: RetrievalManager = Depends(get_retrieval_manager),
) -> list[dict[str, Any]]:
    from intelligence.types import MemoryType
    mtype = None
    if type:
        try:
            mtype = MemoryType(type)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid memory type: {type}")

    entries = await retrieval._stm.retrieve_recent(session_id, limit=limit, memory_type=mtype)
    return [e.to_dict() for e in entries]


@router.post("/memory/search")
async def search_memory(
    req: MemorySearchRequest,
    retrieval: RetrievalManager = Depends(get_retrieval_manager),
) -> list[dict[str, Any]]:
    results = await retrieval._ltm.semantic_search(
        query=req.query,
        top_k=req.top_k,
        min_similarity=req.threshold,
        session_id=req.session_id,
    )
    return [
        {**entry.to_dict(), "similarity_score": round(score, 4)}
        for entry, score in results
    ]


@router.get("/correlations/{session_id}")
async def get_correlations(
    session_id: str,
    retrieval: RetrievalManager = Depends(get_retrieval_manager),
) -> dict[str, Any]:
    summary = await retrieval.get_memory_summary(session_id)
    return {"session_id": session_id, "memory_summary": summary}


# ------------------------------------------------------------------
# Agent routes
# ------------------------------------------------------------------


@agents_router.get("/status")
async def agent_status(
    orchestrator: OrchestrationAgent = Depends(get_orchestration_agent),
) -> dict[str, Any]:
    return await orchestrator.get_cluster_status()


@agents_router.post("/trigger")
async def trigger_agent(
    req: AgentTriggerRequest,
    orchestrator: OrchestrationAgent = Depends(get_orchestration_agent),
) -> dict[str, Any]:
    result = await orchestrator.route_event(
        event_type=req.event_type,
        event_data=req.event_data,
        session_id=req.session_id,
    )
    return result


# ------------------------------------------------------------------
# Knowledge graph routes
# ------------------------------------------------------------------


@kg_router.get("/entities")
async def list_entities() -> dict[str, Any]:
    from intelligence.dependencies import get_entity_manager
    em = get_entity_manager()
    counts = await em.count_entities()
    return {"entity_counts": counts}


@kg_router.get("/relations/{entity_id}")
async def get_relations(entity_id: str) -> list[dict[str, Any]]:
    from intelligence.dependencies import get_relation_mapper
    rm = get_relation_mapper()
    return await rm.get_related_entities(entity_id, direction="both")


@kg_router.get("/graph")
async def get_graph() -> dict[str, Any]:
    from intelligence.dependencies import get_graph_memory
    gm = get_graph_memory()
    summary = await gm.get_graph_summary()
    graph_data = gm._relations._graph.export_for_frontend()
    return {**summary, "graph": graph_data}
