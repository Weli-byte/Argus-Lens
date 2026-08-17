"""
Inference Drift Detector — statistical monitoring of model confidence,
output distribution, and embedding similarity over a sliding window.
"""

from __future__ import annotations

import asyncio
import math
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
from loguru import logger
from prometheus_client import Counter, Gauge

# ---------------------------------------------------------------------------
# Prometheus
# ---------------------------------------------------------------------------

_DRIFT_ALERT = Counter(
    "arguslens_model_drift_alert_total",
    "Number of drift alerts raised",
    ["model_id", "alert_type"],
)
_HEALTH_SCORE = Gauge(
    "arguslens_model_health_score",
    "Model health score in [0, 1]",
    ["model_id"],
)

# ---------------------------------------------------------------------------
# Domain types
# ---------------------------------------------------------------------------


@dataclass
class DriftAlert:
    model_id: str
    alert_type: str          # confidence_degradation | embedding_drift | distribution_shift
    severity: float          # 0.0 (low) … 1.0 (critical)
    details: str
    timestamp: float = field(default_factory=time.time)


# ---------------------------------------------------------------------------
# Detector
# ---------------------------------------------------------------------------


class DriftDetector:
    """
    Online drift detector that maintains a sliding window of inference outputs
    and raises alerts when statistical properties shift beyond *alert_threshold*.

    Window layout (total = window_size):
        baseline : first (window_size - recent_window) samples
        recent   : last  recent_window samples
    """

    _RECENT_WINDOW = 100   # samples considered "recent"

    def __init__(
        self,
        model_id: str,
        window_size: int = 1000,
        alert_threshold: float = 0.15,
    ) -> None:
        self.model_id = model_id
        self.window_size = window_size
        self.alert_threshold = alert_threshold

        self._confidence_history: deque[float] = deque(maxlen=window_size)
        self._embedding_history: deque[np.ndarray] = deque(maxlen=window_size)
        self._output_history: deque[int] = deque(maxlen=window_size)  # argmax class labels

        self._alert_queue: asyncio.Queue[DriftAlert] = asyncio.Queue()
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Data ingestion
    # ------------------------------------------------------------------

    async def record_inference(
        self,
        output_logits: np.ndarray,
        confidence: float,
        embedding: np.ndarray,
    ) -> None:
        """Record a single inference output for drift tracking."""
        async with self._lock:
            self._confidence_history.append(float(confidence))
            self._output_history.append(int(np.argmax(output_logits)))
            # Normalise embedding to unit vector for cosine comparison
            norm = np.linalg.norm(embedding)
            self._embedding_history.append(
                embedding / norm if norm > 1e-9 else embedding
            )

    # ------------------------------------------------------------------
    # Confidence drift
    # ------------------------------------------------------------------

    def detect_confidence_degradation(self) -> Optional[DriftAlert]:
        """
        Compare the mean confidence of the *recent* window against the
        *baseline* window.  Alert when the absolute mean shift exceeds
        *alert_threshold*.
        """
        if len(self._confidence_history) < self._RECENT_WINDOW + 10:
            return None

        arr = np.array(self._confidence_history)
        baseline = arr[: -self._RECENT_WINDOW]
        recent = arr[-self._RECENT_WINDOW :]

        baseline_mean = float(np.mean(baseline))
        recent_mean = float(np.mean(recent))
        shift = baseline_mean - recent_mean  # positive = degradation

        if shift > self.alert_threshold:
            severity = min(shift / (self.alert_threshold * 2), 1.0)
            return DriftAlert(
                model_id=self.model_id,
                alert_type="confidence_degradation",
                severity=severity,
                details=(
                    f"Confidence dropped from baseline={baseline_mean:.3f} "
                    f"to recent={recent_mean:.3f} (shift={shift:.3f})"
                ),
            )
        return None

    # ------------------------------------------------------------------
    # Embedding drift
    # ------------------------------------------------------------------

    def detect_embedding_drift(self) -> Optional[DriftAlert]:
        """
        Measure cosine similarity between baseline and recent embedding
        centroids.  Alert when similarity falls below (1 - alert_threshold).
        """
        if len(self._embedding_history) < self._RECENT_WINDOW + 10:
            return None

        embeddings = list(self._embedding_history)
        baseline_arr = np.stack(embeddings[: -self._RECENT_WINDOW])
        recent_arr = np.stack(embeddings[-self._RECENT_WINDOW :])

        baseline_centroid = baseline_arr.mean(axis=0)
        recent_centroid = recent_arr.mean(axis=0)

        # Cosine similarity of centroids
        denom = np.linalg.norm(baseline_centroid) * np.linalg.norm(recent_centroid)
        if denom < 1e-9:
            return None

        similarity = float(np.dot(baseline_centroid, recent_centroid) / denom)
        drift = 1.0 - similarity  # 0 = identical, 1 = orthogonal

        if drift > self.alert_threshold:
            severity = min(drift / (self.alert_threshold * 2), 1.0)
            return DriftAlert(
                model_id=self.model_id,
                alert_type="embedding_drift",
                severity=severity,
                details=(
                    f"Embedding centroid cosine similarity={similarity:.3f} "
                    f"(drift={drift:.3f})"
                ),
            )
        return None

    # ------------------------------------------------------------------
    # Output distribution shift
    # ------------------------------------------------------------------

    def detect_output_distribution_shift(self) -> Optional[DriftAlert]:
        """
        Compare the output class distribution of baseline vs recent using
        Jensen-Shannon divergence (bounded [0, 1], symmetric).
        """
        if len(self._output_history) < self._RECENT_WINDOW + 10:
            return None

        labels = list(self._output_history)
        n_classes = max(labels) + 1
        if n_classes < 2:
            return None

        baseline_labels = labels[: -self._RECENT_WINDOW]
        recent_labels = labels[-self._RECENT_WINDOW :]

        def _dist(seq: list[int]) -> np.ndarray:
            counts = np.zeros(n_classes, dtype=float)
            for c in seq:
                if 0 <= c < n_classes:
                    counts[c] += 1
            total = counts.sum()
            return counts / total if total > 0 else counts

        p = _dist(baseline_labels) + 1e-10
        q = _dist(recent_labels) + 1e-10
        p /= p.sum()
        q /= q.sum()

        m = 0.5 * (p + q)
        jsd = 0.5 * _kl(p, m) + 0.5 * _kl(q, m)

        if jsd > self.alert_threshold:
            severity = min(jsd / (self.alert_threshold * 2), 1.0)
            return DriftAlert(
                model_id=self.model_id,
                alert_type="distribution_shift",
                severity=severity,
                details=f"Output distribution JSD={jsd:.4f}",
            )
        return None

    # ------------------------------------------------------------------
    # Alert escalation
    # ------------------------------------------------------------------

    async def escalate_alert(self, alert: DriftAlert) -> None:
        """Log a drift alert and increment the Prometheus counter."""
        logger.warning(
            "Drift alert model={} type={} severity={:.2f} details={}",
            alert.model_id,
            alert.alert_type,
            alert.severity,
            alert.details,
        )
        _DRIFT_ALERT.labels(
            model_id=alert.model_id, alert_type=alert.alert_type
        ).inc()

    async def run_all_checks(self) -> list[DriftAlert]:
        """Run all detectors and escalate any alerts found."""
        alerts: list[DriftAlert] = []
        for check in (
            self.detect_confidence_degradation,
            self.detect_embedding_drift,
            self.detect_output_distribution_shift,
        ):
            alert = check()
            if alert:
                alerts.append(alert)
                await self.escalate_alert(alert)

        score = self.get_model_health_score()
        _HEALTH_SCORE.labels(model_id=self.model_id).set(score)
        return alerts

    # ------------------------------------------------------------------
    # Health score
    # ------------------------------------------------------------------

    def get_model_health_score(self) -> float:
        """
        Composite health score in [0.0, 1.0].
        Penalises each active drift dimension by a fraction of the threshold.
        """
        if len(self._confidence_history) < 20:
            return 1.0  # insufficient data → assume healthy

        penalty = 0.0

        # Confidence component
        arr = np.array(self._confidence_history)
        if len(arr) >= self._RECENT_WINDOW + 10:
            shift = float(np.mean(arr[: -self._RECENT_WINDOW])) - float(
                np.mean(arr[-self._RECENT_WINDOW :])
            )
            penalty += max(0.0, shift / self.alert_threshold) * 0.4

        # Embedding component (cosine drift)
        if len(self._embedding_history) >= self._RECENT_WINDOW + 10:
            embs = list(self._embedding_history)
            bc = np.stack(embs[: -self._RECENT_WINDOW]).mean(axis=0)
            rc = np.stack(embs[-self._RECENT_WINDOW :]).mean(axis=0)
            denom = np.linalg.norm(bc) * np.linalg.norm(rc)
            if denom > 1e-9:
                sim = float(np.dot(bc, rc) / denom)
                drift = 1.0 - sim
                penalty += min(drift / self.alert_threshold, 1.0) * 0.4

        penalty = min(penalty, 1.0)
        return round(1.0 - penalty, 4)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _kl(p: np.ndarray, q: np.ndarray) -> float:
    """KL divergence D(P||Q); assumes both are normalised and non-zero."""
    return float(np.sum(p * np.log(p / q)))
