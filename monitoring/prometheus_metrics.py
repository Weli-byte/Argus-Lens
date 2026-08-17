"""
Prometheus metrics registry for ArgusLens.
All metric objects are singletons — import them by name wherever needed.
"""

from __future__ import annotations

import threading

from prometheus_client import Counter, Gauge, Histogram

# ---------------------------------------------------------------------------
# Original metrics (unchanged)
# ---------------------------------------------------------------------------

INFERENCE_LATENCY = Histogram(
    "arguslens_inference_latency_seconds",
    "Time spent processing inference request",
    ["model_name", "device"],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
)

ACTIVE_WEBSOCKETS = Gauge(
    "arguslens_active_websockets",
    "Number of currently active websocket connections",
)

GPU_MEMORY_ALLOCATED = Gauge(
    "arguslens_gpu_memory_allocated_bytes",
    "Currently allocated GPU memory in bytes",
    ["device_id"],
)

API_REQUESTS = Counter(
    "arguslens_api_requests_total",
    "Total number of API requests received",
    ["endpoint", "method", "status_code"],
)

DROPPED_FRAMES = Counter(
    "arguslens_dropped_frames_total",
    "Total number of dropped frames due to backpressure",
)

# ---------------------------------------------------------------------------
# GPU Telemetry (nvidia-ml-py3 / pynvml)
# ---------------------------------------------------------------------------

GPU_VRAM_USED_MB = Gauge(
    "arguslens_gpu_vram_used_mb",
    "VRAM currently allocated (MB)",
    ["device_id"],
)

GPU_VRAM_TOTAL_MB = Gauge(
    "arguslens_gpu_vram_total_mb",
    "Total VRAM capacity (MB)",
    ["device_id"],
)

GPU_UTILIZATION_PERCENT = Gauge(
    "arguslens_gpu_utilization_percent",
    "GPU SM utilization percentage",
    ["device_id"],
)

GPU_TEMPERATURE_CELSIUS = Gauge(
    "arguslens_gpu_temperature_celsius",
    "GPU temperature in Celsius",
    ["device_id"],
)

# ---------------------------------------------------------------------------
# Queue Metrics
# ---------------------------------------------------------------------------

INFERENCE_QUEUE_DEPTH_BY_PRIORITY = Gauge(
    "arguslens_inference_queue_depth_by_priority",
    "Number of items in the inference priority queue",
    ["priority"],
)

CELERY_QUEUE_DEPTH = Gauge(
    "arguslens_celery_queue_depth",
    "Number of tasks waiting in Celery queues",
    ["queue_name"],
)

WEBSOCKET_MESSAGE_QUEUE_DEPTH = Gauge(
    "arguslens_websocket_message_queue_depth",
    "Number of outbound messages pending in WebSocket queues",
    ["session_id"],
)

# ---------------------------------------------------------------------------
# Live Inference Metrics
# ---------------------------------------------------------------------------

INFERENCE_ACTIVE_COUNT = Gauge(
    "arguslens_inference_active_count",
    "Number of inference requests currently being processed",
)

INFERENCE_PER_SECOND = Gauge(
    "arguslens_inference_per_second",
    "Inference throughput (rolling 1-minute rate)",
)

INFERENCE_SUCCESS_RATE_5M = Gauge(
    "arguslens_inference_success_rate_5m",
    "Fraction of successful inferences over the last 5 minutes",
)

# ---------------------------------------------------------------------------
# GPU Telemetry collector (background thread, optional)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Phase 3 — Intelligence Layer Metrics (namespace: arguslens_intel_*)
# ---------------------------------------------------------------------------

INTEL_REASONING_DURATION = Histogram(
    "arguslens_intel_reasoning_duration_seconds",
    "Time spent executing the reasoning pipeline",
    ["mode", "severity"],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
)

INTEL_MEMORY_LOOKUP_DURATION = Histogram(
    "arguslens_intel_memory_lookup_duration_seconds",
    "Time spent retrieving memories (STM/LTM)",
    ["memory_type"],
    buckets=[0.005, 0.01, 0.05, 0.1, 0.25, 0.5],
)

INTEL_INSIGHTS_GENERATED = Counter(
    "arguslens_intel_insights_generated_total",
    "Total AI insights generated",
    ["severity"],
)

