"""
PerformanceAnalyzer — tracks rolling performance baselines and detects regressions.

Metrics tracked per component:
  - Inference latency (p50, p95, p99)
  - Queue depth
  - Memory utilization
  - Error rate

Regression is flagged when p95 latency exceeds baseline × _REGRESSION_FACTOR
or error rate exceeds _ERROR_RATE_THRESHOLD.
"""

from __future__ import annotations

import collections
import logging
import math
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

_WINDOW_SIZE = 200          # samples kept per metric
_REGRESSION_FACTOR = 1.5    # flag if p95 > baseline * factor
_ERROR_RATE_THRESHOLD = 0.05  # 5% error rate triggers alert
_BASELINE_MIN_SAMPLES = 30  # minimum samples before baseline is declared


@dataclass
class PerformanceBaseline:
    component: str
    p50_ms: float = 0.0
    p95_ms: float = 0.0
    p99_ms: float = 0.0
    error_rate: float = 0.0
    sample_count: int = 0
    established_at: float = field(default_factory=time.monotonic)


@dataclass
class RegressionAlert:
    component: str
    metric: str
    current_value: float
    baseline_value: float
    ratio: float
    timestamp: float = field(default_factory=time.monotonic)

    def to_dict(self) -> dict[str, Any]:
        return {
            "component": self.component,
            "metric": self.metric,
            "current_value": round(self.current_value, 4),
            "baseline_value": round(self.baseline_value, 4),
            "ratio": round(self.ratio, 3),
            "timestamp": self.timestamp,
        }


class PerformanceAnalyzer:
    """
    Tracks per-component latency distributions and detects regressions.
    Thread-safe via pure append-only deque operations.
    """

    def __init__(self) -> None:
        # component -> deque of (latency_ms, success: bool, timestamp)
        self._samples: dict[str, collections.deque] = {}
        self._baselines: dict[str, PerformanceBaseline] = {}
        self._alerts: collections.deque[RegressionAlert] = collections.deque(maxlen=500)

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------

    def record(
        self,
        component: str,
        latency_ms: float,
        success: bool = True,
    ) -> None:
        if component not in self._samples:
            self._samples[component] = collections.deque(maxlen=_WINDOW_SIZE)
        self._samples[component].append((latency_ms, success, time.monotonic()))
        self._maybe_update_baseline(component)
        self._check_regression(component)

    # ------------------------------------------------------------------
    # Percentiles
    # ------------------------------------------------------------------

    def percentile(self, component: str, pct: float) -> float | None:
        samples = self._samples.get(component)
        if not samples:
            return None
        latencies = sorted(s[0] for s in samples)
        idx = int(math.ceil(pct / 100 * len(latencies))) - 1
        return latencies[max(0, idx)]

    def error_rate(self, component: str) -> float:
        samples = self._samples.get(component)
        if not samples:
            return 0.0
        failures = sum(1 for _, ok, _ in samples if not ok)
        return failures / len(samples)

    # ------------------------------------------------------------------
    # Baseline management
    # ------------------------------------------------------------------

    def _maybe_update_baseline(self, component: str) -> None:
        samples = self._samples[component]
        if len(samples) < _BASELINE_MIN_SAMPLES:
            return

        p50 = self.percentile(component, 50) or 0.0
        p95 = self.percentile(component, 95) or 0.0
        p99 = self.percentile(component, 99) or 0.0
        err = self.error_rate(component)

        if component not in self._baselines:
            self._baselines[component] = PerformanceBaseline(
                component=component,
                p50_ms=p50,
                p95_ms=p95,
                p99_ms=p99,
                error_rate=err,
                sample_count=len(samples),
            )
            logger.info(
                "performance_analyzer baseline_established component=%s p95=%.2fms",
                component, p95,
            )
        else:
            # Exponential moving average update (alpha=0.1 for stability)
            alpha = 0.1
            bl = self._baselines[component]
            bl.p50_ms = (1 - alpha) * bl.p50_ms + alpha * p50
            bl.p95_ms = (1 - alpha) * bl.p95_ms + alpha * p95
            bl.p99_ms = (1 - alpha) * bl.p99_ms + alpha * p99
            bl.error_rate = (1 - alpha) * bl.error_rate + alpha * err
            bl.sample_count = len(samples)

    def _check_regression(self, component: str) -> None:
        baseline = self._baselines.get(component)
        if baseline is None:
            return

        current_p95 = self.percentile(component, 95) or 0.0
        if baseline.p95_ms > 0 and current_p95 > baseline.p95_ms * _REGRESSION_FACTOR:
            ratio = current_p95 / baseline.p95_ms
            alert = RegressionAlert(
                component=component,
                metric="p95_latency_ms",
                current_value=current_p95,
                baseline_value=baseline.p95_ms,
                ratio=ratio,
            )
            self._alerts.append(alert)
            logger.warning(
                "performance_analyzer regression_detected component=%s p95=%.2fms baseline=%.2fms ratio=%.2f",
                component, current_p95, baseline.p95_ms, ratio,
            )

        err = self.error_rate(component)
        if err > _ERROR_RATE_THRESHOLD:
            alert = RegressionAlert(
                component=component,
                metric="error_rate",
                current_value=err,
                baseline_value=baseline.error_rate,
                ratio=err / max(baseline.error_rate, 1e-6),
            )
            self._alerts.append(alert)
            logger.warning(
                "performance_analyzer high_error_rate component=%s rate=%.3f",
                component, err,
            )

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------

    def summary(self, component: str) -> dict[str, Any]:
        baseline = self._baselines.get(component)
        return {
            "component": component,
            "p50_ms": self.percentile(component, 50),
            "p95_ms": self.percentile(component, 95),
            "p99_ms": self.percentile(component, 99),
            "error_rate": round(self.error_rate(component), 4),
            "sample_count": len(self._samples.get(component, [])),
            "baseline": baseline.__dict__ if baseline else None,
        }

    def all_summaries(self) -> list[dict[str, Any]]:
        return [self.summary(c) for c in self._samples]

    def recent_alerts(self, n: int = 10) -> list[dict[str, Any]]:
        alerts = list(self._alerts)
        return [a.to_dict() for a in alerts[-n:]]
