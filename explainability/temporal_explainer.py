"""
TemporalExplainer — human-readable explanations for metric anomalies,
trends, and forecasts. Pure deterministic — no mocks.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

_METRIC_NAMES = {
    "fatigue_score": "fatigue level",
    "focus_score": "focus level",
    "cognitive_load": "cognitive load",
    "blink_frequency": "blink frequency",
    "heart_rate": "heart rate",
    "eye_pressure": "eye pressure",
    "neural_latency": "neural response latency",
}


class TemporalExplainer:
    """
    Converts numeric temporal anomaly data into operator-readable text.
    """

    async def explain_metric_anomaly(
        self,
        metric_name: str,
        value: float,
        context: dict[str, Any],
    ) -> str:
        mean = context.get("historical_mean", 0.5)
        std = context.get("historical_std", 0.1)

        if std == 0:
            z = 0.0
        else:
            z = abs(value - mean) / std

        readable_name = _METRIC_NAMES.get(metric_name, metric_name.replace("_", " "))
        direction = "above" if value > mean else "below"
        pct = abs((value - mean) / mean * 100) if mean != 0 else 0

        if z >= 3.0:
            severity_text = "extremely unusual"
            action = "Immediate review is strongly recommended."
        elif z >= 2.0:
            severity_text = "significantly elevated"
            action = "Investigation warranted."
        elif z >= 1.5:
            severity_text = "mildly elevated"
            action = "Monitor closely for further changes."
        else:
            severity_text = "within normal range"
            action = "No action required."

        return (
            f"The {readable_name} is {severity_text} at {value:.3f} "
            f"({pct:.1f}% {direction} baseline mean of {mean:.3f}). "
            f"Z-score: {z:.2f}. {action}"
        )

    async def explain_trend(
        self,
        metric_name: str,
        trend_direction: str,
        rate: float,
        window_seconds: int,
    ) -> str:
        readable_name = _METRIC_NAMES.get(metric_name, metric_name.replace("_", " "))
        window_min = window_seconds / 60.0
        per_min_rate = rate * 60  # convert per-sample rate to per-minute

        direction_text = {
            "increasing": "rising",
            "decreasing": "falling",
            "stable": "stable",
        }.get(trend_direction, trend_direction)

        if trend_direction == "stable":
            return (
                f"The {readable_name} has remained {direction_text} "
                f"over the last {window_min:.1f} minutes."
            )

        urgency = ""
        if abs(per_min_rate) > 0.05:
            urgency = " This rate of change is rapid and warrants attention."
        elif abs(per_min_rate) > 0.02:
            urgency = " The trend is moderate; continued monitoring advised."

        return (
            f"The {readable_name} is {direction_text} at a rate of "
            f"{abs(per_min_rate):.4f} units per minute "
            f"over the last {window_min:.1f}-minute window.{urgency}"
        )

    async def generate_forecast_explanation(self, forecast: dict[str, Any]) -> str:
        risk = forecast.get("risk_level", "UNKNOWN")
        projected = forecast.get("projected_value")
        horizon = forecast.get("time_horizon_minutes", 1)
        confidence = forecast.get("confidence", 0.5)
        trend = forecast.get("trend", "stable")

        if projected is None:
            return "Insufficient data to generate a forecast."

        risk_context = {
            "DANGER": "critical threshold",
            "WARNING": "warning threshold",
            "CAUTION": "caution zone",
            "SAFE": "normal operating range",
        }.get(risk, "an unknown threshold")

        trend_clause = ""
        if trend == "increasing":
            trend_clause = " The trend is worsening."
        elif trend == "decreasing":
            trend_clause = " The trend is improving."

        return (
            f"If the current trend continues, the monitored metric is projected to reach "
            f"{projected:.3f} within {horizon} minute(s), which falls in the {risk_context}. "
            f"Forecast confidence: {confidence:.0%}.{trend_clause}"
        )
