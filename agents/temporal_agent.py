"""
TemporalAgent — analyses sliding-window temporal metrics and produces forecasts.
"""

from __future__ import annotations

import logging
import statistics
from typing import Any

import redis.asyncio as aioredis

from agents.base_agent import BaseAgent
from intelligence.multimodal_router import MultimodalRouter
from intelligence.types import AgentState, AgentTask, InsightSeverity
from memory.retrieval_manager import RetrievalManager

logger = logging.getLogger(__name__)


class TemporalAgent(BaseAgent):
    """
    Triggered when temporal metrics exceed anomaly threshold.
    Analyses trend window → routes through MultimodalRouter → produces forecast.
    """

    def __init__(
        self,
        agent_id: str,
        redis_client: aioredis.Redis,
        multimodal_router: MultimodalRouter,
        retrieval_manager: RetrievalManager,
        anomaly_agent: "BaseAgent | None" = None,
    ) -> None:
        super().__init__(agent_id, "temporal_agent", redis_client)
        self._router = multimodal_router
        self._retrieval = retrieval_manager
        self._anomaly_agent = anomaly_agent

    def set_anomaly_agent(self, agent: "BaseAgent") -> None:
        self._anomaly_agent = agent

    async def execute(self, task: AgentTask) -> AgentTask:
        task.add_trace("temporal_agent.execute start")
        await self._update_state(AgentState.ANALYZING)

        session_id: str = task.input_data.get("session_id", "unknown")
        temporal_metrics: dict[str, Any] = task.input_data.get("temporal_metrics", {})
        history: list[dict[str, Any]] = task.input_data.get("metrics_history", [])

        # Sliding window analysis
        window_analysis = await self._analyze_sliding_window(history, window_size=60)
        task.add_trace(
            f"temporal_agent.window trend={window_analysis.get('trend')} "
            f"anomalies={window_analysis.get('anomaly_count', 0)}"
        )

        # Enrich temporal_metrics with window analysis
        temporal_metrics["metric_history"] = [
            h.get("fatigue_score", 0.0) for h in history[-60:]
        ]
        temporal_metrics["trend"] = window_analysis.get("trend", "stable")
        temporal_metrics["anomaly_detected"] = window_analysis.get("anomaly_count", 0) > 0

        await self._update_state(AgentState.REASONING)
        result = await self._router.process(
            session_id=session_id,
            temporal_metrics=temporal_metrics,
        )

        # Build forecast
        forecast = self._build_forecast(window_analysis, temporal_metrics)
        result["forecast"] = forecast
        task.output_data = result
        task.add_trace(
            f"temporal_agent.done severity={result.get('insight', {}).get('severity', '?')} "
            f"forecast_risk={forecast.get('risk_level', '?')}"
        )

        # Escalate if critical trend
        insight_sev = result.get("insight", {}).get("severity", "")
        if insight_sev in (InsightSeverity.CRITICAL.value, InsightSeverity.EMERGENCY.value):
            if self._anomaly_agent:
                esc_task = AgentTask(
                    agent_type="anomaly_agent",
                    trigger="temporal_escalation",
                    priority=1,
                    input_data={
                        "session_id": session_id,
                        "anomaly": result.get("insight", {}),
                        "source": "temporal_agent",
                        "window_analysis": window_analysis,
                    },
                )
                await self._anomaly_agent.submit_task(esc_task)

        return task

    async def _analyze_sliding_window(
        self, metrics_history: list[dict[str, Any]], window_size: int = 60
    ) -> dict[str, Any]:
        window = metrics_history[-window_size:] if metrics_history else []
        if not window:
            return {
                "trend": "stable",
                "mean": 0.0,
                "std": 0.0,
                "min": 0.0,
                "max": 0.0,
                "anomaly_count": 0,
                "rate_of_change": 0.0,
                "window_size": 0,
            }

        values: list[float] = [float(m.get("fatigue_score", 0.0)) for m in window]
        mean = statistics.mean(values)
        std = statistics.pstdev(values) if len(values) > 1 else 0.0
        threshold = mean + 2 * std if std > 0 else mean * 1.5
        anomaly_count = sum(1 for v in values if v > threshold)

        rate = (values[-1] - values[0]) / len(values) if len(values) > 1 else 0.0
        if rate > 0.015:
            trend = "increasing"
        elif rate < -0.015:
            trend = "decreasing"
        else:
            trend = "stable"

        return {
            "trend": trend,
            "mean": round(mean, 4),
            "std": round(std, 4),
            "min": round(min(values), 4),
            "max": round(max(values), 4),
            "anomaly_count": anomaly_count,
            "rate_of_change": round(rate, 6),
            "window_size": len(values),
        }

    @staticmethod
    def _build_forecast(
        window: dict[str, Any], current_metrics: dict[str, Any]
    ) -> dict[str, Any]:
        trend = window.get("trend", "stable")
        mean = window.get("mean", 0.5)
        rate = window.get("rate_of_change", 0.0)
        steps = 60  # 60-second horizon
        projected = mean + rate * steps

        if projected > 0.85 or window.get("anomaly_count", 0) >= 5:
            risk_level = "DANGER"
            predicted_events = max(1, window.get("anomaly_count", 1))
        elif projected > 0.65:
            risk_level = "WARNING"
            predicted_events = max(1, window.get("anomaly_count", 0))
        elif projected > 0.45:
            risk_level = "CAUTION"
            predicted_events = 0
        else:
            risk_level = "SAFE"
            predicted_events = 0

        confidence = max(0.3, 1.0 - abs(rate) * 20)

        return {
            "risk_level": risk_level,
            "predicted_events": predicted_events,
            "time_horizon_minutes": 1,
            "confidence": round(confidence, 3),
            "projected_value": round(projected, 4),
            "trend": trend,
        }
