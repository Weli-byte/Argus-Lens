"""
TemporalCorrelator — detects correlations between time-ordered events.
Uses in-process deque buffers + Redis persistence.
Implements lag-based Pearson correlation for time-series pairs.
"""

from __future__ import annotations

import json
import logging
import math
import time
from collections import defaultdict, deque
from typing import Any

import redis.asyncio as aioredis

from intelligence.types import CorrelationResult, CorrelationStrength

logger = logging.getLogger(__name__)


def _pearson(x: list[float], y: list[float]) -> float:
    n = len(x)
    if n < 2:
        return 0.0
    mx, my = sum(x) / n, sum(y) / n
    cov = sum((a - mx) * (b - my) for a, b in zip(x, y))
    sx = math.sqrt(sum((a - mx) ** 2 for a in x))
    sy = math.sqrt(sum((b - my) ** 2 for b in y))
    return cov / (sx * sy) if sx * sy > 0 else 0.0


def _strength(score: float) -> CorrelationStrength:
    abs_s = abs(score)
    if abs_s >= 0.9:
        return CorrelationStrength.CAUSAL
    if abs_s >= 0.7:
        return CorrelationStrength.STRONG
    if abs_s >= 0.5:
        return CorrelationStrength.MODERATE
    return CorrelationStrength.WEAK


class TemporalCorrelator:
    """
    Records timestamped events and finds lag-based correlations.
    Buffer is ephemeral; Redis snapshot preserves cross-restart continuity.
    """

    def __init__(
        self,
        redis_client: aioredis.Redis,
        window_seconds: int = 300,
    ) -> None:
        self._redis = redis_client
        self.window = window_seconds
        self.event_buffer: dict[str, deque] = defaultdict(
            lambda: deque(maxlen=1000)
        )

    async def record_event(
        self,
        event_type: str,
        event_data: dict[str, Any],
        timestamp: float | None = None,
    ) -> None:
        ts = timestamp or time.time()
        record = {"ts": ts, "data": event_data}
        self.event_buffer[event_type].append(record)

        # Persist last 200 events per type to Redis with TTL
        key = f"argus:corr:events:{event_type}"
        pipe = self._redis.pipeline()
        pipe.lpush(key, json.dumps(record))
        pipe.ltrim(key, 0, 199)
        pipe.expire(key, self.window * 2)
        await pipe.execute()
        logger.debug("temporal_correlator.record type=%s ts=%.3f", event_type, ts)

    async def find_correlated_events(
        self,
        anchor_event: dict[str, Any],
        max_lag_seconds: float = 60.0,
    ) -> list[CorrelationResult]:
        anchor_ts = anchor_event.get("timestamp", time.time())
        results: list[CorrelationResult] = []

        for event_type, buf in self.event_buffer.items():
            nearby = [
                e for e in buf
                if abs(e["ts"] - anchor_ts) <= max_lag_seconds
            ]
            if len(nearby) < 3:
                continue

            lag = nearby[0]["ts"] - anchor_ts
            proximity_score = max(0.0, 1.0 - abs(lag) / max_lag_seconds)
            if proximity_score < 0.3:
                continue

            result = CorrelationResult(
                event_a=anchor_event,
                event_b={"event_type": event_type, "count": len(nearby)},
                strength=_strength(proximity_score),
                score=round(proximity_score, 4),
                lag_seconds=round(lag, 2),
                explanation=(
                    f"{len(nearby)} '{event_type}' events within "
                    f"{max_lag_seconds:.0f}s of anchor (lag={lag:.1f}s)"
                ),
            )
            results.append(result)

        logger.debug(
            "temporal_correlator.find_correlated anchor_ts=%.3f results=%d",
            anchor_ts,
            len(results),
        )
        return sorted(results, key=lambda r: r.score, reverse=True)

    async def detect_recurring_sequences(
        self, min_occurrences: int = 3
    ) -> list[dict[str, Any]]:
        """
        Look for A→B event-type chains that appear at least min_occurrences times.
        Sliding 2-event window over time-ordered events.
        """
        all_events: list[tuple[float, str]] = []
        for etype, buf in self.event_buffer.items():
            for record in buf:
                all_events.append((record["ts"], etype))

        all_events.sort(key=lambda x: x[0])

        pair_counts: dict[tuple[str, str], int] = defaultdict(int)
        for i in range(len(all_events) - 1):
            ts_a, type_a = all_events[i]
            ts_b, type_b = all_events[i + 1]
            if ts_b - ts_a <= 120:  # within 2-minute window
                pair_counts[(type_a, type_b)] += 1

        sequences = [
            {
                "sequence": list(pair),
                "occurrences": count,
                "description": f"'{pair[0]}' followed by '{pair[1]}'",
            }
            for pair, count in pair_counts.items()
            if count >= min_occurrences
        ]
        return sorted(sequences, key=lambda s: s["occurrences"], reverse=True)

    async def compute_lag_correlation(
        self,
        series_a: list[float],
        series_b: list[float],
        max_lag: int = 30,
    ) -> tuple[float, int]:
        """
        Pearson correlation at each lag offset.
        Returns (best_correlation, best_lag_steps).
        """
        if len(series_a) < max_lag + 2 or len(series_b) < max_lag + 2:
            return 0.0, 0

        best_corr = 0.0
        best_lag = 0

        for lag in range(-max_lag, max_lag + 1):
            if lag >= 0:
                a_slice = series_a[: len(series_a) - lag] if lag else series_a
                b_slice = series_b[lag:] if lag else series_b
            else:
                a_slice = series_a[-lag:]
                b_slice = series_b[: len(series_b) + lag]

            n = min(len(a_slice), len(b_slice))
            if n < 2:
                continue

            corr = _pearson(list(a_slice[:n]), list(b_slice[:n]))
            if abs(corr) > abs(best_corr):
                best_corr = corr
                best_lag = lag

        logger.debug(
            "compute_lag_correlation best_corr=%.4f best_lag=%d",
            best_corr,
            best_lag,
        )
        return round(best_corr, 4), best_lag
