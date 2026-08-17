"""
WorkloadPredictor — forecasts future inference request rate using
exponential smoothing (Holt-Winters double smoothing).

Used by AutoScaler to pre-emptively scale before demand peaks,
rather than reacting after saturation.
"""

from __future__ import annotations

import collections
import logging
import time
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

_HISTORY_WINDOW = 120   # max data points retained (e.g. 120 × 30s = 1 hour)
_ALPHA = 0.3            # level smoothing factor
_BETA = 0.1             # trend smoothing factor


@dataclass
class WorkloadForecast:
    current_rps: float
    forecast_rps: float          # predicted rate N steps ahead
    trend: float                 # positive = growing, negative = shrinking
    forecast_horizon_steps: int
    confidence: float            # 0.0–1.0 based on history length
    timestamp: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "current_rps": round(self.current_rps, 3),
            "forecast_rps": round(self.forecast_rps, 3),
            "trend": round(self.trend, 4),
            "forecast_horizon_steps": self.forecast_horizon_steps,
            "confidence": round(self.confidence, 3),
            "timestamp": self.timestamp,
        }


class WorkloadPredictor:
    """
    Holt-Winters double exponential smoothing for request rate forecasting.

    Feed observed request counts with observe(); call forecast() to get
    a prediction N steps ahead.
    """

    def __init__(
        self,
        alpha: float = _ALPHA,
        beta: float = _BETA,
        sample_interval_s: float = 30.0,
    ) -> None:
        self._alpha = alpha
        self._beta = beta
        self._sample_interval_s = sample_interval_s
        self._history: collections.deque[float] = collections.deque(maxlen=_HISTORY_WINDOW)
        self._level: float | None = None
        self._trend: float = 0.0
        self._last_sample_time: float | None = None

    # ------------------------------------------------------------------
    # Data ingestion
    # ------------------------------------------------------------------

    def observe(self, request_count: int, elapsed_s: float | None = None) -> None:
        """
        Record an observed request count over the last sampling interval.
        elapsed_s defaults to self._sample_interval_s if not provided.
        """
        dt = elapsed_s or self._sample_interval_s
        rps = request_count / max(dt, 0.001)
        self._history.append(rps)
        self._update_state(rps)
        self._last_sample_time = time.monotonic()

    def _update_state(self, rps: float) -> None:
        if self._level is None:
            self._level = rps
            self._trend = 0.0
            return
        prev_level = self._level
        self._level = self._alpha * rps + (1 - self._alpha) * (self._level + self._trend)
        self._trend = self._beta * (self._level - prev_level) + (1 - self._beta) * self._trend

    # ------------------------------------------------------------------
    # Forecasting
    # ------------------------------------------------------------------

    def forecast(self, steps_ahead: int = 3) -> WorkloadForecast:
        """
        Predict load steps_ahead sampling intervals into the future.
        Returns confidence=0 if fewer than 5 observations are available.
        """
        n = len(self._history)
        if n == 0:
            return WorkloadForecast(
                current_rps=0.0,
                forecast_rps=0.0,
                trend=0.0,
                forecast_horizon_steps=steps_ahead,
                confidence=0.0,
                timestamp=time.monotonic(),
            )
        current = self._level or (sum(self._history) / n)
        forecast = current + steps_ahead * self._trend
        forecast = max(0.0, forecast)
        confidence = min(1.0, n / 30.0)  # full confidence after 30 observations

        return WorkloadForecast(
            current_rps=current,
            forecast_rps=forecast,
            trend=self._trend,
            forecast_horizon_steps=steps_ahead,
            confidence=confidence,
            timestamp=time.monotonic(),
        )

    def current_rps(self) -> float:
        if not self._history:
            return 0.0
        return self._level or self._history[-1]

    def stats(self) -> dict[str, Any]:
        return {
            "history_length": len(self._history),
            "current_rps": round(self.current_rps(), 3),
            "trend": round(self._trend, 4),
            "alpha": self._alpha,
            "beta": self._beta,
            "sample_interval_s": self._sample_interval_s,
        }
