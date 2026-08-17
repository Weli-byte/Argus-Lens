"""
ModelSelector — chooses the optimal model variant (precision, backend, version)
for a given hardware profile and current system load.

Decision factors:
  1. Hardware profile tier
  2. Available VRAM headroom (live reading)
  3. Current inference queue depth
  4. Requested latency budget (optional, from config)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from edge.types import HardwareProfile, ModelPrecision
from model_serving.hardware_profiler import HardwareCapabilities

logger = logging.getLogger(__name__)


@dataclass
class ModelVariant:
    """Describes a specific loadable model configuration."""
    model_name: str
    precision: ModelPrecision
    backend: str            # "pytorch" | "onnx" | "tflite" | "openvino"
    quantized: bool
    estimated_vram_mb: float
    estimated_latency_ms: float
    min_hardware: HardwareProfile
    path_template: str      # e.g. "models/{name}_{precision}.onnx"
    metadata: dict[str, Any] = None

    def __post_init__(self) -> None:
        if self.metadata is None:
            self.metadata = {}

    def resolved_path(self) -> str:
        return self.path_template.format(
            name=self.model_name,
            precision=self.precision.value,
        )


# Ordered registry of available variants per model family.
# Lower index = larger / slower / more accurate; higher = smaller / faster / lighter.
_VARIANT_REGISTRY: dict[str, list[ModelVariant]] = {
    "grounding_dino": [
        ModelVariant(
            model_name="grounding_dino",
            precision=ModelPrecision.FP32,
            backend="pytorch",
            quantized=False,
            estimated_vram_mb=5_200,
            estimated_latency_ms=120,
            min_hardware=HardwareProfile.WORKSTATION,
            path_template="models/{name}_{precision}.pt",
        ),
        ModelVariant(
            model_name="grounding_dino",
            precision=ModelPrecision.FP16,
            backend="pytorch",
            quantized=False,
            estimated_vram_mb=2_800,
            estimated_latency_ms=65,
            min_hardware=HardwareProfile.EDGE_GPU,
            path_template="models/{name}_{precision}.pt",
        ),
        ModelVariant(
            model_name="grounding_dino",
            precision=ModelPrecision.INT8,
            backend="onnx",
            quantized=True,
            estimated_vram_mb=900,
            estimated_latency_ms=40,
            min_hardware=HardwareProfile.EMBEDDED,
            path_template="models/{name}_{precision}.onnx",
        ),
    ],
    "temporal_transformer": [
        ModelVariant(
            model_name="temporal_transformer",
            precision=ModelPrecision.FP32,
            backend="pytorch",
            quantized=False,
            estimated_vram_mb=1_200,
            estimated_latency_ms=30,
            min_hardware=HardwareProfile.WORKSTATION,
            path_template="models/{name}_{precision}.pt",
        ),
        ModelVariant(
            model_name="temporal_transformer",
            precision=ModelPrecision.FP16,
            backend="pytorch",
            quantized=False,
            estimated_vram_mb=650,
            estimated_latency_ms=15,
            min_hardware=HardwareProfile.EDGE_GPU,
            path_template="models/{name}_{precision}.pt",
        ),
        ModelVariant(
            model_name="temporal_transformer",
            precision=ModelPrecision.INT8,
            backend="onnx",
            quantized=True,
            estimated_vram_mb=200,
            estimated_latency_ms=8,
            min_hardware=HardwareProfile.EMBEDDED,
            path_template="models/{name}_{precision}.onnx",
        ),
    ],
    "sentence_transformer": [
        ModelVariant(
            model_name="sentence_transformer",
            precision=ModelPrecision.FP32,
            backend="pytorch",
            quantized=False,
            estimated_vram_mb=500,
            estimated_latency_ms=10,
            min_hardware=HardwareProfile.WORKSTATION,
            path_template="models/{name}_{precision}.pt",
        ),
        ModelVariant(
            model_name="sentence_transformer",
            precision=ModelPrecision.INT8,
            backend="onnx",
            quantized=True,
            estimated_vram_mb=150,
            estimated_latency_ms=4,
            min_hardware=HardwareProfile.EMBEDDED,
            path_template="models/{name}_{precision}.onnx",
        ),
    ],
}

_PROFILE_ORDER = [
    HardwareProfile.SERVER,
    HardwareProfile.WORKSTATION,
    HardwareProfile.EDGE_GPU,
    HardwareProfile.EMBEDDED,
    HardwareProfile.CLOUD,
]


class ModelSelector:
    """
    Selects the best ModelVariant for a given model family given current
    hardware capabilities and headroom constraints.
    """

    def __init__(self, caps: HardwareCapabilities) -> None:
        self._caps = caps

    def select(
        self,
        model_name: str,
        *,
        available_vram_mb: float | None = None,
        max_latency_ms: float | None = None,
        force_precision: ModelPrecision | None = None,
    ) -> ModelVariant | None:
        """
        Returns the best variant for *model_name*, or None if nothing fits.
        Prefers higher accuracy variants and falls back down to lighter ones.
        """
        variants = _VARIANT_REGISTRY.get(model_name, [])
        if not variants:
            logger.warning("model_selector unknown_model=%s", model_name)
            return None

        headroom = available_vram_mb if available_vram_mb is not None else self._caps.total_vram_mb
        profile_rank = _PROFILE_ORDER.index(self._caps.profile) if self._caps.profile in _PROFILE_ORDER else len(_PROFILE_ORDER)

        candidates: list[ModelVariant] = []
        for v in variants:
            if force_precision and v.precision != force_precision:
                continue
            min_rank = _PROFILE_ORDER.index(v.min_hardware) if v.min_hardware in _PROFILE_ORDER else len(_PROFILE_ORDER)
            if profile_rank > min_rank:
                continue
            if v.estimated_vram_mb > headroom * 0.85:
                continue
            if max_latency_ms and v.estimated_latency_ms > max_latency_ms:
                continue
            candidates.append(v)

        if not candidates:
            # Relax VRAM constraint and pick lightest variant that fits hardware
            for v in reversed(variants):
                min_rank = _PROFILE_ORDER.index(v.min_hardware) if v.min_hardware in _PROFILE_ORDER else len(_PROFILE_ORDER)
                if profile_rank <= min_rank:
                    candidates.append(v)
                    break

        if not candidates:
            logger.warning(
                "model_selector no_variant model=%s profile=%s vram_mb=%.0f",
                model_name, self._caps.profile.value, headroom,
            )
            return None

        chosen = candidates[0]
        logger.info(
            "model_selector selected model=%s precision=%s backend=%s latency_ms=%.0f",
            chosen.model_name, chosen.precision.value, chosen.backend, chosen.estimated_latency_ms,
        )
        return chosen

    def select_all(self) -> dict[str, ModelVariant | None]:
        """Returns the best variant for every registered model family."""
        return {name: self.select(name) for name in _VARIANT_REGISTRY}
