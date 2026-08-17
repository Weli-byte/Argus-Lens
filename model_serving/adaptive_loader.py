"""
AdaptiveModelLoader — orchestrates model selection, quantization, and hot-swap.

Responsibilities:
  1. Profile hardware at startup (via HardwareProfiler)
  2. Select best variant per model family (via ModelSelector)
  3. Load all selected variants via QuantizedRuntime
  4. Monitor VRAM headroom and downgrade precision under memory pressure
  5. Expose async `infer(model_name, inputs)` for callers
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from edge.types import HardwareProfile, ModelPrecision
from model_serving.hardware_profiler import HardwareCapabilities, HardwareProfiler
from model_serving.model_selector import ModelSelector, ModelVariant
from model_serving.quantized_runtime import QuantizedRuntime

logger = logging.getLogger(__name__)

_VRAM_PRESSURE_THRESHOLD = 0.90    # 90% used → downgrade precision
_RELOAD_COOLDOWN_S = 30.0          # minimum seconds between hot-swaps


class AdaptiveModelLoader:
    """
    Central model lifecycle manager.  Initialize once at app startup;
    inject into FastAPI app state.
    """

    def __init__(self) -> None:
        self._caps: HardwareCapabilities | None = None
        self._selector: ModelSelector | None = None
        self._runtimes: dict[str, QuantizedRuntime] = {}
        self._variants: dict[str, ModelVariant] = {}
        self._lock = asyncio.Lock()
        self._last_reload: dict[str, float] = {}
        self._ready = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> HardwareCapabilities:
        """Profile hardware, select variants, load all models."""
        profiler = HardwareProfiler()
        self._caps = profiler.profile()
        self._selector = ModelSelector(self._caps)
        selections = self._selector.select_all()

        load_tasks = []
        for name, variant in selections.items():
            if variant is None:
                logger.warning("adaptive_loader no_variant_for model=%s — skipped", name)
                continue
            rt = QuantizedRuntime(variant)
            self._runtimes[name] = rt
            self._variants[name] = variant
            load_tasks.append(rt.load())

        if load_tasks:
            await asyncio.gather(*load_tasks, return_exceptions=True)

        self._ready = True
        logger.info(
            "adaptive_loader initialized profile=%s models_loaded=%d",
            self._caps.profile.value, len(self._runtimes),
        )
        return self._caps

    async def shutdown(self) -> None:
        tasks = [rt.unload() for rt in self._runtimes.values()]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self._runtimes.clear()
        self._variants.clear()
        self._ready = False
        logger.info("adaptive_loader shutdown")

    # ------------------------------------------------------------------
    # Inference
    # ------------------------------------------------------------------

    async def infer(self, model_name: str, inputs: dict[str, Any]) -> dict[str, Any]:
        """
        Run inference on the specified model.  If VRAM pressure is detected,
        triggers an async downgrade before returning.
        """
        if not self._ready:
            raise RuntimeError("AdaptiveModelLoader not initialized")

        rt = self._runtimes.get(model_name)
        if rt is None:
            raise KeyError(f"Unknown model: {model_name}")

        await self._maybe_downgrade(model_name)
        return await rt.run(inputs)

    # ------------------------------------------------------------------
    # Adaptive pressure management
    # ------------------------------------------------------------------

    async def _maybe_downgrade(self, model_name: str) -> None:
        if not self._caps or self._caps.gpu_count == 0:
            return

        vram_used_ratio = self._sample_vram_pressure()
        if vram_used_ratio < _VRAM_PRESSURE_THRESHOLD:
            return

        now = time.monotonic()
        last = self._last_reload.get(model_name, 0.0)
        if now - last < _RELOAD_COOLDOWN_S:
            return

        async with self._lock:
            # Re-check inside lock
            if time.monotonic() - self._last_reload.get(model_name, 0.0) < _RELOAD_COOLDOWN_S:
                return

            current_variant = self._variants.get(model_name)
            if current_variant is None:
                return

            if current_variant.precision == ModelPrecision.INT8:
                return  # already at minimum

            logger.warning(
                "adaptive_loader vram_pressure=%.1f%% — downgrading model=%s",
                vram_used_ratio * 100, model_name,
            )

            next_precision = {
                ModelPrecision.FP32: ModelPrecision.FP16,
                ModelPrecision.FP16: ModelPrecision.INT8,
            }.get(current_variant.precision, ModelPrecision.INT8)

            assert self._selector is not None
            new_variant = self._selector.select(
                model_name,
                available_vram_mb=self._caps.total_vram_mb * (1 - vram_used_ratio),
                force_precision=next_precision,
            )
            if new_variant is None:
                return

            old_rt = self._runtimes[model_name]
            await old_rt.unload()
            new_rt = QuantizedRuntime(new_variant)
            await new_rt.load()
            self._runtimes[model_name] = new_rt
            self._variants[model_name] = new_variant
            self._last_reload[model_name] = time.monotonic()
            logger.info(
                "adaptive_loader downgrade_complete model=%s new_precision=%s",
                model_name, next_precision.value,
            )

    def _sample_vram_pressure(self) -> float:
        """Returns fraction of total VRAM that is currently used (0.0–1.0)."""
        try:
            import torch
            if not torch.cuda.is_available():
                return 0.0
            allocated = torch.cuda.memory_allocated()
            total = torch.cuda.get_device_properties(0).total_memory
            return allocated / total if total > 0 else 0.0
        except Exception:
            return 0.0

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def status(self) -> dict[str, Any]:
        if not self._caps:
            return {"ready": False}
        return {
            "ready": self._ready,
            "hardware_profile": self._caps.profile.value,
            "models": {
                name: rt.stats() for name, rt in self._runtimes.items()
            },
        }

    @property
    def capabilities(self) -> HardwareCapabilities | None:
        return self._caps
