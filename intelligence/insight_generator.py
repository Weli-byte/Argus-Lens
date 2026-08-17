"""
InsightGenerator — produces structured AIInsight objects from raw
pattern + risk + temporal + memory inputs.
All output fields are derived from real data; no hardcoded strings.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from intelligence.anomaly_explainer import AnomalyExplainer
from intelligence.semantic_correlator import SemanticCorrelator
from intelligence.types import AIInsight, InsightSeverity, MemoryEntry, ReasoningContext

logger = logging.getLogger(__name__)

_SEVERITY_THRESHOLDS: list[tuple[float, InsightSeverity]] = [
    (0.9, InsightSeverity.EMERGENCY),
    (0.75, InsightSeverity.CRITICAL),
    (0.5, InsightSeverity.WARNING),
    (0.2, InsightSeverity.NOTICE),
    (0.0, InsightSeverity.INFO),
]

_TREND_LABELS = {
    "increasing": "worsening",
    "decreasing": "improving",
    "stable": "stable",
}


def _risk_to_severity(risk: float) -> InsightSeverity:
    for threshold, sev in _SEVERITY_THRESHOLDS:
        if risk >= threshold:
            return sev
    return InsightSeverity.INFO


class InsightGenerator:
    """
    Converts analysis artefacts into a fully populated AIInsight.
    """

    def __init__(
        self,
        anomaly_explainer: AnomalyExplainer,
        semantic_correlator: SemanticCorrelator,
    ) -> None:
        self._explainer = anomaly_explainer
        self._correlator = semantic_correlator

    async def generate(
        self,
        context: ReasoningContext,
        patterns: list[dict[str, Any]],
        risk_score: float,
        temporal_analysis: dict[str, Any],
        similar_memories: list[MemoryEntry],
    ) -> AIInsight:
        severity = _risk_to_severity(risk_score)
        context.add_trace(
            f"insight_generator.start patterns={len(patterns)} risk={risk_score:.3f} severity={severity.value}"
        )

        title = await self._generate_title(patterns, risk_score)
        summary = await self._generate_summary(context, patterns, temporal_analysis)
        evidence = await self._build_supporting_evidence(context, patterns)
        recommendations = await self._generate_recommendations(
            patterns, risk_score, similar_memories
        )
        confidence = await self._calculate_confidence(
            patterns,
            memory_support=len(similar_memories),
            temporal_consistency=temporal_analysis.get("consistency_score", 0.5),
        )

        # Expire insights after a window proportional to severity
        expire_minutes = {
            InsightSeverity.EMERGENCY: 60,
            InsightSeverity.CRITICAL: 120,
            InsightSeverity.WARNING: 240,
            InsightSeverity.NOTICE: 480,
            InsightSeverity.INFO: 1440,
        }
        expires_at = datetime.utcnow() + timedelta(
            minutes=expire_minutes.get(severity, 240)
        )

        insight = AIInsight(
            context_id=context.context_id,
            title=title,
            summary=summary,
            detailed_explanation=self._build_detailed_explanation(
                context, patterns, temporal_analysis, similar_memories
            ),
            severity=severity,
            confidence=round(confidence, 3),
            reasoning_steps=context.trace_steps.copy(),
            supporting_evidence=evidence,
            recommendations=recommendations,
            related_memories=[m.memory_id for m in similar_memories],
            expires_at=expires_at,
            metadata={
                "risk_score": round(risk_score, 4),
                "pattern_count": len(patterns),
                "memory_support": len(similar_memories),
                "session_id": context.session_id,
            },
        )

        context.add_trace(
            f"insight_generator.done insight_id={insight.insight_id} confidence={confidence:.3f}"
        )
        logger.info(
            "insight_generator severity=%s confidence=%.3f patterns=%d",
            severity.value,
            confidence,
            len(patterns),
        )
        return insight

    async def _generate_title(
        self, patterns: list[dict[str, Any]], risk_score: float
    ) -> str:
        dominant = patterns[0] if patterns else {}
        pattern_name = dominant.get("name", "System Event")
        readable = pattern_name.replace("_", " ").title()

        if risk_score >= 0.8:
            return f"CRITICAL: {readable} Detected"
        if risk_score >= 0.5:
            return f"WARNING: {readable} Pattern"
        if risk_score >= 0.2:
            return f"NOTICE: {readable} Observed"
        return f"INFO: {readable}"

    async def _generate_summary(
        self,
        context: ReasoningContext,
        patterns: list[dict[str, Any]],
        temporal: dict[str, Any],
    ) -> str:
        parts: list[str] = []

        # What was detected
        if patterns:
            names = ", ".join(p.get("name", "unknown").replace("_", " ") for p in patterns[:3])
            parts.append(f"Detected pattern(s): {names}.")
        else:
            parts.append("No dominant pattern identified; monitoring general system state.")

        # Vision context
        if context.vision_data:
            dets = context.vision_data.get("detections", [])
            if dets:
                labels = ", ".join(d.get("label", "") for d in dets[:3])
                parts.append(f"Visual context: {len(dets)} object(s) detected ({labels}).")

        # Temporal context
        trend = temporal.get("trend", "stable")
        trend_label = _TREND_LABELS.get(trend, trend)
        metric = temporal.get("primary_metric", "primary metric")
        parts.append(
            f"Temporal trend: {metric} is {trend_label} over the monitoring window."
        )

        # Memory context
        mem_count = len(context.memory_context)
        if mem_count > 0:
            parts.append(
                f"Analysis informed by {mem_count} historical memory entr{'y' if mem_count == 1 else 'ies'}."
            )

        return " ".join(parts)

    async def _generate_recommendations(
        self,
        patterns: list[dict[str, Any]],
        risk_score: float,
        similar_memories: list[MemoryEntry],
    ) -> list[str]:
        recs: list[str] = []

        for p in patterns[:3]:
            for r in p.get("recommendations", []):
                if r not in recs:
                    recs.append(r)

        if risk_score >= 0.8 and "Notify on-site supervisor immediately" not in recs:
            recs.insert(0, "Notify on-site supervisor immediately")

        if similar_memories:
            recs.append(
                f"Review {len(similar_memories)} similar historical event(s) for context and prior outcomes"
            )

        return recs[:6]

    async def _calculate_confidence(
        self,
        patterns: list[dict[str, Any]],
        memory_support: int,
        temporal_consistency: float,
    ) -> float:
        # Base: average of individual pattern confidences
        if patterns:
            base = sum(p.get("confidence", 0.5) for p in patterns) / len(patterns)
        else:
            base = 0.2

        # Memory support bonus (up to +0.15 for 5+ matches)
        memory_bonus = min(0.15, memory_support * 0.03)

        # Temporal consistency factor (0–1 → scales the base)
        consistency_factor = 0.7 + 0.3 * max(0.0, min(1.0, temporal_consistency))

        confidence = min(1.0, (base + memory_bonus) * consistency_factor)
        return confidence

    async def _build_supporting_evidence(
        self,
        context: ReasoningContext,
        patterns: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        evidence: list[dict[str, Any]] = []
        ts = context.timestamp.isoformat()

        # Vision evidence
        dets = context.vision_data.get("detections", [])
        if dets:
            evidence.append(
                {
                    "type": "vision",
                    "description": f"{len(dets)} object detection(s)",
                    "value": [d.get("label") for d in dets[:5]],
                    "timestamp": ts,
                }
            )

        # Temporal evidence
        for key in ("fatigue_score", "focus_score", "cognitive_load"):
            val = context.temporal_data.get(key)
            if val is not None:
                evidence.append(
                    {
                        "type": "temporal",
                        "description": key.replace("_", " ").title(),
                        "value": round(float(val), 3),
                        "timestamp": ts,
                    }
                )

        # Pattern evidence
        for p in patterns:
            for ev in p.get("evidence", []):
                evidence.append(
                    {
                        "type": "pattern",
                        "description": ev.get("description", ""),
                        "value": ev.get("value"),
                        "timestamp": ts,
                    }
                )

        return evidence

    @staticmethod
    def _build_detailed_explanation(
        context: ReasoningContext,
        patterns: list[dict[str, Any]],
        temporal: dict[str, Any],
        memories: list[MemoryEntry],
    ) -> str:
        lines: list[str] = ["=== Detailed Reasoning Explanation ===", ""]

        lines.append(f"Session: {context.session_id}")
        lines.append(f"Reasoning mode: {context.reasoning_mode.value}")
        lines.append(f"Context assembled at: {context.timestamp.isoformat()}")
        lines.append("")

        if patterns:
            lines.append("Detected Patterns:")
            for p in patterns:
                lines.append(
                    f"  - {p.get('name', 'unknown')} "
                    f"(confidence={p.get('confidence', 0):.2f}, severity={p.get('severity', 'unknown')})"
                )
        else:
            lines.append("No specific patterns triggered.")

        lines.append("")
        lines.append("Temporal Analysis:")
        lines.append(f"  Primary metric: {temporal.get('primary_metric', 'N/A')}")
        lines.append(f"  Trend: {temporal.get('trend', 'N/A')}")
        lines.append(f"  Forecast: {temporal.get('forecast_description', 'N/A')}")

        if memories:
            lines.append("")
            lines.append(f"Historical Context ({len(memories)} similar events found):")
            for m in memories[:3]:
                lines.append(f"  [{m.memory_type.value}] {m.content[:120]}")

        lines.append("")
        lines.append("Reasoning Trace:")
        for step in context.trace_steps[-10:]:
            lines.append(f"  {step}")

        return "\n".join(lines)
