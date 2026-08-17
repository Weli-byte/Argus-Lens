# ArgusLens Phase 4 — Autonomous AI Ecosystem & Edge Intelligence Network

## What Was Built

Phase 4 transforms ArgusLens from a centralized AI platform into a self-optimizing,
edge-aware, distributed intelligence fabric.  Inspired by Tesla FSD edge architecture
and federated AI systems.

---

## New Files — 33 Python modules + 9 YAML + 2 compose + 1 shell script

```
edge/
  __init__.py          Package marker
  types.py             All Phase 4 shared dataclasses and enums
  local_cache.py       LRU in-memory cache (offline Redis replacement)
  offline_mode.py      Offline state machine + local event buffer (FIFO)
  edge_sync.py         Priority-queue cloud sync with retry + back-off
  edge_scheduler.py    Min-heap adaptive task scheduler, 4-worker pool
  edge_runtime.py      Top-level edge node controller, heartbeat, routing

model_serving/
  __init__.py
  hardware_profiler.py HardwareProfiler: GPU/CPU/RAM detection → HardwareProfile tier
  model_selector.py    ModelSelector: variant registry, VRAM-aware selection
  quantized_runtime.py QuantizedRuntime: PyTorch INT8/FP16 + ONNX async wrapper
  adaptive_loader.py   AdaptiveModelLoader: hot-swap on VRAM pressure (90% threshold)

federated/
  __init__.py
  privacy_layer.py     Gaussian + Laplace DP mechanisms, epsilon accounting
  gradient_aggregator.py FedAvg + FedProx, poisoning detection (z-score)
  model_sync.py        Delta sync via Redis, ACK tracking, 1e-6 threshold filter
  federated_coordinator.py Full round lifecycle: COLLECTING→AGGREGATING→DISTRIBUTING→VALIDATING

autonomy/
  __init__.py
  anomaly_response.py  Playbook executor, per-event action chains
  recovery_engine.py   restart_worker, reload_model, clear_queue, flush_cache, reduce_load
  self_healing.py      Redis pub/sub consumer, cooldown management, escalation
  health_orchestrator.py GPU/CPU/Redis/queue/worker probes every 30s

cognition/
  __init__.py
  shared_context.py    Versioned distributed key-value store via Redis hash
  node_memory_sync.py  Vector-clock-based STM merge across nodes
  distributed_reasoning.py Redis pub/sub multi-node voting → CognitionState consensus

optimization/self_optimization/
  __init__.py
  performance_analyzer.py  p50/p95/p99 rolling windows, EMA baseline, regression alerts
  workload_predictor.py    Holt-Winters double exponential smoothing forecast
  adaptive_scheduler.py    Batch size + concurrency auto-tuning every 30s
  auto_scaler.py           K8s HPA-compatible: min=2, max=20, CPU>70% or queue>80%

api/v1/
  edge.py              8 REST endpoints: node list, stats, ingest, ack, offline queue
  federated.py         7 REST endpoints: register, update, round start/status, history
  autonomy.py          5 REST endpoints: health status, inject event, decisions, log
  optimization.py      7 REST endpoints: performance, forecast, scheduler, hardware, models

deployment/
  k8s/namespace.yaml
  k8s/api-deployment.yaml    RollingUpdate, liveness/readiness probes
  k8s/worker-deployment.yaml GPU toleration, Celery worker
  k8s/hpa.yaml               Dual HPA: CPU + custom queue metric
  k8s/services.yaml          ClusterIP + LoadBalancer
  k8s/configmap.yaml         All Phase 4 env vars
  k8s/pdb.yaml               PodDisruptionBudget (minAvailable=1)
  k8s/networkpolicy.yaml     Ingress/egress locked to known ports
  edge_node_setup.sh         7-step ARM/x86 edge node bootstrap (systemd service)
  edge_docker_compose.yml    Lightweight single-node edge deployment
  multi_node_compose.yml     2 edge + 1 coordinator + Prometheus + Grafana
```

---

## Architecture — Phase 4 Data Flow

