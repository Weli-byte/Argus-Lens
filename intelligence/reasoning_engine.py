"""
ReasoningEngine — core reasoning loop.
Accepts ReasoningContext → produces AIInsight + ReasoningTrace.
Rule-based + statistical; LLM-ready interface.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Any

from intelligence.anomaly_explainer import AnomalyExplainer
from intelligence.context_manager import IntelligenceContextManager
from intelligence.insight_generator import InsightGenerator
from intelligence.types import (
    AIInsight,
    InsightSeverity,
    ReasoningContext,
    ReasoningMode,
    ReasoningTrace,
)
from memory.retrieval_manager import RetrievalManager

logger = logging.getLogger(__name__)

_SEVERITY_WEIGHT: dict[str, float] = {
    "EMERGENCY": 1.0,
    "CRITICAL": 0.8,
    "WARNING": 0.5,
    "NOTICE": 0.2,
    "INFO": 0.05,
}

# Pattern definitions: each entry is (name, check_fn, severity, confidence_base, recommendations)
# check_fn receives (context: ReasoningContext) and returns (bool, evidence: list[dict])


def _check_medical_emergency(ctx: ReasoningContext) -> tuple[bool, list[dict]]:
    td = ctx.temporal_data
    vd = ctx.vision_data
    fatigue = td.get("fatigue_score", 0.0)
    detections = vd.get("detections", [])
    person_lying = any(
        "lying" in d.get("label", "").lower() or "floor" in d.get("label", "").lower()
        for d in detections
    )
    if person_lying and fatigue > 0.75:
        return True, [
            {"description": "Person detected in prone position", "value": True},
            {"description": "Fatigue score", "value": round(fatigue, 3)},
        ]
    return False, []


def _check_fainting_risk(ctx: ReasoningContext) -> tuple[bool, list[dict]]:
    td = ctx.temporal_data
    fatigue = td.get("fatigue_score", 0.0)
    blink = td.get("blink_frequency", 1.0)
    focus = td.get("focus_score", 1.0)
    if fatigue > 0.65 and blink < 0.4 and focus < 0.35:
        return True, [
            {"description": "Fatigue score", "value": round(fatigue, 3)},
            {"description": "Blink frequency", "value": round(blink, 3)},
            {"description": "Focus score", "value": round(focus, 3)},
        ]
    return False, []


def _check_model_drift(ctx: ReasoningContext) -> tuple[bool, list[dict]]:
    vd = ctx.vision_data
    dets = vd.get("detections", [])
    if not dets:
        return False, []
    avg_conf = sum(d.get("confidence", 1.0) for d in dets) / len(dets)
    if avg_conf < 0.35:
        return True, [
            {"description": "Average detection confidence", "value": round(avg_conf, 3)},
        ]
    return False, []


def _check_scene_change(ctx: ReasoningContext) -> tuple[bool, list[dict]]:
    vd = ctx.vision_data
    td = ctx.temporal_data
    det_count = len(vd.get("detections", []))
    prev_count = vd.get("previous_detection_count", det_count)
    delta = abs(det_count - prev_count)
    temporal_anomaly = td.get("anomaly_detected", False)
    if delta >= 3 and temporal_anomaly:
        return True, [
            {"description": "Detection count delta", "value": delta},
            {"description": "Temporal anomaly active", "value": True},
        ]
    return False, []


def _check_high_fatigue(ctx: ReasoningContext) -> tuple[bool, list[dict]]:
    fatigue = ctx.temporal_data.get("fatigue_score", 0.0)
    if fatigue > 0.7:
        return True, [{"description": "Fatigue score", "value": round(fatigue, 3)}]
    return False, []


def _check_system_degraded(ctx: ReasoningContext) -> tuple[bool, list[dict]]:
    tel = ctx.system_telemetry
    gpu_util = tel.get("avg_gpu_utilization", 0.0)
    queue_pct = tel.get("queue_utilization", 0.0)
    dead_workers = tel.get("dead_workers", 0)
    issues: list[dict] = []
    if gpu_util > 0.9:
        issues.append({"description": "GPU utilisation", "value": round(gpu_util, 3)})
    if queue_pct > 0.85:
        issues.append({"description": "Queue utilisation", "value": round(queue_pct, 3)})
    if dead_workers > 0:
        issues.append({"description": "Dead workers", "value": dead_workers})
    return bool(issues), issues


_PATTERN_REGISTRY: list[dict[str, Any]] = [
    {
        "name": "medical_emergency_suspect",
        "check": _check_medical_emergency,
        "severity": "EMERGENCY",
        "confidence_base": 0.75,
        "recommendations": [
            "Contact emergency services immediately",
            "Do not move the subject",
        ],
    },
    {
        "name": "fainting_risk",
        "check": _check_fainting_risk,
        "severity": "CRITICAL",
        "confidence_base": 0.7,
        "recommendations": [
            "Prompt operator to take an immediate break",
            "Check ambient environmental conditions",
        ],
    },
    {
        "name": "model_drift",
        "check": _check_model_drift,
        "severity": "WARNING",
        "confidence_base": 0.65,
        "recommendations": [
            "Trigger model hot-reload",
            "Verify lighting and camera focus",
        ],
    },
    {
        "name": "scene_change",
        "check": _check_scene_change,
        "severity": "WARNING",
        "confidence_base": 0.6,
        "recommendations": [
            "Review recent camera feed for environmental changes",
        ],
    },
    {
        "name": "high_fatigue",
        "check": _check_high_fatigue,
        "severity": "WARNING",
        "confidence_base": 0.8,
        "recommendations": [
            "Schedule mandatory break of ≥10 minutes",
        ],
    },
    {
        "name": "system_degraded",
        "check": _check_system_degraded,
        "severity": "WARNING",
        "confidence_base": 0.85,
        "recommendations": [
            "Free GPU memory or scale worker pool",
        ],
    },
]


class ReasoningEngine:
    """
    Main reasoning loop: context → patterns → risk → insight + trace.
    """

    def __init__(
        self,
        context_manager: IntelligenceContextManager,
        insight_generator: InsightGenerator,
        anomaly_explainer: AnomalyExplainer,
        retrieval_manager: RetrievalManager,
    ) -> None:
        self._ctx_mgr = context_manager
        self._generator = insight_generator
        self._explainer = anomaly_explainer
        self._retrieval = retrieval_manager

    async def reason(
        self,
        context: ReasoningContext,
        mode: ReasoningMode = ReasoningMode.CONTEXTUAL,
    ) -> tuple[AIInsight, ReasoningTrace]:
        t_start = time.monotonic()
        trace = ReasoningTrace(context_id=context.context_id)

        context.reasoning_mode = mode
        context.add_trace(f"reasoning_engine.start mode={mode.value}")

        # 1. Detect patterns
        patterns = await self._detect_critical_patterns(context)
        trace.steps.append(
            {"step": "detect_patterns", "count": len(patterns), "ts": datetime.utcnow().isoformat()}
        )
        context.add_trace(f"reasoning_engine.patterns detected={len(patterns)}")

        # 2. Temporal reasoning
        temporal_analysis = await self._apply_temporal_reasoning(context)
        trace.steps.append(
            {"step": "temporal_reasoning", "result": temporal_analysis, "ts": datetime.utcnow().isoformat()}
        )
        context.add_trace(
            f"reasoning_engine.temporal trend={temporal_analysis.get('trend', 'unknown')}"
        )

        # 3. Risk score
        risk_score = await self._calculate_risk_score(patterns, context)
        trace.steps.append(
            {"step": "risk_score", "value": risk_score, "ts": datetime.utcnow().isoformat()}
        )
        context.add_trace(f"reasoning_engine.risk_score={risk_score:.4f}")

        # 4. Memory — find similar historical events
        similar_memories = []
        if mode in (ReasoningMode.CONTEXTUAL, ReasoningMode.AGENTIC, ReasoningMode.PREDICTIVE):
            similar_memories = await self._retrieval.retrieve_by_type(
                context.session_id, limit=5, memory_type=None  # type: ignore[arg-type]
            )
            trace.memory_lookups += 1
            context.add_trace(f"reasoning_engine.memory_hits={len(similar_memories)}")

        # 5. Generate insight
        insight = await self._generator.generate(
            context=context,
            patterns=patterns,
            risk_score=risk_score,
            temporal_analysis=temporal_analysis,
            similar_memories=similar_memories,
        )
        trace.final_insight = insight
        trace.correlations_found = len(patterns)

        duration_ms = (time.monotonic() - t_start) * 1000
        trace.total_duration_ms = round(duration_ms, 2)
        trace.steps.append(
            {
                "step": "complete",
                "duration_ms": trace.total_duration_ms,
                "insight_id": insight.insight_id,
                "ts": datetime.utcnow().isoformat(),
            }
        )

        context.add_trace(
            f"reasoning_engine.complete duration_ms={duration_ms:.1f} "
            f"severity={insight.severity.value} confidence={insight.confidence:.3f}"
        )
        logger.info(
            "reasoning_engine.reason context_id=%s mode=%s risk=%.3f severity=%s "
            "confidence=%.3f duration_ms=%.1f",
            context.context_id,
            mode.value,
            risk_score,
            insight.severity.value,
            insight.confidence,
            duration_ms,
        )
        return insight, trace

    async def _detect_critical_patterns(
        self, context: ReasoningContext
    ) -> list[dict[str, Any]]:
        detected: list[dict[str, Any]] = []
        for pattern in _PATTERN_REGISTRY:
            try:
                matched, evidence = pattern["check"](context)
                if matched:
                    detected.append(
                        {
                            "name": pattern["name"],
                            "severity": pattern["severity"],
                            "confidence": pattern["confidence_base"],
                            "evidence": evidence,
                            "recommendations": pattern["recommendations"],
                        }
                    )
                    context.add_trace(
                        f"reasoning_engine.pattern:{pattern['name']} "
                        f"severity={pattern['severity']}"
                    )
            except Exception as exc:
                logger.warning(
                    "reasoning_engine.pattern_check error pattern=%s: %s",
                    pattern["name"],
                    exc,
                )
        return detected

    async def _calculate_risk_score(
        self, patterns: list[dict[str, Any]], context: ReasoningContext
    ) -> float:
        if not patterns:
            base = 0.0
        else:
            weights = [_SEVERITY_WEIGHT.get(p.get("severity", "INFO"), 0.05) for p in patterns]
            base = min(1.0, sum(w * p.get("confidence", 0.5) for w, p in zip(weights, patterns)))

        # Temporal trend modifier
        trend = context.temporal_data.get("trend", "stable")
        trend_factor = {"increasing": 0.1, "stable": 0.0, "decreasing": -0.05}.get(trend, 0.0)

        # Memory modifier: prior occurrences of same patterns increase risk
        memory_modifier = min(0.1, len(context.memory_context) * 0.01)

        risk = max(0.0, min(1.0, base + trend_factor + memory_modifier))
        logger.debug(
            "risk_score base=%.3f trend_factor=%.3f memory_mod=%.3f final=%.3f",
            base,
            trend_factor,
            memory_modifier,
            risk,
        )
        return round(risk, 4)

    async def _select_reasoning_mode(self, context: ReasoningContext) -> ReasoningMode:
        risk = await self._calculate_risk_score(
            await self._detect_critical_patterns(context), context
        )
        if risk > 0.8:
            return ReasoningMode.AGENTIC
        if context.memory_context:
            return ReasoningMode.CONTEXTUAL
        if context.temporal_data.get("trend") in ("increasing", "decreasing"):
            return ReasoningMode.PREDICTIVE
        return ReasoningMode.REACTIVE

    async def _apply_temporal_reasoning(
        self, context: ReasoningContext
    ) -> dict[str, Any]:
        td = context.temporal_data
        history: list[float] = td.get("metric_history", [])

        primary_metric = "fatigue_score"
        current_val = td.get(primary_metric, 0.0)

        if len(history) >= 3:
            delta = history[-1] - history[0]
            rate = delta / len(history)
            if rate > 0.02:
                trend = "increasing"
            elif rate < -0.02:
                trend = "decreasing"
            else:
                trend = "stable"
        else:
            trend = "stable"
            rate = 0.0

        # Simple linear forecast for the next 60 seconds (assuming 1 sample/sec history)
        steps_ahead = 60
        forecast_val = current_val + rate * steps_ahead
        forecast_description = (
            f"If current trend continues, {primary_metric} projected at "
            f"{forecast_val:.3f} in ~{steps_ahead}s"
        )

        consistency_score = 1.0 - min(1.0, abs(rate) * 10)

        return {
            "primary_metric": primary_metric,
            "current_value": round(current_val, 4),
            "trend": trend,
            "rate_per_sample": round(rate, 5),
            "forecast_value": round(forecast_val, 4),
            "forecast_description": forecast_description,
            "consistency_score": round(consistency_score, 3),
        }
