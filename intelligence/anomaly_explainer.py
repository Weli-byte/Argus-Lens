"""
AnomalyExplainer — answers "why did this happen and what does it mean"
rather than just "what was detected."
"""

from __future__ import annotations

import logging
import math
from typing import Any

from intelligence.types import ReasoningContext

logger = logging.getLogger(__name__)

_SEVERITY_LABELS = {
    (3.0, math.inf): ("extreme", "Immediately alarming — multiple standard deviations from baseline"),
    (2.0, 3.0): ("significant", "Clear deviation — warrants investigation"),
    (1.5, 2.0): ("mild", "Noticeable but could be transient variation"),
}

_VISION_CAUSES = [
    "Scene illumination change (over/under-exposure)",
    "Subject occlusion or partial frame exit",
    "Camera calibration drift",
    "Motion blur from rapid movement",
    "Environmental obstruction (glare, reflection)",
]

_TEMPORAL_CAUSES: dict[str, list[str]] = {
    "fatigue_score": [
        "Prolonged continuous task without break",
        "Sleep deficit accumulation",
        "Elevated cognitive demand",
        "Dehydration or physiological stress",
    ],
    "focus_score": [
        "Task monotony reducing attentional engagement",
        "External distraction event",
        "Post-meal alertness dip",
        "Early fatigue onset",
    ],
    "cognitive_load": [
        "Concurrent task interference",
        "Novel or complex task introduced",
        "Decision pressure spike",
        "Accumulated context-switching cost",
    ],
    "blink_frequency": [
        "Screen dryness / environmental conditions",
        "Deep concentration suppressing blink reflex",
        "Early drowsiness reducing blink rate",
    ],
}


class AnomalyExplainer:
    """
    Explains anomalies in human-readable, traceable terms.
    Produces structured explanations with z-scores, likely causes,
    and estimated normalisation windows.
    """

    async def explain_vision_anomaly(
        self,
        detected_objects: list[dict],
        expected_objects: list[str],
        context: ReasoningContext,
    ) -> dict[str, Any]:
        detected_labels = {d.get("label", "") for d in detected_objects}
        missing = [e for e in expected_objects if e not in detected_labels]
        unexpected = [d for d in detected_objects if d.get("label") not in expected_objects]
        avg_conf = (
            sum(d.get("confidence", 0) for d in detected_objects) / len(detected_objects)
            if detected_objects
            else 0.0
        )

        causes: list[str] = []
        if avg_conf < 0.4:
            causes.append("Low confidence scores suggest adverse imaging conditions")
        if missing:
            causes.append(f"Expected objects not detected: {', '.join(missing)}")
            causes.extend(_VISION_CAUSES[:2])
        if unexpected:
            causes.append("Unexpected objects may indicate scene change")

        severity = "low"
        if len(missing) >= 2 or avg_conf < 0.3:
            severity = "high"
        elif missing or avg_conf < 0.5:
            severity = "medium"

        explanation: dict[str, Any] = {
            "type": "vision_anomaly",
            "detected_count": len(detected_objects),
            "missing_objects": missing,
            "unexpected_objects": [u.get("label") for u in unexpected],
            "avg_confidence": round(avg_conf, 3),
            "severity": severity,
            "likely_causes": causes,
            "recommended_action": (
                "Verify camera feed and lighting conditions"
                if severity == "high"
                else "Monitor next 5 frames for confirmation"
            ),
        }
        context.add_trace(
            f"anomaly_explainer.vision severity={severity} missing={len(missing)}"
        )
        logger.debug(
            "explain_vision_anomaly severity=%s missing=%d unexpected=%d",
            severity,
            len(missing),
            len(unexpected),
        )
        return explanation

    async def explain_temporal_anomaly(
        self,
        metric_name: str,
        current_value: float,
        historical_mean: float,
        historical_std: float,
        context: ReasoningContext,
    ) -> dict[str, Any]:
        if historical_std == 0:
            z_score = 0.0
        else:
            z_score = abs(current_value - historical_mean) / historical_std

        # Map z-score to severity label
        severity_label = "normal"
        severity_description = "Within expected variability"
        for (low, high), (label, desc) in _SEVERITY_LABELS.items():
            if low <= z_score < high:
                severity_label = label
                severity_description = desc
                break

        causes = _TEMPORAL_CAUSES.get(metric_name, ["Undetermined — review raw signal"])

        # Rough normalisation estimate: higher z → longer recovery window
        recovery_minutes = max(2, min(60, int(z_score * 5)))

        direction = "elevated" if current_value > historical_mean else "depressed"
        pct_delta = (
            abs((current_value - historical_mean) / historical_mean * 100)
            if historical_mean != 0
            else 0.0
        )

        explanation: dict[str, Any] = {
            "type": "temporal_anomaly",
            "metric": metric_name,
            "current_value": round(current_value, 4),
            "historical_mean": round(historical_mean, 4),
            "historical_std": round(historical_std, 4),
            "z_score": round(z_score, 2),
            "direction": direction,
            "percent_deviation": round(pct_delta, 1),
            "severity_label": severity_label,
            "severity_description": severity_description,
            "likely_causes": causes[:3],
            "estimated_recovery_minutes": recovery_minutes,
        }
        context.add_trace(
            f"anomaly_explainer.temporal metric={metric_name} z={z_score:.2f} severity={severity_label}"
        )
        logger.debug(
            "explain_temporal_anomaly metric=%s z_score=%.2f severity=%s",
            metric_name,
            z_score,
            severity_label,
        )
        return explanation

    async def explain_pattern_correlation(
        self,
        vision_anomaly: dict[str, Any],
        temporal_anomaly: dict[str, Any],
    ) -> str:
        vision_sev = vision_anomaly.get("severity", "unknown")
        temporal_sev = temporal_anomaly.get("severity_label", "unknown")
        metric = temporal_anomaly.get("metric", "an operator metric")
        direction = temporal_anomaly.get("direction", "shifted")
        z = temporal_anomaly.get("z_score", 0.0)

        correlation_text = (
            f"A {vision_sev}-severity vision anomaly is occurring concurrently with a "
            f"{temporal_sev} deviation in {metric} (z={z:.2f}, value {direction}). "
        )

        # Add interpretation based on combined context
        if vision_sev == "high" and temporal_sev in ("significant", "extreme"):
            correlation_text += (
                "The co-occurrence of degraded visual detection and an extreme physiological "
                "shift is a strong indicator of a high-risk operator state. Immediate review recommended."
            )
        elif vision_sev == "medium" or temporal_sev == "mild":
            correlation_text += (
                "The combination suggests an emerging trend rather than an acute event. "
                "Continue monitoring; escalate if either signal worsens within the next 2 minutes."
            )
        else:
            correlation_text += (
                "The two signals may share a common environmental cause "
                "(e.g., lighting change affecting both camera and operator alertness cues)."
            )

        logger.debug(
            "explain_pattern_correlation vision_sev=%s temporal_sev=%s",
            vision_sev,
            temporal_sev,
        )
        return correlation_text
