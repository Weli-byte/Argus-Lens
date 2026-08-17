"""
AnomalyCorrelator — groups independent anomalies into clusters
and computes composite severity + root cause.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from correlation.temporal_correlator import TemporalCorrelator
from intelligence.semantic_correlator import SemanticCorrelator
from intelligence.types import InsightSeverity

logger = logging.getLogger(__name__)

_SEVERITY_RANK = {
    "LOW": 1,
    "MEDIUM": 2,
    "HIGH": 3,
    "CRITICAL": 4,
    "EMERGENCY": 5,
}

_RANK_SEVERITY = {v: k for k, v in _SEVERITY_RANK.items()}


class AnomalyCorrelator:
    """
    Clusters anomalies by time window + semantic proximity.
    Computes composite severity and identifies root-cause event.
    """

    def __init__(
        self,
        temporal_correlator: TemporalCorrelator,
        semantic_correlator: SemanticCorrelator,
    ) -> None:
        self._temporal = temporal_correlator
        self._semantic = semantic_correlator

    async def cluster_anomalies(
        self,
        anomalies: list[dict[str, Any]],
        time_window_seconds: float = 120,
    ) -> list[list[dict[str, Any]]]:
        """
        Greedy temporal clustering.
        Sort by timestamp, merge into cluster if within time_window of last entry.
        """
        if not anomalies:
            return []

        sorted_a = sorted(
            anomalies,
            key=lambda a: a.get("timestamp", time.time()),
        )

        clusters: list[list[dict[str, Any]]] = []
        current_cluster: list[dict[str, Any]] = [sorted_a[0]]
        window_end = sorted_a[0].get("timestamp", 0) + time_window_seconds

        for anomaly in sorted_a[1:]:
            ts = anomaly.get("timestamp", 0)
            if ts <= window_end:
                current_cluster.append(anomaly)
            else:
                clusters.append(current_cluster)
                current_cluster = [anomaly]
                window_end = ts + time_window_seconds

        if current_cluster:
            clusters.append(current_cluster)

        logger.debug(
            "anomaly_correlator.cluster input=%d clusters=%d",
            len(anomalies),
            len(clusters),
        )
        return clusters

    async def compute_composite_severity(
        self, anomaly_cluster: list[dict[str, Any]]
    ) -> InsightSeverity:
        """
        Composite severity is determined by:
        1. Maximum individual severity
        2. Cluster size bonus (3+ anomalies → escalate by 1 level)
        """
        if not anomaly_cluster:
            return InsightSeverity.INFO

        max_rank = max(
            _SEVERITY_RANK.get(a.get("severity", "LOW"), 1)
            for a in anomaly_cluster
        )

        # Cluster-size escalation
        if len(anomaly_cluster) >= 3:
            max_rank = min(5, max_rank + 1)

        severity_str = _RANK_SEVERITY.get(max_rank, "INFO")
        severity_map = {
            "LOW": InsightSeverity.INFO,
            "MEDIUM": InsightSeverity.NOTICE,
            "HIGH": InsightSeverity.WARNING,
            "CRITICAL": InsightSeverity.CRITICAL,
            "EMERGENCY": InsightSeverity.EMERGENCY,
        }
        result = severity_map.get(severity_str, InsightSeverity.INFO)
        logger.debug(
            "anomaly_correlator.composite_severity cluster_size=%d result=%s",
            len(anomaly_cluster),
            result.value,
        )
        return result

    async def find_root_cause(
        self, anomaly_cluster: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """
        Root cause = earliest anomaly in the cluster.
        Secondary indicators: highest severity, most referenced type.
        """
        if not anomaly_cluster:
            return {}

        sorted_by_time = sorted(
            anomaly_cluster, key=lambda a: a.get("timestamp", time.time())
        )
        earliest = sorted_by_time[0]

        # Count anomaly types
        type_counts: dict[str, int] = {}
        for a in anomaly_cluster:
            t = a.get("type", "unknown")
            type_counts[t] = type_counts.get(t, 0) + 1
        dominant_type = max(type_counts, key=lambda k: type_counts[k])

        return {
            "root_event": earliest,
            "dominant_type": dominant_type,
            "cluster_size": len(anomaly_cluster),
            "time_span_seconds": round(
                sorted_by_time[-1].get("timestamp", 0)
                - earliest.get("timestamp", 0),
                2,
            ),
            "explanation": (
                f"Cluster of {len(anomaly_cluster)} anomaly(ies) initiated by "
                f"'{earliest.get('type', 'unknown')}' event; "
                f"dominant type: '{dominant_type}'."
            ),
        }