```
                    ┌─────────────────────────────────────┐
                    │          ArgusLens Cloud             │
                    │  FederatedCoordinator                │
                    │  HealthOrchestrator                  │
                    │  AutoScaler (K8s HPA)                │
                    └──────────────┬──────────────────────┘
                                   │ Redis pub/sub + REST
              ┌────────────────────┼────────────────────┐
              │                    │                    │
    ┌─────────▼──────┐   ┌────────▼───────┐   ┌───────▼──────┐
    │  Edge Node 1   │   │  Edge Node 2   │   │  Edge Node N  │
    │  EdgeRuntime   │   │  EdgeRuntime   │   │  EdgeRuntime  │
    │  AdaptiveLoader│   │  AdaptiveLoader│   │  AdaptiveLoader│
    │  OfflineMode   │   │  OfflineMode   │   │  OfflineMode  │
    │  EdgeScheduler │   │  EdgeScheduler │   │  EdgeScheduler│
    └────────────────┘   └────────────────┘   └───────────────┘
```

### Self-Healing Flow
```
MonitoringAgent / HealthOrchestrator
        │  publishes HealthEvent to argus:health:events
        ▼
SelfHealingSystem (Redis pubsub consumer)
        │  classifies → checks autonomy level + cooldown
        ▼
AnomalyResponse.respond()
        │  runs playbook actions
        ▼
RecoveryEngine.restart_worker() / reload_model() / clear_queue() / reduce_load()
        │  logs SelfOptimizationDecision
        ▼
Redis PUBLISH argus:health:escalations (for CRITICAL/EMERGENCY)
```

### Federated Learning Round
```
FederatedCoordinator.run_round()
  1. COLLECTING  → broadcast start; wait for FederatedUpdate from nodes
  2. AGGREGATING → GradientAggregator.aggregate() [FedAvg weighted by n_samples]
  3. PRIVACY     → PrivacyLayer.apply_gaussian() [Gaussian noise, epsilon accounting]
  4. DISTRIBUTING → ModelSyncManager.distribute() [delta sync via Redis, ACK tracking]
  5. VALIDATING  → wait_for_acks() [60s timeout]
  6. COMPLETE    → log RoundResult, reset to IDLE
```

---

## Environment Variables Added

| Variable | Default | Description |
|----------|---------|-------------|
| `EDGE_NODE` | `false` | Enable edge runtime for this process |
| `NODE_ID` | hostname | Unique identifier for this edge node |
| `INFERENCE_STRATEGY` | `adaptive` | `edge_first` / `cloud_first` / `edge_only` / `hybrid` |
| `CLOUD_SYNC_URL` | `` | Base URL of cloud coordinator for sync |
| `EDGE_AUTH_TOKEN` | `` | Bearer token for edge→cloud API calls |
| `FEDERATED_ENABLED` | `false` | Enable federated learning coordinator |
| `FEDERATED_AGGREGATION_METHOD` | `fedavg` | `fedavg` or `fedprox` |
| `FEDERATED_MIN_PARTICIPANTS` | `2` | Minimum nodes for a valid federated round |
| `PRIVACY_EPSILON` | `1.0` | Differential privacy epsilon budget |
| `PRIVACY_DELTA` | `1e-5` | Differential privacy delta |
| `AUTONOMY_LEVEL` | `autonomous` | `supervised` / `semi_auto` / `autonomous` / `emergency` |

---

## New Prometheus Metrics (namespace: arguslens_edge_* / arguslens_fed_* / arguslens_auto_*)

| Metric | Type | Labels |
|--------|------|--------|
| `arguslens_edge_nodes_online` | Gauge | — |
| `arguslens_edge_offline_queue_depth` | Gauge | node_id |
| `arguslens_edge_sync_latency_seconds` | Histogram | node_id |
| `arguslens_edge_inference_requests_total` | Counter | node_id, model_name, strategy |
| `arguslens_fed_rounds_total` | Counter | model_name, outcome |
| `arguslens_fed_round_duration_seconds` | Histogram | model_name |
| `arguslens_fed_participants_total` | Gauge | model_name |
| `arguslens_fed_privacy_epsilon_spent` | Gauge | model_name |
| `arguslens_auto_healing_events_total` | Counter | event_type, severity, outcome |
| `arguslens_auto_scaler_replicas` | Gauge | deployment |
| `arguslens_auto_scaler_scale_events_total` | Counter | deployment, direction |
| `arguslens_model_precision_active` | Gauge | model_name |
| `arguslens_cognition_consensus_score` | Histogram | — |

---

## New WebSocket Message Types (8 added to IntelligenceStreamBroadcaster)

