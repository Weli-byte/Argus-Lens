"""
InferenceExplainer — explains detection decisions in human-readable terms.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

_CONFIDENCE_DROP_CAUSES = [
    ("motion_blur", "Rapid movement causing frame blur"),
    ("lighting_change", "Significant illumination shift"),
    ("occlusion", "Subject partially out of frame or occluded"),
    ("model_drift", "Gradual model performance degradation"),
    ("resolution_issue", "Camera focus or resolution degradation"),
]


class InferenceExplainer:
    """
    Explains why inference produced a given result.
    No machine learning — deterministic analysis of confidence and bbox distributions.
    """

    async def explain_detection(
        self,
        inference_result: dict[str, Any],
        prompt: str,
        threshold: float,
    ) -> dict[str, Any]:
        detections = inference_result.get("detections", [])
        all_confidences = [d.get("confidence", 0.0) for d in detections]
        above = [d for d in detections if d.get("confidence", 0) >= threshold]
        below = [d for d in detections if d.get("confidence", 0) < threshold]

        avg_conf = sum(all_confidences) / len(all_confidences) if all_confidences else 0.0
        prompt_terms = [t.strip() for t in prompt.split() if len(t) > 2]

        explanation = {
            "detections_returned": len(above),
            "detections_below_threshold": len(below),
            "threshold": threshold,
            "avg_confidence": round(avg_conf, 3),
            "prompt_keywords": prompt_terms,
            "notes": [],
        }

        if avg_conf > 0.8:
            explanation["notes"].append(
                "High-confidence detections — model and scene conditions are optimal."
            )
        elif avg_conf > 0.5:
            explanation["notes"].append(
                "Moderate confidence — some uncertainty; verify edge-case detections manually."
            )
        else:
            explanation["notes"].append(
                "Low average confidence — scene or model conditions may be suboptimal."
            )

        if below:
            missed_labels = [d.get("label", "?") for d in below[:3]]
            explanation["notes"].append(
                f"Objects below threshold ({', '.join(missed_labels)}) were suppressed. "
                f"Consider lowering threshold or improving scene conditions."
            )

        logger.debug(
            "inference_explainer.explain_detection above=%d below=%d avg_conf=%.3f",
            len(above),
            len(below),
            avg_conf,
        )
        return explanation

    async def explain_confidence_drop(
        self,
        recent_confidences: list[float],
        baseline_confidence: float,
    ) -> dict[str, Any]:
        if not recent_confidences:
            return {"error": "no_data"}

        recent_avg = sum(recent_confidences) / len(recent_confidences)
        drop = baseline_confidence - recent_avg
        pct_drop = (drop / baseline_confidence * 100) if baseline_confidence > 0 else 0

        # Heuristic cause detection based on magnitude and pattern
        likely_causes: list[str] = []
        if pct_drop > 40:
            likely_causes.append(_CONFIDENCE_DROP_CAUSES[0][1])  # motion blur
            likely_causes.append(_CONFIDENCE_DROP_CAUSES[1][1])  # lighting change
        elif pct_drop > 20:
            likely_causes.append(_CONFIDENCE_DROP_CAUSES[2][1])  # occlusion
            likely_causes.append(_CONFIDENCE_DROP_CAUSES[1][1])
        elif pct_drop > 10:
            likely_causes.append(_CONFIDENCE_DROP_CAUSES[3][1])  # model drift

        severity = "critical" if pct_drop > 40 else "warning" if pct_drop > 20 else "notice"

        result = {
            "baseline": round(baseline_confidence, 3),
            "recent_avg": round(recent_avg, 3),
            "absolute_drop": round(drop, 3),
            "percent_drop": round(pct_drop, 1),
            "severity": severity,
            "likely_causes": likely_causes,
            "recommendation": (
                "Inspect camera feed and trigger model health check"
                if severity in ("critical", "warning")
                else "Monitor for further degradation"
            ),
        }
        logger.debug(
            "explain_confidence_drop baseline=%.3f recent=%.3f drop=%.1f%%",
            baseline_confidence,
            recent_avg,
            pct_drop,
        )
        return result

    async def generate_attention_map_description(
        self,
        bounding_boxes: list[dict[str, Any]],
        frame_width: int,
        frame_height: int,
    ) -> str:
        if not bounding_boxes:
            return "No detections — full frame attention is diffuse."

        # Compute bbox centroids and region labels
        regions: list[str] = []
        for bbox in bounding_boxes[:5]:
            cx = (bbox.get("x1", 0) + bbox.get("x2", 0)) / 2
            cy = (bbox.get("y1", 0) + bbox.get("y2", 0)) / 2
            h_zone = "left" if cx < 0.33 else "center" if cx < 0.67 else "right"
            v_zone = "upper" if cy < 0.33 else "middle" if cy < 0.67 else "lower"
            label = bbox.get("label", "object")
            regions.append(f"{label} ({v_zone}-{h_zone})")

        description = (
            f"Model attention focused on {len(bounding_boxes)} region(s): "
            + ", ".join(regions)
            + f". Frame dimensions: {frame_width}×{frame_height}px."
        )
        logger.debug(
            "attention_map_description detections=%d", len(bounding_boxes)
        )
        return description
