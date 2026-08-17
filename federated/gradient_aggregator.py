"""
GradientAggregator — implements FedAvg (weighted average) and FedProx
aggregation over gradient deltas contributed by edge nodes.

FedAvg formula:
    w_global = sum(n_k / N * delta_k)  for all k nodes

Where n_k is the number of local training samples on node k and N = sum(n_k).

FedProx adds a proximal penalty term to prevent divergence on heterogeneous data.
"""

from __future__ import annotations

import logging
import math
from typing import Any

from edge.types import FederatedUpdate

logger = logging.getLogger(__name__)


class GradientAggregator:
    """
    Aggregates FederatedUpdate objects into a single averaged gradient dict.
    Pure Python — no torch dependency for the aggregation math.
    """

    def __init__(self, method: str = "fedavg", proximal_mu: float = 0.01) -> None:
        if method not in ("fedavg", "fedprox"):
            raise ValueError(f"Unknown aggregation method: {method}")
        self._method = method
        self._proximal_mu = proximal_mu

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def aggregate(
        self,
        updates: list[FederatedUpdate],
        *,
        min_participants: int = 2,
    ) -> dict[str, list[float]] | None:
        """
        Aggregate a list of FederatedUpdate objects.
        Returns None if fewer than min_participants updates are provided.
        """
        if len(updates) < min_participants:
            logger.warning(
                "gradient_aggregator insufficient_participants n=%d min=%d",
                len(updates), min_participants,
            )
            return None

        valid = [u for u in updates if u.gradient_deltas and u.n_samples > 0]
        if not valid:
            logger.warning("gradient_aggregator no_valid_updates")
            return None

        total_samples = sum(u.n_samples for u in valid)
        if total_samples == 0:
            return None

        if self._method == "fedavg":
            return self._fedavg(valid, total_samples)
        return self._fedprox(valid, total_samples)

    def compute_global_metrics(
        self,
        updates: list[FederatedUpdate],
    ) -> dict[str, float]:
        """Compute weighted loss and accuracy across all participating nodes."""
        valid = [u for u in updates if u.n_samples > 0]
        if not valid:
            return {}
        total = sum(u.n_samples for u in valid)
        weighted_loss = sum(u.local_loss * u.n_samples for u in valid) / total
        weighted_acc = sum(u.local_accuracy * u.n_samples for u in valid) / total
        return {
            "global_loss": round(weighted_loss, 6),
            "global_accuracy": round(weighted_acc, 6),
            "total_samples": total,
            "participant_count": len(valid),
        }

    # ------------------------------------------------------------------
    # Aggregation methods
    # ------------------------------------------------------------------

    def _fedavg(
        self, updates: list[FederatedUpdate], total_samples: int
    ) -> dict[str, list[float]]:
        """Weighted average of gradient deltas."""
        aggregated: dict[str, list[float]] = {}
        for update in updates:
            weight = update.n_samples / total_samples
            for layer, deltas in update.gradient_deltas.items():
                if layer not in aggregated:
                    aggregated[layer] = [0.0] * len(deltas)
                for i, d in enumerate(deltas):
                    if i < len(aggregated[layer]):
                        aggregated[layer][i] += weight * d
                    else:
                        aggregated[layer].append(weight * d)

        logger.debug(
            "gradient_aggregator fedavg layers=%d total_samples=%d",
            len(aggregated), total_samples,
        )
        return aggregated

    def _fedprox(
        self, updates: list[FederatedUpdate], total_samples: int
    ) -> dict[str, list[float]]:
        """
        FedProx: FedAvg + proximal regularization.
        The proximal term shrinks each gradient toward zero by factor mu,
        penalizing updates that deviate far from the global model.
        """
        base = self._fedavg(updates, total_samples)
        mu = self._proximal_mu
        result: dict[str, list[float]] = {}
        for layer, vals in base.items():
            result[layer] = [v * (1.0 - mu) for v in vals]
        logger.debug(
            "gradient_aggregator fedprox mu=%.4f layers=%d", mu, len(result)
        )
        return result

    # ------------------------------------------------------------------
    # Validation helpers
    # ------------------------------------------------------------------

    def compute_gradient_norm(self, gradients: dict[str, list[float]]) -> float:
        total_sq = sum(v * v for vals in gradients.values() for v in vals)
        return math.sqrt(total_sq)

    def detect_poisoning(
        self,
        updates: list[FederatedUpdate],
        *,
        z_score_threshold: float = 3.0,
    ) -> list[str]:
        """
        Basic poisoning detection: flag nodes whose gradient L2 norm is more
        than z_score_threshold standard deviations above the mean.
        Returns list of suspicious node_ids.
        """
        if len(updates) < 3:
            return []
        norms = [(u.node_id, self.compute_gradient_norm(u.gradient_deltas)) for u in updates]
        values = [n for _, n in norms]
        mean = sum(values) / len(values)
        variance = sum((v - mean) ** 2 for v in values) / len(values)
        std = math.sqrt(variance) if variance > 0 else 0.0
        if std == 0:
            return []
        suspicious = [
            node_id for node_id, norm in norms
            if abs(norm - mean) / std > z_score_threshold
        ]
        if suspicious:
            logger.warning(
                "gradient_aggregator poisoning_suspects=%s", suspicious
            )
        return suspicious
