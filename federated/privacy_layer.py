"""
PrivacyLayer — differential privacy mechanisms for federated gradient updates.

Implements:
  - Gaussian mechanism: add N(0, sigma^2) noise to gradient vectors
  - Laplace mechanism: add Laplace(0, b) noise (stronger privacy, weaker utility)
  - Gradient clipping: bound L2 norm before noise injection

Privacy accounting uses the basic (epsilon, delta)-DP composition.
"""

from __future__ import annotations

import logging
import math
import random
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class PrivacyBudget:
    epsilon: float = 1.0        # privacy loss bound
    delta: float = 1e-5         # failure probability
    sensitivity: float = 1.0   # L2 sensitivity of function
    noise_multiplier: float = 1.1  # sigma = noise_multiplier * sensitivity


class PrivacyLayer:
    """
    Applies differential privacy to gradient delta dictionaries.

    All noise is added in Python (no torch dependency); if torch is available
    the same operations can be performed on GPU by converting lists first.
    """

    def __init__(self, budget: PrivacyBudget | None = None) -> None:
        self._budget = budget or PrivacyBudget()
        self._total_epsilon_spent = 0.0
        self._rounds_applied = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def apply_gaussian(
        self,
        gradients: dict[str, list[float]],
        clip_norm: float = 1.0,
    ) -> tuple[dict[str, list[float]], float]:
        """
        1. Clip gradient vectors to clip_norm (L2).
        2. Add Gaussian noise calibrated to (epsilon, delta)-DP.
        Returns (noised_gradients, epsilon_spent).
        """
        clipped = self._clip_gradients(gradients, clip_norm)
        sigma = self._budget.noise_multiplier * self._budget.sensitivity
        noised = self._add_gaussian_noise(clipped, sigma)
        epsilon = self._compute_gaussian_epsilon(sigma, self._budget.delta)
        self._total_epsilon_spent += epsilon
        self._rounds_applied += 1
        logger.debug(
            "privacy_layer gaussian_applied sigma=%.4f epsilon_spent=%.4f",
            sigma, epsilon,
        )
        return noised, epsilon

    def apply_laplace(
        self,
        gradients: dict[str, list[float]],
        clip_norm: float = 1.0,
    ) -> tuple[dict[str, list[float]], float]:
        """
        1. Clip gradient vectors.
        2. Add Laplace noise.
        Returns (noised_gradients, epsilon_spent).
        """
        clipped = self._clip_gradients(gradients, clip_norm)
        b = self._budget.sensitivity / self._budget.epsilon
        noised = self._add_laplace_noise(clipped, b)
        self._total_epsilon_spent += self._budget.epsilon
        self._rounds_applied += 1
        logger.debug(
            "privacy_layer laplace_applied b=%.4f epsilon=%.4f",
            b, self._budget.epsilon,
        )
        return noised, self._budget.epsilon

    # ------------------------------------------------------------------
    # Clipping
    # ------------------------------------------------------------------

    def _clip_gradients(
        self,
        gradients: dict[str, list[float]],
        clip_norm: float,
    ) -> dict[str, list[float]]:
        result: dict[str, list[float]] = {}
        for layer, vals in gradients.items():
            l2 = math.sqrt(sum(v * v for v in vals)) if vals else 0.0
            if l2 > clip_norm and l2 > 0:
                scale = clip_norm / l2
                result[layer] = [v * scale for v in vals]
            else:
                result[layer] = list(vals)
        return result

    # ------------------------------------------------------------------
    # Noise mechanisms
    # ------------------------------------------------------------------

    def _add_gaussian_noise(
        self,
        gradients: dict[str, list[float]],
        sigma: float,
    ) -> dict[str, list[float]]:
        result: dict[str, list[float]] = {}
        for layer, vals in gradients.items():
            result[layer] = [v + random.gauss(0.0, sigma) for v in vals]
        return result

    def _add_laplace_noise(
        self,
        gradients: dict[str, list[float]],
        b: float,
    ) -> dict[str, list[float]]:
        # Laplace via inverse CDF: sign * b * ln(1 - 2|U - 0.5|)
        def _sample() -> float:
            u = random.random() - 0.5
            return -b * math.copysign(1, u) * math.log(1 - 2 * abs(u) + 1e-12)

        result: dict[str, list[float]] = {}
        for layer, vals in gradients.items():
            result[layer] = [v + _sample() for v in vals]
        return result

    # ------------------------------------------------------------------
    # Epsilon accounting
    # ------------------------------------------------------------------

    def _compute_gaussian_epsilon(self, sigma: float, delta: float) -> float:
        if sigma <= 0 or delta <= 0:
            return float("inf")
        sensitivity = self._budget.sensitivity
        return (sensitivity / sigma) * math.sqrt(2 * math.log(1.25 / delta))

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def budget_remaining(self) -> float:
        return max(0.0, self._budget.epsilon - self._total_epsilon_spent)

    def stats(self) -> dict[str, Any]:
        return {
            "epsilon_total": self._budget.epsilon,
            "epsilon_spent": round(self._total_epsilon_spent, 6),
            "epsilon_remaining": round(self.budget_remaining(), 6),
            "delta": self._budget.delta,
            "rounds_applied": self._rounds_applied,
        }