```json
{"type": "edge_node_update",        "payload": {"node_id":"..","state":"online"}}
{"type": "federated_round_update",  "payload": {"round_number":3,"state":"aggregating","model_name":"..","participants":5}}
{"type": "self_healing_action",     "payload": {"event_type":"worker_crash","action_taken":"restart_worker","success":true}}
{"type": "scale_event",             "payload": {"direction":"up","from_replicas":2,"to_replicas":4,"trigger":"cpu=0.78"}}
{"type": "offline_mode_change",     "payload": {"node_id":"edge-1","offline":true}}
{"type": "model_downgrade",         "payload": {"model_name":"grounding_dino","from_precision":"fp16","to_precision":"int8","reason":"vram_pressure"}}
{"type": "consensus_reached",       "payload": {"session_id":"..","agreement_score":0.87,"participant_count":3,"reasoning_summary":"..."}}
{"type": "performance_regression",  "payload": {"component":"inference","metric":"p95_latency_ms","current_value":450,"baseline_value":120,"ratio":3.75}}
```

---

## How to Test

### 1. Pure-Python components (no infrastructure needed)
```bash
python -c "
from edge.types import EdgeNode, HardwareProfile, EdgeNodeState
n = EdgeNode(hostname='test-node')
n.hardware_profile = HardwareProfile.WORKSTATION
n.state = EdgeNodeState.ONLINE
print(n.to_dict())
"

python -c "
from optimization.self_optimization.workload_predictor import WorkloadPredictor
p = WorkloadPredictor()
for i in range(35):
    p.observe(i * 5 + 10, elapsed_s=30)
fc = p.forecast(steps_ahead=3)
print(fc.to_dict())
"

python -c "
from federated.gradient_aggregator import GradientAggregator
from edge.types import FederatedUpdate
agg = GradientAggregator()
updates = [
    FederatedUpdate(node_id='n1', n_samples=100, gradient_deltas={'layer1': [0.1, -0.2, 0.3]}),
    FederatedUpdate(node_id='n2', n_samples=200, gradient_deltas={'layer1': [0.2, -0.1, 0.4]}),
]
result = agg.aggregate(updates)
print(result)
"
```

### 2. Hardware profiler
```bash
python -c "
from model_serving.hardware_profiler import HardwareProfiler
caps = HardwareProfiler().profile()
print(caps.to_dict())
"
```

### 3. API endpoints (requires running server)
```bash
# Edge nodes
curl http://localhost:8000/api/v1/edge/nodes

# Federated learning status
curl http://localhost:8000/api/v1/federated/round/status

# Autonomy / self-healing
curl http://localhost:8000/api/v1/autonomy/healing/stats

# Performance metrics
curl http://localhost:8000/api/v1/optimization/performance

# Hardware profile
curl http://localhost:8000/api/v1/optimization/hardware

# Trigger a federated round
curl -X POST http://localhost:8000/api/v1/federated/round/start \
  -H "Content-Type: application/json" -d '{"model_name":"grounding_dino"}'

# Inject a health event
curl -X POST http://localhost:8000/api/v1/autonomy/health/event \
  -H "Content-Type: application/json" \
  -d '{"event_type":"queue_overflow","severity":"warning","description":"Queue at 600 items"}'
```

### 4. Multi-node local test
```bash
cd deployment
docker compose -f multi_node_compose.yml up -d
# coordinator: http://localhost:8000
# edge-node-1: http://localhost:8001
# edge-node-2: http://localhost:8002
# grafana:     http://localhost:3001
```

### 5. Edge node setup (Linux)
```bash
sudo bash deployment/edge_node_setup.sh --cloud-url http://cloud:8000 --node-id edge-prod-01
systemctl start arguslens-edge
journalctl -u arguslens-edge -f
```

---

## Next Steps

1. **LLM-augmented reasoning** — plug an LLM into `ReasoningEngine` + `DistributedReasoning` for natural-language consensus summaries
2. **Granger causality calibration** — tune `max_lag` and p-value thresholds after accumulating real temporal data
3. **Frontend Phase 4 pages** — edge node topology map, federated round timeline, self-healing audit trail
4. **Model registry** — store trained model variants in S3/MinIO; AdaptiveModelLoader pulls on demand
5. **mTLS between edge and cloud** — replace bearer tokens with mutual TLS for zero-trust edge-cloud auth
6. **Federated round scheduling** — cron-based triggers via existing CronCreate infrastructure
