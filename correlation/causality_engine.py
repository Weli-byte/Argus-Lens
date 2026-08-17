"""
CausalityEngine — distinguishes correlation from causation.
Implements Granger causality via scipy's VAR-based F-test wrapper.
Falls back to lag-correlation heuristic if scipy unavailable.
"""

from __future__ import annotations

import logging
from typing import Any

from correlation.temporal_correlator import TemporalCorrelator

logger = logging.getLogger(__name__)

try:
    from statsmodels.tsa.stattools import grangercausalitytests  # type: ignore[import]
    import numpy as np  # type: ignore[import]
    _STATSMODELS_AVAILABLE = True
except ImportError:
    _STATSMODELS_AVAILABLE = False
    np = None  # type: ignore[assignment]


class CausalityEngine:
    """
    Tests whether one time series Granger-causes another,
    and extracts causal chains from ordered event sequences.
    """

    def __init__(self, temporal_correlator: TemporalCorrelator) -> None:
        self._temporal = temporal_correlator

    async def test_granger_causality(
        self,
        cause_series: list[float],
        effect_series: list[float],
        max_lag: int = 10,
    ) -> dict[str, Any]:
        """
        Test: does cause_series improve prediction of effect_series?
        Returns {is_causal, p_value, optimal_lag, confidence}.
        Uses statsmodels if available, else lag-correlation heuristic.
        """
        if len(cause_series) < max_lag + 4 or len(effect_series) < max_lag + 4:
            return {
                "is_causal": False,
                "p_value": 1.0,
                "optimal_lag": 0,
                "confidence": 0.0,
                "method": "insufficient_data",
            }

        if _STATSMODELS_AVAILABLE and np is not None:
            return await self._granger_statsmodels(cause_series, effect_series, max_lag)
        else:
            return await self._granger_heuristic(cause_series, effect_series, max_lag)

    async def identify_causal_chain(
        self, events: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """
        Given an ordered list of events, identify causal links A→B
        where A precedes B and their type combination recurs.
        Returns a list of causal link dicts.
        """
        if len(events) < 2:
            return []

        causal_links: list[dict[str, Any]] = []
        recurring = await self._temporal.detect_recurring_sequences(min_occurrences=2)
        recurring_pairs = {
            (s["sequence"][0], s["sequence"][1]) for s in recurring if len(s["sequence"]) >= 2
        }

        for i in range(len(events) - 1):
            a, b = events[i], events[i + 1]
            pair = (a.get("type", ""), b.get("type", ""))
            if pair in recurring_pairs:
                lag = b.get("timestamp", 0) - a.get("timestamp", 0)
                causal_links.append(
                    {
                        "cause": a,
                        "effect": b,
                        "lag_seconds": round(lag, 2),
                        "relation": f"{pair[0]} → {pair[1]}",
                        "evidence": "recurring temporal sequence",
                    }
                )

        logger.debug(
            "causality_engine.causal_chain events=%d links=%d",
            len(events),
            len(causal_links),
        )
        return causal_links

    # ------------------------------------------------------------------
    # Internal implementations
    # ------------------------------------------------------------------

    async def _granger_statsmodels(
        self,
        cause: list[float],
        effect: list[float],
        max_lag: int,
    ) -> dict[str, Any]:
        try:
            data = np.column_stack([effect, cause])
            results = grangercausalitytests(data, maxlag=max_lag, verbose=False)

            best_lag = 1
            best_p = 1.0
            for lag, res in results.items():
                p = res[0]["ssr_ftest"][1]
                if p < best_p:
                    best_p = p
                    best_lag = lag

            is_causal = best_p < 0.05
            confidence = max(0.0, 1.0 - best_p) if is_causal else 0.0
            logger.debug(
                "granger_statsmodels p=%.4f lag=%d is_causal=%s",
                best_p,
                best_lag,
                is_causal,
            )
            return {
                "is_causal": is_causal,
                "p_value": round(best_p, 4),
                "optimal_lag": best_lag,
                "confidence": round(confidence, 3),
                "method": "granger_f_test",
            }
        except Exception as exc:
            logger.warning("granger_statsmodels failed: %s — falling back to heuristic", exc)
            return await self._granger_heuristic(cause, effect, max_lag)

    async def _granger_heuristic(
        self,
        cause: list[float],
        effect: list[float],
        max_lag: int,
    ) -> dict[str, Any]:
        """
        Heuristic: if cause at lag L has Pearson|r| > 0.7 with effect[L:],
        we declare it likely causal.
        """
        best_corr, best_lag = await self._temporal.compute_lag_correlation(
            cause, effect, max_lag=max_lag
        )
        is_causal = abs(best_corr) > 0.70
        # Approximate p-value proxy from |r|: p ≈ 2*(1 - |r|)
        p_proxy = max(0.001, 2.0 * (1.0 - abs(best_corr)))
        logger.debug(
            "granger_heuristic corr=%.4f lag=%d is_causal=%s",
            best_corr,
            best_lag,
            is_causal,
        )
        return {
            "is_causal": is_causal,
            "p_value": round(p_proxy, 4),
            "optimal_lag": best_lag,
            "confidence": round(abs(best_corr), 3),
            "method": "lag_correlation_heuristic",
        }
