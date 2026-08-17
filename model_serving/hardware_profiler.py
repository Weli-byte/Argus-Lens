"""
HardwareProfiler — detects host hardware capabilities at startup and assigns
a HardwareProfile tier. Used by AdaptiveModelLoader and EdgeRuntime to select
the correct model precision and inference backend.
"""

from __future__ import annotations

import logging
import platform
import sys
from dataclasses import dataclass, field
from typing import Any

from edge.types import HardwareProfile, ModelPrecision

logger = logging.getLogger(__name__)


@dataclass
class HardwareCapabilities:
    profile: HardwareProfile
    gpu_count: int
    gpu_names: list[str]
    gpu_vram_mb: list[float]          # per device
    total_vram_mb: float
    cpu_cores: int
    cpu_model: str
    ram_mb: float
    platform: str                     # linux / windows / darwin
    arch: str                         # x86_64 / aarch64 / armv7l
    cuda_available: bool
    cuda_version: str | None
    recommended_precision: ModelPrecision
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile": self.profile.value,
            "gpu_count": self.gpu_count,
            "gpu_names": self.gpu_names,
            "gpu_vram_mb": self.gpu_vram_mb,
            "total_vram_mb": self.total_vram_mb,
            "cpu_cores": self.cpu_cores,
            "cpu_model": self.cpu_model,
            "ram_mb": self.ram_mb,
            "platform": self.platform,
            "arch": self.arch,
            "cuda_available": self.cuda_available,
            "cuda_version": self.cuda_version,
            "recommended_precision": self.recommended_precision.value,
            "metadata": self.metadata,
        }


class HardwareProfiler:
    """
    Introspects the host machine and returns a HardwareCapabilities snapshot.
    All detection is non-destructive and safe to call repeatedly.
    """

    def profile(self) -> HardwareCapabilities:
        cpu_cores, cpu_model, ram_mb = self._probe_cpu_ram()
        gpu_count, gpu_names, gpu_vram_mb, cuda_available, cuda_version = self._probe_gpu()
        total_vram = sum(gpu_vram_mb)
        hw_profile = self._classify(gpu_count, total_vram, cpu_cores, ram_mb)
        precision = self._recommend_precision(hw_profile, total_vram)

        caps = HardwareCapabilities(
            profile=hw_profile,
            gpu_count=gpu_count,
            gpu_names=gpu_names,
            gpu_vram_mb=gpu_vram_mb,
            total_vram_mb=total_vram,
            cpu_cores=cpu_cores,
            cpu_model=cpu_model,
            ram_mb=ram_mb,
            platform=sys.platform,
            arch=platform.machine().lower(),
            cuda_available=cuda_available,
            cuda_version=cuda_version,
            recommended_precision=precision,
        )
        logger.info(
            "hardware_profiler profile=%s gpu=%d vram_mb=%.0f ram_mb=%.0f precision=%s",
            hw_profile.value, gpu_count, total_vram, ram_mb, precision.value,
        )
        return caps

    # ------------------------------------------------------------------
    # Probe helpers
    # ------------------------------------------------------------------

    def _probe_cpu_ram(self) -> tuple[int, str, float]:
        cores = 1
        model = "unknown"
        ram_mb = 0.0
        try:
            import psutil
            cores = psutil.cpu_count(logical=False) or psutil.cpu_count() or 1
            ram_mb = psutil.virtual_memory().total / (1024 ** 2)
        except ImportError:
            import os
            cores = os.cpu_count() or 1

        try:
            model = platform.processor() or "unknown"
        except Exception:
            pass

        return cores, model, ram_mb

    def _probe_gpu(
        self,
    ) -> tuple[int, list[str], list[float], bool, str | None]:
        gpu_count = 0
        gpu_names: list[str] = []
        gpu_vram_mb: list[float] = []
        cuda_available = False
        cuda_version: str | None = None

        try:
            import torch

            cuda_available = torch.cuda.is_available()
            if cuda_available:
                cuda_version = torch.version.cuda
                gpu_count = torch.cuda.device_count()
                for i in range(gpu_count):
                    props = torch.cuda.get_device_properties(i)
                    gpu_names.append(props.name)
                    gpu_vram_mb.append(props.total_memory / (1024 ** 2))
        except ImportError:
            pass

        if gpu_count == 0:
            # Try pynvml as fallback
            try:
                import pynvml
                pynvml.nvmlInit()
                gpu_count = pynvml.nvmlDeviceGetCount()
                for i in range(gpu_count):
                    handle = pynvml.nvmlDeviceGetHandleByIndex(i)
                    gpu_names.append(pynvml.nvmlDeviceGetName(handle))
                    mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
                    gpu_vram_mb.append(mem.total / (1024 ** 2))
                cuda_available = gpu_count > 0
            except Exception:
                pass

        return gpu_count, gpu_names, gpu_vram_mb, cuda_available, cuda_version

    # ------------------------------------------------------------------
    # Classification logic
    # ------------------------------------------------------------------

    def _classify(
        self, gpu_count: int, total_vram_mb: float, cpu_cores: int, ram_mb: float
    ) -> HardwareProfile:
        arch = platform.machine().lower()
        if arch in ("aarch64", "armv7l", "arm"):
            if gpu_count > 0 and total_vram_mb >= 4000:
                return HardwareProfile.EDGE_GPU   # Jetson-class
            return HardwareProfile.EMBEDDED

        if gpu_count == 0:
            if ram_mb < 4096 or cpu_cores <= 2:
                return HardwareProfile.EMBEDDED
            return HardwareProfile.WORKSTATION

        if total_vram_mb >= 32_000:
            return HardwareProfile.SERVER
        if total_vram_mb >= 8_000:
            return HardwareProfile.WORKSTATION
        if total_vram_mb >= 2_000:
            return HardwareProfile.EDGE_GPU
        return HardwareProfile.EMBEDDED

    def _recommend_precision(
        self, profile: HardwareProfile, total_vram_mb: float
    ) -> ModelPrecision:
        if profile == HardwareProfile.SERVER:
            return ModelPrecision.FP16
        if profile == HardwareProfile.WORKSTATION:
            return ModelPrecision.FP16 if total_vram_mb >= 8_000 else ModelPrecision.INT8
        if profile == HardwareProfile.EDGE_GPU:
            return ModelPrecision.INT8
        # EMBEDDED / CLOUD (CPU fallback)
        return ModelPrecision.INT8