INTEL_AGENT_TASK_DURATION = Histogram(
    "arguslens_intel_agent_task_duration_seconds",
    "Time spent executing an agent task",
    ["agent_type"],
    buckets=[0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)

INTEL_AGENT_QUEUE_DEPTH = Gauge(
    "arguslens_intel_agent_queue_depth",
    "Current depth of each agent's task queue",
    ["agent_type"],
)

INTEL_CORRELATION_FOUND = Counter(
    "arguslens_intel_correlation_found_total",
    "Total event correlations detected",
    ["strength"],
)

INTEL_MEMORY_ENTRIES = Gauge(
    "arguslens_intel_memory_entries_total",
    "Current number of memory entries",
    ["memory_type"],
)

INTEL_MEMORY_CONSOLIDATIONS = Counter(
    "arguslens_intel_memory_consolidation_total",
    "Total short-term→long-term memory consolidations",
)

INTEL_KNOWLEDGE_GRAPH_ENTITIES = Gauge(
    "arguslens_intel_knowledge_graph_entities_total",
    "Total entities in the knowledge graph",
)

INTEL_REASONING_CONFIDENCE = Histogram(
    "arguslens_intel_reasoning_confidence_score",
    "Distribution of insight confidence scores",
    buckets=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
)


# ---------------------------------------------------------------------------
# Phase 4 — Edge / Federated / Autonomy Metrics
# ---------------------------------------------------------------------------

EDGE_NODES_ONLINE = Gauge(
    "arguslens_edge_nodes_online",
    "Number of edge nodes currently in ONLINE state",
)

EDGE_OFFLINE_QUEUE_DEPTH = Gauge(
    "arguslens_edge_offline_queue_depth",
    "Total buffered events across all offline edge nodes",
    ["node_id"],
)

EDGE_SYNC_LATENCY = Histogram(
    "arguslens_edge_sync_latency_seconds",
    "Time taken to sync buffered events from edge to cloud",
    ["node_id"],
    buckets=[0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0],
)

EDGE_INFERENCE_REQUESTS = Counter(
    "arguslens_edge_inference_requests_total",
    "Total inference requests processed by edge nodes",
    ["node_id", "model_name", "strategy"],
)

FEDERATED_ROUNDS_TOTAL = Counter(
    "arguslens_fed_rounds_total",
    "Total federated learning rounds completed",
    ["model_name", "outcome"],
)

FEDERATED_ROUND_DURATION = Histogram(
    "arguslens_fed_round_duration_seconds",
    "Duration of each federated learning round",
    ["model_name"],
    buckets=[1.0, 5.0, 15.0, 30.0, 60.0, 120.0, 300.0],
)

FEDERATED_PARTICIPANTS = Gauge(
    "arguslens_fed_participants_total",
    "Number of nodes participating in the current federated round",
    ["model_name"],
)

FEDERATED_PRIVACY_EPSILON_SPENT = Gauge(
    "arguslens_fed_privacy_epsilon_spent",
    "Cumulative differential privacy epsilon budget consumed",
    ["model_name"],
)

AUTO_HEALING_EVENTS = Counter(
    "arguslens_auto_healing_events_total",
    "Total self-healing events triggered",
    ["event_type", "severity", "outcome"],
)

AUTO_SCALER_REPLICAS = Gauge(
    "arguslens_auto_scaler_replicas",
    "Current replica count managed by AutoScaler",
    ["deployment"],
)

AUTO_SCALER_SCALE_EVENTS = Counter(
    "arguslens_auto_scaler_scale_events_total",
    "Total auto-scaling events",
    ["deployment", "direction"],
)

MODEL_PRECISION = Gauge(
    "arguslens_model_precision_active",
    "Current active precision for each loaded model (0=fp32, 1=fp16, 2=int8)",
    ["model_name"],
)

COGNITION_CONSENSUS_SCORE = Histogram(
    "arguslens_cognition_consensus_score",
    "Agreement score distribution from distributed reasoning rounds",
    buckets=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
)


def start_gpu_telemetry_collector(interval_s: float = 5.0) -> threading.Thread:
    """
    Start a daemon thread that samples NVML GPU stats every *interval_s*
    seconds and updates Prometheus gauges.  Returns the thread (already
    started).  Safe to call even when CUDA / pynvml is unavailable.
    """

    def _collect() -> None:
        try:
            import pynvml  # nvidia-ml-py3

            pynvml.nvmlInit()
            n_devices = pynvml.nvmlDeviceGetCount()
            import time

            while True:
                for i in range(n_devices):
                    handle = pynvml.nvmlDeviceGetHandleByIndex(i)
                    mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
                    util = pynvml.nvmlDeviceGetUtilizationRates(handle)
                    temp = pynvml.nvmlDeviceGetTemperature(
                        handle, pynvml.NVML_TEMPERATURE_GPU
                    )

                    dev_id = str(i)
                    GPU_VRAM_USED_MB.labels(device_id=dev_id).set(
                        mem.used / (1024 ** 2)
                    )
                    GPU_VRAM_TOTAL_MB.labels(device_id=dev_id).set(
                        mem.total / (1024 ** 2)
                    )
                    GPU_UTILIZATION_PERCENT.labels(device_id=dev_id).set(util.gpu)
                    GPU_TEMPERATURE_CELSIUS.labels(device_id=dev_id).set(temp)
                time.sleep(interval_s)
        except ImportError:
            pass  # pynvml not installed — telemetry unavailable
        except Exception:
            pass  # silently stop on any NVML error

    t = threading.Thread(target=_collect, daemon=True, name="gpu_telemetry")
    t.start()
    return t
