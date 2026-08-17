"""
Shared types for Phase 4: Autonomous AI Ecosystem and Edge Intelligence Network.
All enums and dataclasses used across edge, federated, autonomy, and cognition layers.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class EdgeNodeState(Enum):
    """Lifecycle state of an edge compute node."""
    INITIALIZING = "initializing"
    ONLINE = "online"
    DEGRADED = "degraded"       # partial functionality
    OFFLINE = "offline"         # no cloud connectivity, running local
    SYNCING = "syncing"         # uploading buffered data to cloud
    RECOVERING = "recovering"   # self-healing in progress
    SHUTDOWN = "shutdown"


class InferenceStrategy(Enum):
    """How the node selects inference path."""
    CLOUD_FIRST = "cloud_first"         # prefer cloud, fall back to edge
    EDGE_FIRST = "edge_first"           # prefer edge, fall back to cloud
    EDGE_ONLY = "edge_only"             # strictly local, never calls cloud
    HYBRID = "hybrid"                   # run both, reconcile outputs
    ADAPTIVE = "adaptive"               # dynamically chosen per request


class ModelPrecision(Enum):
    """Numeric precision of a loaded model."""
    FP32 = "fp32"
    FP16 = "fp16"
    INT8 = "int8"
    INT4 = "int4"
    DYNAMIC = "dynamic"     # quantization decided at runtime


class HardwareProfile(Enum):
    """Capability tier of the host hardware."""
    EMBEDDED = "embedded"           # ARM / Raspberry Pi class
    EDGE_GPU = "edge_gpu"           # Jetson / small GPU
    WORKSTATION = "workstation"     # desktop / dev GPU
    SERVER = "server"               # datacenter GPU(s)
    CLOUD = "cloud"                 # auto-scaling cloud instance


class FederatedRound(Enum):
    """Phase of a federated learning round."""
    IDLE = "idle"
    COLLECTING_GRADIENTS = "collecting_gradients"
    AGGREGATING = "aggregating"
    DISTRIBUTING = "distributing"
    VALIDATING = "validating"
    COMPLETE = "complete"
    FAILED = "failed"


class AutonomyLevel(Enum):
    """
    How much autonomy the self-healing system has to act without human approval.
    Ordered by increasing autonomy.
    """
    SUPERVISED = "supervised"       # propose action, wait for approval
    SEMI_AUTO = "semi_auto"         # act on low-risk events, escalate high
    AUTONOMOUS = "autonomous"       # act on all events, log decisions
    EMERGENCY = "emergency"         # bypass all checks during crisis


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class EdgeNode:
    """
    Represents a single edge compute node in the distributed ArgusLens network.
    Created by EdgeRuntime at startup; published to Redis for discovery.
    """
    node_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    hostname: str = ""
    hardware_profile: HardwareProfile = HardwareProfile.WORKSTATION
    state: EdgeNodeState = EdgeNodeState.INITIALIZING
    inference_strategy: InferenceStrategy = InferenceStrategy.ADAPTIVE
    capabilities: list[str] = field(default_factory=list)   # e.g. ["vision","temporal"]
    gpu_count: int = 0
    gpu_vram_mb: float = 0.0
    cpu_cores: int = 0
    ram_mb: float = 0.0
    model_precision: ModelPrecision = ModelPrecision.FP32
    cloud_url: str | None = None
    last_heartbeat: datetime = field(default_factory=datetime.utcnow)
    last_sync: datetime | None = None
    offline_queue_depth: int = 0
    version: str = "4.0.0"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "hostname": self.hostname,
            "hardware_profile": self.hardware_profile.value,
            "state": self.state.value,
            "inference_strategy": self.inference_strategy.value,
            "capabilities": self.capabilities,
            "gpu_count": self.gpu_count,
            "gpu_vram_mb": self.gpu_vram_mb,
            "cpu_cores": self.cpu_cores,
            "ram_mb": self.ram_mb,
            "model_precision": self.model_precision.value,
            "cloud_url": self.cloud_url,
            "last_heartbeat": self.last_heartbeat.isoformat(),
            "last_sync": self.last_sync.isoformat() if self.last_sync else None,
            "offline_queue_depth": self.offline_queue_depth,
            "version": self.version,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EdgeNode":
        node = cls()
        node.node_id = data.get("node_id", node.node_id)
        node.hostname = data.get("hostname", "")
        node.hardware_profile = HardwareProfile(data.get("hardware_profile", "workstation"))
        node.state = EdgeNodeState(data.get("state", "initializing"))
        node.inference_strategy = InferenceStrategy(data.get("inference_strategy", "adaptive"))
        node.capabilities = data.get("capabilities", [])
        node.gpu_count = data.get("gpu_count", 0)
        node.gpu_vram_mb = data.get("gpu_vram_mb", 0.0)
        node.cpu_cores = data.get("cpu_cores", 0)
        node.ram_mb = data.get("ram_mb", 0.0)
        node.model_precision = ModelPrecision(data.get("model_precision", "fp32"))
        node.cloud_url = data.get("cloud_url")
        raw_hb = data.get("last_heartbeat")
        if raw_hb:
            node.last_heartbeat = datetime.fromisoformat(raw_hb)
        raw_sync = data.get("last_sync")
        if raw_sync:
            node.last_sync = datetime.fromisoformat(raw_sync)
        node.offline_queue_depth = data.get("offline_queue_depth", 0)
        node.version = data.get("version", "4.0.0")
        node.metadata = data.get("metadata", {})
        return node


@dataclass
class FederatedUpdate:
    """
    A single node's contribution to a federated learning round.
    Contains anonymized gradient deltas and training statistics.
    """
    update_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    node_id: str = ""
    round_number: int = 0
    model_name: str = ""
    # Serialized gradient deltas: layer_name -> list[float]
    gradient_deltas: dict[str, list[float]] = field(default_factory=dict)
    n_samples: int = 0          # number of local training samples
    local_loss: float = 0.0
    local_accuracy: float = 0.0
    noise_applied: bool = False
    privacy_budget_spent: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "update_id": self.update_id,
            "node_id": self.node_id,
            "round_number": self.round_number,
            "model_name": self.model_name,
            "gradient_deltas": self.gradient_deltas,
            "n_samples": self.n_samples,
            "local_loss": self.local_loss,
            "local_accuracy": self.local_accuracy,
            "noise_applied": self.noise_applied,
            "privacy_budget_spent": self.privacy_budget_spent,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FederatedUpdate":
        update = cls()
        update.update_id = data.get("update_id", update.update_id)
        update.node_id = data.get("node_id", "")
        update.round_number = data.get("round_number", 0)
        update.model_name = data.get("model_name", "")
        update.gradient_deltas = data.get("gradient_deltas", {})
        update.n_samples = data.get("n_samples", 0)
        update.local_loss = data.get("local_loss", 0.0)
        update.local_accuracy = data.get("local_accuracy", 0.0)
        update.noise_applied = data.get("noise_applied", False)
        update.privacy_budget_spent = data.get("privacy_budget_spent", 0.0)
        raw_ts = data.get("timestamp")
        if raw_ts:
            update.timestamp = datetime.fromisoformat(raw_ts)
        update.metadata = data.get("metadata", {})
        return update


@dataclass
class SelfOptimizationDecision:
    """
    A logged autonomous decision made by the self-optimization engine.
    Every autonomous action must be captured as one of these.
    """
    decision_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    decision_type: str = ""         # e.g. "scale_up", "reload_model", "adjust_batch"
    trigger: str = ""               # what caused the decision
    action_taken: str = ""          # human-readable description of action
    expected_outcome: str = ""
    actual_outcome: str | None = None
    autonomy_level: AutonomyLevel = AutonomyLevel.SUPERVISED
    approved_by: str | None = None  # None = autonomous, else human approver id
    parameters: dict[str, Any] = field(default_factory=dict)
    metrics_before: dict[str, float] = field(default_factory=dict)
    metrics_after: dict[str, float] = field(default_factory=dict)
    success: bool | None = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    completed_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "decision_type": self.decision_type,
            "trigger": self.trigger,
            "action_taken": self.action_taken,
            "expected_outcome": self.expected_outcome,
            "actual_outcome": self.actual_outcome,
            "autonomy_level": self.autonomy_level.value,
            "approved_by": self.approved_by,
            "parameters": self.parameters,
            "metrics_before": self.metrics_before,
            "metrics_after": self.metrics_after,
            "success": self.success,
            "timestamp": self.timestamp.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


@dataclass
class HealthEvent:
    """
    Represents a system health observation that may trigger self-healing.
    Published by MonitoringAgent; consumed by HealthOrchestrator.
    """
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source: str = ""            # component name that raised the event
    event_type: str = ""        # e.g. "gpu_oom", "queue_overflow", "worker_crash"
    severity: str = "warning"   # "info" | "warning" | "critical" | "emergency"
    description: str = ""
    affected_components: list[str] = field(default_factory=list)
    metrics: dict[str, float] = field(default_factory=dict)
    recoverable: bool = True
    timestamp: datetime = field(default_factory=datetime.utcnow)
    resolved_at: datetime | None = None
    resolution: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "source": self.source,
            "event_type": self.event_type,
            "severity": self.severity,
            "description": self.description,
            "affected_components": self.affected_components,
            "metrics": self.metrics,
            "recoverable": self.recoverable,
            "timestamp": self.timestamp.isoformat(),
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "resolution": self.resolution,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "HealthEvent":
        ev = cls()
        ev.event_id = data.get("event_id", ev.event_id)
        ev.source = data.get("source", "")
        ev.event_type = data.get("event_type", "")
        ev.severity = data.get("severity", "warning")
        ev.description = data.get("description", "")
        ev.affected_components = data.get("affected_components", [])
        ev.metrics = data.get("metrics", {})
        ev.recoverable = data.get("recoverable", True)
        raw_ts = data.get("timestamp")
        if raw_ts:
            ev.timestamp = datetime.fromisoformat(raw_ts)
        raw_res = data.get("resolved_at")
        if raw_res:
            ev.resolved_at = datetime.fromisoformat(raw_res)
        ev.resolution = data.get("resolution")
        ev.metadata = data.get("metadata", {})
        return ev


@dataclass
class CognitionState:
    """
    Snapshot of distributed cognition consensus across multiple nodes.
    Produced by DistributedReasoning after multi-node voting.
    """
    state_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str = ""
    participating_nodes: list[str] = field(default_factory=list)
    consensus_insight: dict[str, Any] = field(default_factory=dict)
    agreement_score: float = 0.0    # 0.0 = total disagreement, 1.0 = unanimous
    dissenting_nodes: list[str] = field(default_factory=list)
    reasoning_summary: str = ""
    context_snapshot: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    ttl_seconds: int = 300

    def to_dict(self) -> dict[str, Any]:
        return {
            "state_id": self.state_id,
            "session_id": self.session_id,
            "participating_nodes": self.participating_nodes,
            "consensus_insight": self.consensus_insight,
            "agreement_score": self.agreement_score,
            "dissenting_nodes": self.dissenting_nodes,
            "reasoning_summary": self.reasoning_summary,
            "context_snapshot": self.context_snapshot,
            "timestamp": self.timestamp.isoformat(),
            "ttl_seconds": self.ttl_seconds,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CognitionState":
        cs = cls()
        cs.state_id = data.get("state_id", cs.state_id)
        cs.session_id = data.get("session_id", "")
        cs.participating_nodes = data.get("participating_nodes", [])
        cs.consensus_insight = data.get("consensus_insight", {})
        cs.agreement_score = data.get("agreement_score", 0.0)
        cs.dissenting_nodes = data.get("dissenting_nodes", [])
        cs.reasoning_summary = data.get("reasoning_summary", "")
        cs.context_snapshot = data.get("context_snapshot", {})
        raw_ts = data.get("timestamp")
        if raw_ts:
            cs.timestamp = datetime.fromisoformat(raw_ts)
        cs.ttl_seconds = data.get("ttl_seconds", 300)
        return cs
