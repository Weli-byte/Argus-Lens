"""
QuantizedRuntime — wraps a PyTorch or ONNX model behind a unified async interface.

Supported backends:
  - pytorch:  uses torch.quantization.quantize_dynamic() for INT8 on CPU
  - onnx:     uses onnxruntime InferenceSession with optimization level 3
  - passthrough: returns raw model without quantization (FP32 / FP16)
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

import numpy as np

from edge.types import ModelPrecision
from model_serving.model_selector import ModelVariant

logger = logging.getLogger(__name__)

_TORCH_AVAILABLE = False
_ONNX_AVAILABLE = False

try:
    import torch
    _TORCH_AVAILABLE = True
except ImportError:
    pass

try:
    import onnxruntime as ort
    _ONNX_AVAILABLE = True
except ImportError:
    pass


class QuantizedRuntime:
    """
    Loads a model variant and provides an async `run()` method for inference.

    Usage:
        qr = QuantizedRuntime(variant)
        await qr.load()
        output = await qr.run(inputs)
        await qr.unload()
    """

    def __init__(self, variant: ModelVariant) -> None:
        self._variant = variant
        self._model: Any = None
        self._session: Any = None   # ONNX InferenceSession
        self._loaded = False
        self._lock = asyncio.Lock()
        self._inference_count = 0
        self._total_latency_ms = 0.0

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def load(self) -> None:
        async with self._lock:
            if self._loaded:
                return
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._load_sync)
            self._loaded = True
            logger.info(
                "quantized_runtime loaded model=%s precision=%s backend=%s",
                self._variant.model_name, self._variant.precision.value, self._variant.backend,
            )

    async def unload(self) -> None:
        async with self._lock:
            if not self._loaded:
                return
            self._model = None
            self._session = None
            self._loaded = False
            if _TORCH_AVAILABLE:
                try:
                    import torch
                    torch.cuda.empty_cache()
                except Exception:
                    pass
            logger.info("quantized_runtime unloaded model=%s", self._variant.model_name)

    def _load_sync(self) -> None:
        backend = self._variant.backend
        if backend == "onnx":
            self._load_onnx()
        elif backend in ("pytorch", "passthrough"):
            self._load_pytorch()
        else:
            raise ValueError(f"Unsupported backend: {backend}")

    def _load_pytorch(self) -> None:
        if not _TORCH_AVAILABLE:
            raise RuntimeError("torch is not installed")
        path = self._variant.resolved_path()
        try:
            import torch
            self._model = torch.load(path, map_location="cpu")
            self._model.eval()
        except FileNotFoundError:
            logger.warning("quantized_runtime model_file_missing path=%s — using stub", path)
            self._model = _StubModel()
            return

        if self._variant.precision == ModelPrecision.INT8:
            import torch.quantization
            self._model = torch.quantization.quantize_dynamic(
                self._model, {torch.nn.Linear, torch.nn.LSTM}, dtype=torch.qint8
            )
            logger.debug("quantized_runtime int8_quantization applied model=%s", self._variant.model_name)
        elif self._variant.precision == ModelPrecision.FP16:
            try:
                import torch
                if torch.cuda.is_available():
                    self._model = self._model.half().cuda()
                else:
                    logger.warning("quantized_runtime fp16_requested but no CUDA — using FP32")
            except Exception as exc:
                logger.warning("quantized_runtime fp16_failed: %s", exc)

    def _load_onnx(self) -> None:
        if not _ONNX_AVAILABLE:
            raise RuntimeError("onnxruntime is not installed")
        path = self._variant.resolved_path()
        try:
            import onnxruntime as ort
            opts = ort.SessionOptions()
            opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
            providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
            self._session = ort.InferenceSession(path, sess_options=opts, providers=providers)
        except Exception as exc:
            logger.warning("quantized_runtime onnx_load_failed path=%s err=%s — using stub", path, exc)
            self._session = _StubSession()

    # ------------------------------------------------------------------
    # Inference
    # ------------------------------------------------------------------

    async def run(self, inputs: dict[str, Any]) -> dict[str, Any]:
        if not self._loaded:
            raise RuntimeError("QuantizedRuntime.run() called before load()")
        loop = asyncio.get_event_loop()
        t0 = time.monotonic()
        result = await loop.run_in_executor(None, self._run_sync, inputs)
        elapsed_ms = (time.monotonic() - t0) * 1000
        self._inference_count += 1
        self._total_latency_ms += elapsed_ms
        return result

    def _run_sync(self, inputs: dict[str, Any]) -> dict[str, Any]:
        if self._session is not None:
            return self._run_onnx(inputs)
        return self._run_pytorch(inputs)

    def _run_pytorch(self, inputs: dict[str, Any]) -> dict[str, Any]:
        if isinstance(self._model, _StubModel):
            return self._model(inputs)
        try:
            import torch
            with torch.no_grad():
                result = self._model(**inputs)
            if isinstance(result, dict):
                return result
            return {"output": result}
        except Exception as exc:
            logger.error("quantized_runtime pytorch_inference_error: %s", exc)
            return {"error": str(exc)}

    def _run_onnx(self, inputs: dict[str, Any]) -> dict[str, Any]:
        if isinstance(self._session, _StubSession):
            return self._session.run(None, inputs)
        try:
            # Convert tensors to numpy if needed
            np_inputs: dict[str, np.ndarray] = {}
            for k, v in inputs.items():
                if hasattr(v, "numpy"):
                    np_inputs[k] = v.numpy()
                elif isinstance(v, np.ndarray):
                    np_inputs[k] = v
                else:
                    np_inputs[k] = np.array(v)
            outputs = self._session.run(None, np_inputs)
            names = [o.name for o in self._session.get_outputs()]
            return dict(zip(names, outputs))
        except Exception as exc:
            logger.error("quantized_runtime onnx_inference_error: %s", exc)
            return {"error": str(exc)}

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    def avg_latency_ms(self) -> float:
        if self._inference_count == 0:
            return 0.0
        return self._total_latency_ms / self._inference_count

    def stats(self) -> dict[str, Any]:
        return {
            "model_name": self._variant.model_name,
            "precision": self._variant.precision.value,
            "backend": self._variant.backend,
            "loaded": self._loaded,
            "inference_count": self._inference_count,
            "avg_latency_ms": round(self.avg_latency_ms(), 2),
        }


# ---------------------------------------------------------------------------
# Stub implementations for missing model files (dev / test environments)
# ---------------------------------------------------------------------------


class _StubModel:
    """Returns empty outputs when no model file is present."""
    def __call__(self, **kwargs: Any) -> dict[str, Any]:
        return {"stub": True, "output": []}


class _StubSession:
    """Returns empty outputs when no ONNX file is present."""
    def run(self, output_names: list | None, inputs: dict) -> list:
        return [[]]
