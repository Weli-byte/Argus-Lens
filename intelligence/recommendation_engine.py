"""
RecommendationEngine — generates prioritised, actionable recommendations
from an AIInsight and its ReasoningContext.
Historical effectiveness is queried from LTM to weight recommendations.
"""

from __future__ import annotations

import logging
from typing import Any

from intelligence.types import AIInsight, InsightSeverity, ReasoningContext
from memory.long_term_memory import LongTermMemory
from memory.retrieval_manager import RetrievalManager

logger = logging.getLogger(__name__)

# Severity → default priority band (1 = highest urgency)
_SEVERITY_PRIORITY: dict[InsightSeverity, int] = {
    InsightSeverity.EMERGENCY: 1,
    InsightSeverity.CRITICAL: 1,
    InsightSeverity.WARNING: 2,
    InsightSeverity.NOTICE: 3,
    InsightSeverity.INFO: 4,
}

# Pattern name → rule-based recommendations
_PATTERN_RECS: dict[str, list[dict[str, Any]]] = {
    "medical_emergency_suspect": [
        {"action": "Immediately check on the monitored subject", "estimated_impact": "High — confirms or rules out acute medical event"},
        {"action": "Alert on-site emergency personnel", "estimated_impact": "High — enables rapid response"},
        {"action": "Capture and timestamp current frame for incident record", "estimated_impact": "Medium — supports post-incident review"},
    ],
    "fainting_risk": [
        {"action": "Prompt operator break or position change within 2 minutes", "estimated_impact": "High — prevents vasovagal episode"},
        {"action": "Verify ambient temperature and ventilation", "estimated_impact": "Medium — addresses environmental causes"},
    ],
    "scene_change": [
        {"action": "Run camera calibration check", "estimated_impact": "Medium — eliminates sensor drift as cause"},
        {"action": "Review recent environment audit log", "estimated_impact": "Low — provides context"},
    ],
    "model_drift": [
        {"action": "Reload model checkpoint or trigger hot-reload", "estimated_impact": "High — restores detection quality"},
        {"action": "Inspect recent inference confidence trend for gradual decay", "estimated_impact": "Medium — distinguishes drift from acute event"},
    ],
    "high_fatigue": [
        {"action": "Schedule mandatory rest break (≥10 minutes)", "estimated_impact": "High — reduces error probability"},
        {"action": "Adjust task complexity or reduce multitasking load", "estimated_impact": "Medium — lowers cognitive demand"},
    ],
    "system_degraded": [
        {"action": "Inspect GPU VRAM headroom — free memory if >90% utilised", "estimated_impact": "High — prevents OOM inference failure"},
        {"action": "Drain inference queue of stale frames", "estimated_impact": "Medium — reduces processing latency"},
    ],
}

_DEFAULT_RECS: list[dict[str, Any]] = [
    {"action": "Review live feed and confirm signal integrity", "estimated_impact": "Medium"},
    {"action": "Check system logs for upstream errors in the last 5 minutes", "estimated_impact": "Low"},
]


class RecommendationEngine:
    """
    Combines rule-based templates with LTM-backed historical effectiveness
    to produce ranked, actionable recommendations.
    """

    def __init__(
        self,
        long_term_memory: LongTermMemory,
        retrieval_manager: RetrievalManager,
    ) -> None:
        self._ltm = long_term_memory
        self._retrieval = retrieval_manager

    async def generate_recommendations(
        self,
        insight: AIInsight,
        context: ReasoningContext,
    ) -> list[dict[str, Any]]:
        """
        Build recommendations from detected patterns, enrich with
        historical effectiveness, then sort by priority.
        """
        context.add_trace(
            f"rec_engine.start severity={insight.severity.value} steps={len(insight.reasoning_steps)}"
        )

        raw_recs: list[dict[str, Any]] = []

        # Extract pattern names from insight reasoning steps
        pattern_names = self._extract_pattern_names(insight.reasoning_steps)
        for pname in pattern_names:
            recs = _PATTERN_RECS.get(pname, _DEFAULT_RECS)
            for r in recs:
                raw_recs.append(
                    {
                        "action": r["action"],
                        "priority": _SEVERITY_PRIORITY.get(insight.severity, 3),
                        "reasoning": f"Triggered by detected pattern: {pname}",
                        "estimated_impact": r.get("estimated_impact", "Unknown"),
                        "based_on_history": False,
                        "historical_effectiveness": 0.5,
                    }
                )

        if not raw_recs:
            for r in _DEFAULT_RECS:
                raw_recs.append(
                    {
                        "action": r["action"],
                        "priority": _SEVERITY_PRIORITY.get(insight.severity, 4),
                        "reasoning": "Default monitoring recommendation",
                        "estimated_impact": r.get("estimated_impact", "Low"),
                        "based_on_history": False,
                        "historical_effectiveness": 0.5,
                    }
                )

        # Enrich with historical effectiveness from LTM
        for rec in raw_recs:
            eff = await self._get_historical_effectiveness(rec["action"])
            rec["historical_effectiveness"] = round(eff, 3)
            if eff > 0.6:
                rec["based_on_history"] = True
                rec["reasoning"] += f" (historically {eff:.0%} effective)"

        ranked = await self._prioritize_recommendations(raw_recs)

        context.add_trace(f"rec_engine.done recommendations={len(ranked)}")
        logger.info(
            "rec_engine recommendations=%d severity=%s",
            len(ranked),
            insight.severity.value,
        )
        return ranked

    async def _get_historical_effectiveness(self, action_type: str) -> float:
        """
        Query LTM for past instances of this action and their outcomes.
        Returns effectiveness ratio 0.0–1.0; defaults to 0.5 if no history.
        """
        try:
            results = await self._ltm.semantic_search(
                query=f"action effectiveness outcome: {action_type}",
                top_k=5,
                min_similarity=0.6,
            )
            if not results:
                return 0.5
            # Importance score approximates outcome quality
            scores = [entry.importance_score for entry, _ in results]
            return sum(scores) / len(scores)
        except Exception as exc:
            logger.warning("rec_engine.historical_effectiveness error: %s", exc)
            return 0.5

    async def _prioritize_recommendations(
        self, recommendations: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """
        Sort by: priority ASC, then historical_effectiveness DESC.
        """

        def sort_key(r: dict[str, Any]) -> tuple[int, float]:
            return (r.get("priority", 5), -r.get("historical_effectiveness", 0.0))

        return sorted(recommendations, key=sort_key)

    @staticmethod
    def _extract_pattern_names(reasoning_steps: list[str]) -> list[str]:
        """Extract pattern identifiers from step strings like 'pattern:medical_emergency_suspect'."""
        names: list[str] = []
        for step in reasoning_steps:
            if "pattern:" in step:
                parts = step.split("pattern:")
                if len(parts) > 1:
                    name = parts[1].split()[0].strip()
                    if name:
                        names.append(name)
        return names
