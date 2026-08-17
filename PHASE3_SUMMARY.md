# ArgusLens Phase 3 — Multimodal AI Intelligence & Agentic Reasoning Platform

## What Was Built

Phase 3 adds a full intelligence layer on top of the existing ArgusLens inference and monitoring stack.
It converts raw vision detections, temporal biometric metrics, and system telemetry into:

- **Traceable AI insights** (severity-ranked, confidence-scored)
- **Autonomous agent behaviour** (multi-source validation, escalation, monitoring)
- **Persistent semantic memory** (STM via Redis, LTM via pgvector)
- **Event correlation and causality** (lag-based, Granger causality)
- **Knowledge graph** (entity and relation tracking)
- **Human-readable explainability** (every decision step is logged)

---

## New Files — 35 Python modules

```
intelligence/
  types.py               Shared dataclasses and enums for entire Phase 3
  context_manager.py     Assembles ReasoningContext from multimodal sources
  reasoning_engine.py    Core reasoning loop — pattern detection, risk scoring
  insight_generator.py   Converts analysis into structured AIInsight objects
  anomaly_explainer.py   Explains vision and temporal anomalies (z-score, causes)
  semantic_correlator.py Embedding-based event correlation and drift detection
  recommendation_engine.py LTM-backed actionable recommendation generation
  multimodal_router.py   Main entry point — orchestrates the full pipeline
  dependencies.py        FastAPI DI singletons + startup/shutdown hooks

memory/
  short_term_memory.py   Redis TTL-based, 15-min session working memory
  long_term_memory.py    PostgreSQL + pgvector persistent semantic memory
  context_window.py      Token-budget-aware context assembly for reasoning
  retrieval_manager.py   STM + LTM coordinator with recency-weighted ranking

agents/
  base_agent.py          asyncio.Queue state machine, logging, Redis state pub
  vision_agent.py        Processes inference results, escalates critical insights
  temporal_agent.py      Sliding-window temporal analysis and 60s forecasting
  anomaly_agent.py       Multi-source cross-validation and LTM outcome tracking
  monitoring_agent.py    Periodic (30s) system health probes — GPU, queue, workers
  orchestration_agent.py Starts/stops all agents, routes events by type

correlation/
  temporal_correlator.py Lag-based Pearson correlation, recurring sequence detection
  anomaly_correlator.py  Temporal clustering, composite severity, root cause
  event_graph.py         networkx DiGraph of events with centrality analysis
  causality_engine.py    Granger causality test (statsmodels or lag-correlation fallback)

explainability/
  reasoning_trace.py     Redis-backed full audit trail for every reasoning step
  inference_explainer.py Explains detection confidence and confidence drops
  temporal_explainer.py  Z-score narratives, trend explanations, forecast text

knowledge_graph/
  entity_manager.py      Redis-backed entity CRUD with type index
  relation_mapper.py     Directed relation management (Redis + EventGraph)
  graph_memory.py        Learns entity relations from observed events

api/v1/intelligence.py           11 REST endpoints (analyze, trace, memory, agents, KG)
streaming/intelligence_broadcaster.py  WS severity filtering + per-session routing
monitoring/prometheus_metrics.py       +10 arguslens_intel_* metrics added
```

---

## Architecture — Data Flow

```
Camera / Sensor Input
        |
        v
  GroundingDINO          TemporalTransformer
  (vision_result)        (temporal_metrics)
        |                      |
        +----------+-----------+
                   |
                   v
         MultimodalRouter.process()
                   |
          +--------+--------+
          |                 |
          v                 v
  IntelligenceContextManager    RetrievalManager
  (build ReasoningContext)       (STM lookup)
          |                          |
          +----------+---------------+
                     |
                     v
             ReasoningEngine.reason()
             +--------------------------+
             | _detect_critical_patterns| <- rule-based checks (6 patterns)
             | _apply_temporal_reasoning| <- trend + 60s forecast
             | _calculate_risk_score    | <- weighted severity score
             +--------------------------+
                     |
                     v
           InsightGenerator.generate()
                     |
                     v
         RecommendationEngine.generate_recommendations()
                     |
         +-----------+-----------+
         |           |           |
         v           v           v
    STM.store()  LTM.consolidate  WS.broadcast_insight()
    (Redis)      (if CRITICAL+)   (IntelligenceStreamBroadcaster)
                     |
                     v
              REST API Response
         {insight, recommendations, trace_id, processing_ms}
```

### Agent Event Flow

```
External Event (vision / temporal / system)
        |
        v
  OrchestrationAgent.route_event()
        |
  +-----------+-----------+------------------+
  |           |           |                  |
  v           v           v                  v
VisionAgent  TemporalAgent  AnomalyAgent  MonitoringAgent
  |              |            |              |
  v              v            v              v
MultimodalRouter (each agent calls process() internally)
```

---

## Component Connection Map

