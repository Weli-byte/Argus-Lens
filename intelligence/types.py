"""
Phase 3 shared type system — all dataclasses and enums used across
intelligence, memory, agent, correlation, and explainability layers.
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


class ReasoningMode(Enum):
    REACTIVE = "reactive"       # Single-event response, no memory lookup
    CONTEXTUAL = "contextual"   # Memory-augmented analysis
    PREDICTIVE = "predictive"   # Future-state forecasting via temporal trends
    AGENTIC = "agentic"         # Autonomous decision + action


class InsightSeverity(Enum):
    INFO = "info"
    NOTICE = "notice"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


class AgentState(Enum):
    IDLE = "idle"
    ANALYZING = "analyzing"
    REASONING = "reasoning"
    ACTING = "acting"
    WAITING = "waiting"
    ERROR = "error"


class MemoryType(Enum):
    EPISODIC = "episodic"       # What happened
    SEMANTIC = "semantic"       # What it means
    PROCEDURAL = "procedural"   # How to do it
    WORKING = "working"         # Current context


class CorrelationStrength(Enum):
    WEAK = "weak"               # 0.3–0.5
    MODERATE = "moderate"       # 0.5–0.7
    STRONG = "strong"           # 0.7–0.9
    CAUSAL = "causal"           # 0.9+


# ---------------------------------------------------------------------------
# Core dataclasses
# ---------------------------------------------------------------------------


@dataclass
class ReasoningContext:
    """Unified context object carried through the entire reasoning pipeline."""

    context_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    vision_data: dict[str, Any] = field(default_factory=dict)
    temporal_data: dict[str, Any] = field(default_factory=dict)
    memory_context: list[dict[str, Any]] = field(default_factory=list)
    system_telemetry: dict[str, Any] = field(default_factory=dict)
    reasoning_mode: ReasoningMode = ReasoningMode.REACTIVE
    trace_steps: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def add_trace(self, step: str) -> None:
        self.trace_steps.append(f"[{datetime.utcnow().isoformat()}] {step}")


@dataclass
class AIInsight:
    """Structured intelligence output produced by the ReasoningEngine."""

    insight_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    context_id: str = ""
    title: str = ""
    summary: str = ""
    detailed_explanation: str = ""
    severity: InsightSeverity = InsightSeverity.INFO
    confidence: float = 0.0
    reasoning_steps: list[str] = field(default_factory=list)
    supporting_evidence: list[dict[str, Any]] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    related_memories: list[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    expires_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "insight_id": self.insight_id,
            "context_id": self.context_id,
            "title": self.title,
            "summary": self.summary,
            "detailed_explanation": self.detailed_explanation,
            "severity": self.severity.value,
            "confidence": self.confidence,
            "reasoning_steps": self.reasoning_steps,
            "supporting_evidence": self.supporting_evidence,
            "recommendations": self.recommendations,
            "related_memories": self.related_memories,
            "timestamp": self.timestamp.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "metadata": self.metadata,
        }


@dataclass
class MemoryEntry:
    """Single entry in either short-term or long-term memory."""

    memory_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    memory_type: MemoryType = MemoryType.EPISODIC
    content: str = ""
    embedding: list[float] = field(default_factory=list)
    importance_score: float = 0.5
    access_count: int = 0
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_accessed: datetime = field(default_factory=datetime.utcnow)
    expires_at: datetime | None = None
    tags: list[str] = field(default_factory=list)
    source: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "memory_id": self.memory_id,
            "memory_type": self.memory_type.value,
            "content": self.content,
            "importance_score": self.importance_score,
            "access_count": self.access_count,
            "created_at": self.created_at.isoformat(),
            "last_accessed": self.last_accessed.isoformat(),
            "tags": self.tags,
            "source": self.source,
            "metadata": self.metadata,
        }


@dataclass
class AgentTask:
    """Task submitted to and processed by an agent."""

    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    agent_type: str = ""
    trigger: str = ""
    priority: int = 5
    input_data: dict[str, Any] = field(default_factory=dict)
    output_data: dict[str, Any] = field(default_factory=dict)
    state: AgentState = AgentState.IDLE
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error: str | None = None
    reasoning_trace: list[str] = field(default_factory=list)

    def add_trace(self, msg: str) -> None:
        self.reasoning_trace.append(f"[{datetime.utcnow().isoformat()}] {msg}")


@dataclass
class CorrelationResult:
    """Result of correlating two events."""

    correlation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    event_a: dict[str, Any] = field(default_factory=dict)
    event_b: dict[str, Any] = field(default_factory=dict)
    strength: CorrelationStrength = CorrelationStrength.WEAK
    score: float = 0.0
    lag_seconds: float = 0.0
    explanation: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict[str, Any]:
        return {
            "correlation_id": self.correlation_id,
            "event_a": self.event_a,
            "event_b": self.event_b,
            "strength": self.strength.value,
            "score": self.score,
            "lag_seconds": self.lag_seconds,
            "explanation": self.explanation,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class ReasoningTrace:
    """Full audit trail of a reasoning pipeline execution."""

    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    context_id: str = ""
    steps: list[dict[str, Any]] = field(default_factory=list)
    total_duration_ms: float = 0.0
    memory_lookups: int = 0
    correlations_found: int = 0
    final_insight: AIInsight | None = None
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "context_id": self.context_id,
            "steps": self.steps,
            "total_duration_ms": self.total_duration_ms,
            "memory_lookups": self.memory_lookups,
            "correlations_found": self.correlations_found,
            "final_insight": self.final_insight.to_dict() if self.final_insight else None,
            "timestamp": self.timestamp.isoformat(),
        }
