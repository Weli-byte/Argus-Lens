"""
Dependency injection singletons for the intelligence layer.
FastAPI `Depends()` factories that return shared instances.
All singletons are initialised during app startup via init_intelligence_layer().
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level singletons (populated by init_intelligence_layer)
# ---------------------------------------------------------------------------

_stm: Any = None
_ltm: Any = None
_retrieval: Any = None
_ctx_mgr: Any = None
_reasoning: Any = None
_multimodal: Any = None
_orchestrator: Any = None
_trace_logger: Any = None
_entity_mgr: Any = None
_relation_mapper: Any = None
_graph_memory: Any = None


def get_short_term_memory():
    if _stm is None:
        raise RuntimeError("Intelligence layer not initialised — call init_intelligence_layer() first")
    return _stm


def get_long_term_memory():
    if _ltm is None:
        raise RuntimeError("Intelligence layer not initialised")
    return _ltm


def get_retrieval_manager():
    if _retrieval is None:
        raise RuntimeError("Intelligence layer not initialised")
    return _retrieval


def get_context_manager():
    if _ctx_mgr is None:
        raise RuntimeError("Intelligence layer not initialised")
    return _ctx_mgr


def get_reasoning_engine():
    if _reasoning is None:
        raise RuntimeError("Intelligence layer not initialised")
    return _reasoning


def get_multimodal_router():
    if _multimodal is None:
        raise RuntimeError("Intelligence layer not initialised")
    return _multimodal


def get_orchestration_agent():
    if _orchestrator is None:
        raise RuntimeError("Intelligence layer not initialised")
    return _orchestrator


def get_trace_logger():
    if _trace_logger is None:
        raise RuntimeError("Intelligence layer not initialised")
    return _trace_logger


def get_entity_manager():
    if _entity_mgr is None:
        raise RuntimeError("Intelligence layer not initialised")
    return _entity_mgr


def get_relation_mapper():
    if _relation_mapper is None:
        raise RuntimeError("Intelligence layer not initialised")
    return _relation_mapper


def get_graph_memory():
    if _graph_memory is None:
        raise RuntimeError("Intelligence layer not initialised")
    return _graph_memory


# ---------------------------------------------------------------------------
# Initialisation (called from main.py startup)
# ---------------------------------------------------------------------------


async def init_intelligence_layer(
    redis_client: Any,
    db_session: Any,
    embedding_fn: Any,
) -> None:
    """
    Bootstrap all intelligence layer singletons.
    Call once during FastAPI lifespan startup.
    """
    global _stm, _ltm, _retrieval, _ctx_mgr, _reasoning
    global _multimodal, _orchestrator, _trace_logger
    global _entity_mgr, _relation_mapper, _graph_memory

    from memory.short_term_memory import ShortTermMemory
    from memory.long_term_memory import LongTermMemory
    from memory.retrieval_manager import RetrievalManager
    from intelligence.context_manager import IntelligenceContextManager
    from intelligence.anomaly_explainer import AnomalyExplainer
    from intelligence.semantic_correlator import SemanticCorrelator
    from intelligence.insight_generator import InsightGenerator
    from intelligence.reasoning_engine import ReasoningEngine
    from intelligence.recommendation_engine import RecommendationEngine
    from intelligence.multimodal_router import MultimodalRouter
    from agents.vision_agent import VisionAgent
    from agents.temporal_agent import TemporalAgent
    from agents.anomaly_agent import AnomalyAgent
    from agents.monitoring_agent import MonitoringAgent
    from agents.orchestration_agent import OrchestrationAgent
    from explainability.reasoning_trace import ReasoningTraceLogger
    from correlation.event_graph import EventGraph
    from knowledge_graph.entity_manager import EntityManager
    from knowledge_graph.relation_mapper import RelationMapper
    from knowledge_graph.graph_memory import GraphMemory

    # Memory layer
    _stm = ShortTermMemory(redis_client)
    _ltm = LongTermMemory(db_session, embedding_fn)
    _retrieval = RetrievalManager(_stm, _ltm)

    # Intelligence engine
    _ctx_mgr = IntelligenceContextManager(_retrieval)
    _anomaly_explainer = AnomalyExplainer()
    _semantic_correlator = SemanticCorrelator(embedding_fn, _ltm)
    _insight_gen = InsightGenerator(_anomaly_explainer, _semantic_correlator)
    _reasoning = ReasoningEngine(_ctx_mgr, _insight_gen, _anomaly_explainer, _retrieval)
    _rec_engine = RecommendationEngine(_ltm, _retrieval)
    _multimodal = MultimodalRouter(_ctx_mgr, _reasoning, _rec_engine, _retrieval, _stm)

    # Trace logger
    _trace_logger = ReasoningTraceLogger(redis_client, db_session)

    # Knowledge graph
    _event_graph = EventGraph()
    _entity_mgr = EntityManager(redis_client)
    _relation_mapper = RelationMapper(_entity_mgr, _event_graph, redis_client)
    _graph_memory = GraphMemory(_entity_mgr, _relation_mapper, _ltm)

    # Agent system
    _vision_agent = VisionAgent("vision-01", redis_client, _multimodal, _stm)
    _anomaly_agent = AnomalyAgent("anomaly-01", redis_client, _multimodal, _retrieval, _ltm)
    _temporal_agent = TemporalAgent("temporal-01", redis_client, _multimodal, _retrieval)
    _monitoring_agent = MonitoringAgent("monitor-01", redis_client, _multimodal)
    _orchestrator = OrchestrationAgent(
        "orch-01", redis_client,
        _vision_agent, _temporal_agent, _anomaly_agent, _monitoring_agent,
    )

    logger.info("intelligence_layer.init complete — all singletons ready")


async def shutdown_intelligence_layer() -> None:
    """Graceful shutdown called from main.py lifespan teardown."""
    if _orchestrator is not None:
        await _orchestrator.stop()
    logger.info("intelligence_layer.shutdown complete")