| Component | Depends On | Called By |
|-----------|-----------|-----------|
| MultimodalRouter | ContextManager, ReasoningEngine, RecommendationEngine, STM | VisionAgent, TemporalAgent, API |
| ReasoningEngine | ContextManager, InsightGenerator, AnomalyExplainer, RetrievalManager | MultimodalRouter |
| InsightGenerator | AnomalyExplainer, SemanticCorrelator | ReasoningEngine |
| RetrievalManager | ShortTermMemory, LongTermMemory | ContextManager, AnomalyAgent |
| OrchestrationAgent | VisionAgent, TemporalAgent, AnomalyAgent, MonitoringAgent | main.py startup |
| AnomalyAgent | MultimodalRouter, RetrievalManager, LongTermMemory | OrchestrationAgent (escalation path) |
| CausalityEngine | TemporalCorrelator | AnomalyCorrelator |
| EventGraph | networkx | RelationMapper, AnomalyCorrelator |
| GraphMemory | EntityManager, RelationMapper, LongTermMemory | API /knowledge-graph |

---

## How to Test Each Component

### 1. Types (no deps)
```bash
python -c "
from intelligence.types import ReasoningContext, AIInsight, InsightSeverity
ctx = ReasoningContext(session_id='s1')
ctx.add_trace('step1')
ins = AIInsight(title='Test', severity=InsightSeverity.CRITICAL, confidence=0.9)
print(ins.to_dict())
"
```

### 2. EventGraph (networkx only)
```bash
python -c "
from correlation.event_graph import EventGraph
g = EventGraph()
g.add_event('a', {'type': 'fatigue_spike'})
g.add_event('b', {'type': 'blink_drop'})
g.add_relation('a','b','causes',0.85)
print(g.find_paths('a','b'))  # [['a','b']]
print(g.stats())
"
```

### 3. AnomalyExplainer (pure Python)
```bash
python -c "
import asyncio
from intelligence.anomaly_explainer import AnomalyExplainer
from intelligence.types import ReasoningContext
ex = AnomalyExplainer()
ctx = ReasoningContext(session_id='test')
result = asyncio.run(ex.explain_temporal_anomaly('fatigue_score', 0.92, 0.45, 0.08, ctx))
print(result)
"
```

### 4. Full pipeline (requires running Redis + PostgreSQL)
```bash
curl -X POST http://localhost:8000/api/v1/intelligence/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "test-session",
    "temporal_metrics": {"fatigue_score": 0.88, "focus_score": 0.22, "cognitive_load": 0.91},
    "vision_result": {"detections": [{"label": "person", "confidence": 0.91, "bbox": {"x1":0.1,"y1":0.1,"x2":0.4,"y2":0.9}}]}
  }'
```

### 5. Agent status
```bash
curl http://localhost:8000/api/v1/agents/status
```

### 6. Trigger an event
```bash
curl -X POST http://localhost:8000/api/v1/agents/trigger \
  -H "Content-Type: application/json" \
  -d '{"event_type":"vision_result","event_data":{"vision_result":{}},"session_id":"s1"}'
```

### 7. Knowledge graph
```bash
curl http://localhost:8000/api/v1/knowledge-graph/graph
```

---

## WebSocket Intelligence Messages

Connect to `ws://localhost:8000/ws/{session_id}` and expect:

```json
{"type": "ai_insight",        "payload": { ...AIInsight fields... }}
{"type": "agent_update",      "payload": {"agent_id":"..","state":"acting","current_task":"..."}}
{"type": "correlation_found", "payload": { ...CorrelationResult fields... }}
{"type": "memory_consolidated","payload": {"session_id":"..","count":5,"important_patterns":[]}}
{"type": "knowledge_graph_update","payload":{"entities_added":2,"relations_added":3}}
```

Severity routing:
- INFO / NOTICE → batched, max 1 per 5 seconds
- WARNING → immediate to session
- CRITICAL / EMERGENCY → immediate to session + broadcast to all sessions

---

## Prometheus Metrics Added

All use `arguslens_intel_*` namespace to avoid collision with existing metrics.

| Metric | Type | Labels |
|--------|------|--------|
| `arguslens_intel_reasoning_duration_seconds` | Histogram | mode, severity |
| `arguslens_intel_memory_lookup_duration_seconds` | Histogram | memory_type |
| `arguslens_intel_insights_generated_total` | Counter | severity |
| `arguslens_intel_agent_task_duration_seconds` | Histogram | agent_type |
| `arguslens_intel_agent_queue_depth` | Gauge | agent_type |
| `arguslens_intel_correlation_found_total` | Counter | strength |
| `arguslens_intel_memory_entries_total` | Gauge | memory_type |
| `arguslens_intel_memory_consolidation_total` | Counter | — |
| `arguslens_intel_knowledge_graph_entities_total` | Gauge | — |
| `arguslens_intel_reasoning_confidence_score` | Histogram | — |

---

## Next Steps

1. **LTM schema migration** — run Alembic to create `ltm_memories` table with pgvector column
2. **Wire IntelligenceStreamBroadcaster** into websocket.py endpoint and inject via `MultimodalRouter.set_broadcaster()`
3. **Frontend Phase 3 pages** — `/intelligence` dashboard showing real-time AIInsight stream, trace viewer, knowledge graph visualiser
4. **Pattern expansion** — add more patterns to `_PATTERN_REGISTRY` in `reasoning_engine.py` as domain knowledge grows
5. **LLM integration hook** — `ReasoningEngine.reason()` has a clean extension point; replace/augment deterministic patterns with LLM-generated reasoning
6. **Granger test tuning** — once real temporal data accumulates, calibrate `max_lag` and p-value threshold per metric
