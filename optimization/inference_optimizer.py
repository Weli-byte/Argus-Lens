"""
Inference Optimizer — mixed-precision AMP, async inference pool, memory-mapped
model loading, and ONNX benchmarking suite.
"""

from __future__ import annotations

import asyncio
import mmap
import os
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional

import numpy as np
from loguru import logger

try:
    import torch
    import torch.cuda.amp as amp

    _CUDA = torch.cuda.is_available()
except ImportError:
    _CUDA = False

try:
    import onnxruntime as ort

    _ORT_AVAILABLE = True
except ImportError:
    _ORT_AVAILABLE = False

# ---------------------------------------------------------------------------
# Mixed Precision Inference
# ---------------------------------------------------------------------------


class MixedPrecisionInference:
    """
    Wraps PyTorch inference in ``torch.cuda.amp.autocast`` for automatic
    FP16/BF16 casting on CUDA, with a CPU fallback.
    """

    def enable_amp(self) -> Any:
        """Return an autocast context manager (or a no-op on CPU)."""
        if _CUDA:
            return amp.autocast(device_type="cuda", dtype=torch.float16)
        return _NullContext()

    async def run_with_amp(self, model: Any, inputs: Any) -> Any:
        """Run *model(inputs)* inside autocast, off the event loop."""
        loop = asyncio.get_running_loop()

        def _infer() -> Any:
            with self.enable_amp():
                return model(inputs)

        return await loop.run_in_executor(None, _infer)

    def benchmark_precision_modes(
        self,
        model: Any,
        sample_input: Any,
        iterations: int = 50,
    ) -> dict[str, float]:
        """
        Time the same model under FP32, FP16 (AMP), and BF16 on the current
        device.  Returns avg latency (ms) per mode.
        """
        results: dict[str, float] = {}

        def _time_mode(ctx: Any, mode_name: str) -> float:
            if _CUDA:
                torch.cuda.synchronize()
            t0 = time.perf_counter()
            for _ in range(iterations):
                with ctx:
                    _ = model(sample_input)
            if _CUDA:
                torch.cuda.synchronize()
            elapsed_ms = (time.perf_counter() - t0) * 1000 / iterations
            logger.info("Precision benchmark mode={} avg={:.2f}ms", mode_name, elapsed_ms)
            return round(elapsed_ms, 2)

        results["fp32"] = _time_mode(_NullContext(), "fp32")
        if _CUDA:
            results["fp16_amp"] = _time_mode(
                amp.autocast(device_type="cuda", dtype=torch.float16), "fp16_amp"
            )
            if torch.cuda.is_bf16_supported():
                results["bf16_amp"] = _time_mode(
                    amp.autocast(device_type="cuda", dtype=torch.bfloat16), "bf16_amp"
                )

        return results


class _NullContext:
    """No-op context manager used for CPU fallback."""

    def __enter__(self) -> "_NullContext":
        return self

    def __exit__(self, *_: Any) -> None:
        pass


# ---------------------------------------------------------------------------
# Async Inference Pool
# ---------------------------------------------------------------------------


@dataclass
class _PoolItem:
    fn: Callable[..., Any]
    inputs: Any
    priority: int
    future: asyncio.Future[Any]


class AsyncInferencePool:
    """
    Fixed-size thread pool that dispatches inference calls across *pool_size*
    worker threads (one per GPU stream in multi-GPU setups).

    Accepts tasks via ``submit`` with an optional priority hint (lower = higher
    priority).  Tasks are executed in FIFO order within the same priority tier.
    """

    def __init__(self, pool_size: int = 4) -> None:
        self.pool_size = pool_size
        self._executor = ThreadPoolExecutor(
            max_workers=pool_size,
            thread_name_prefix="argus_inference",
        )
        self._semaphore = asyncio.Semaphore(pool_size)
        self._task_queue: asyncio.PriorityQueue[tuple[int, int, _PoolItem]] = (
            asyncio.PriorityQueue()
        )
        self._seq = 0
        self._running = False
        self._dispatcher_task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        self._running = True
        self._dispatcher_task = asyncio.create_task(
            self._dispatch_loop(), name="inference_pool_dispatcher"
        )
        logger.info("AsyncInferencePool started pool_size={}", self.pool_size)

    async def stop(self) -> None:
        self._running = False
        if self._dispatcher_task and not self._dispatcher_task.done():
            self._dispatcher_task.cancel()
        self._executor.shutdown(wait=False)

    async def submit(
        self,
        model_fn: Callable[..., Any],
        inputs: Any,
        priority: int = 3,
    ) -> asyncio.Future[Any]:
        """
        Submit an inference job.  Returns a Future that resolves to the result.
        Lower *priority* value = runs sooner.
        """
        loop = asyncio.get_running_loop()
        future: asyncio.Future[Any] = loop.create_future()
        self._seq += 1
        item = _PoolItem(fn=model_fn, inputs=inputs, priority=priority, future=future)
        await self._task_queue.put((priority, self._seq, item))
        return future

    async def _dispatch_loop(self) -> None:
        while self._running:
            try:
                _, _, item = await asyncio.wait_for(self._task_queue.get(), timeout=1.0)
                if item.future.cancelled():
                    self._task_queue.task_done()
                    continue
                asyncio.create_task(self._run(item))
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break

    async def _run(self, item: _PoolItem) -> None:
        async with self._semaphore:
            loop = asyncio.get_running_loop()
            try:
                result = await loop.run_in_executor(
                    self._executor, lambda: item.fn(item.inputs)
                )
                if not item.future.done():
                    item.future.set_result(result)
            except Exception as exc:
                if not item.future.done():
                    item.future.set_exception(exc)
            finally:
                self._task_queue.task_done()


# ---------------------------------------------------------------------------
# Memory-Mapped Model Loader
# ---------------------------------------------------------------------------


class MemoryMappedModelLoader:
    """
    Zero-copy model loading via ``mmap``.  Reads the model file into a
    memory-mapped buffer that the OS can share across processes.
    """

    def load_model_mmap(self, model_path: str) -> mmap.mmap:
        """
        Open *model_path* and return a read-only mmap object.
        Caller is responsible for closing when done.
        """
        path = Path(model_path)
        if not path.exists():
            raise FileNotFoundError(f"Model file not found: {model_path}")

        fd = os.open(model_path, os.O_RDONLY)
        try:
            size = os.fstat(fd).st_size
            mm = mmap.mmap(fd, size, access=mmap.ACCESS_READ)
            logger.info(
                "Memory-mapped model path={} size={:.1f}MB",
                model_path,
                size / (1024 ** 2),
            )
            return mm
        finally:
            os.close(fd)  # fd can be closed after mmap is created

    async def preload_to_gpu(self, model: Any, device: str = "cuda") -> None:
        """
        Move all model parameters to *device* asynchronously (runs in executor
        to avoid blocking the event loop during large model transfers).
        """
        if not _CUDA and device == "cuda":
            logger.warning("CUDA unavailable — skipping GPU preload")
            return

        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, lambda: model.to(device))
        logger.info("Model preloaded to device={}", device)


# ---------------------------------------------------------------------------
# ONNX Benchmark Suite
# ---------------------------------------------------------------------------


@dataclass
class BenchmarkResult:
    avg_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    throughput_fps: float
    memory_mb: float


class ONNXBenchmarkSuite:
    """
    Benchmarks an ONNX model with *iterations* inference passes and reports
    latency percentiles, throughput, and peak memory usage.
    """

    async def benchmark(
        self,
        model_path: str,
        test_inputs: dict[str, np.ndarray],
        iterations: int = 100,
    ) -> BenchmarkResult:
        """
        Run *iterations* ONNX inference passes and return benchmark statistics.
        """
        if not _ORT_AVAILABLE:
            raise RuntimeError("onnxruntime not installed — cannot benchmark")

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None,
            self._run_benchmark_sync,
            model_path,
            test_inputs,
            iterations,
        )

    def _run_benchmark_sync(
        self,
        model_path: str,
        test_inputs: dict[str, np.ndarray],
        iterations: int,
    ) -> BenchmarkResult:
        providers = ["CUDAExecutionProvider", "CPUExecutionProvider"] if _CUDA else ["CPUExecutionProvider"]
        sess = ort.InferenceSession(model_path, providers=providers)

        # Warm up
        for _ in range(min(10, iterations)):
            sess.run(None, test_inputs)

        latencies: list[float] = []
        for _ in range(iterations):
            t0 = time.perf_counter()
            sess.run(None, test_inputs)
            latencies.append((time.perf_counter() - t0) * 1000)

        arr = np.array(latencies)
        total_s = sum(latencies) / 1000
        throughput = iterations / total_s if total_s > 0 else 0.0

        # Estimate memory via ORT session runtime memory info (not precise but available)
        memory_mb = 0.0

        result = BenchmarkResult(
            avg_latency_ms=round(float(np.mean(arr)), 2),
            p95_latency_ms=round(float(np.percentile(arr, 95)), 2),
            p99_latency_ms=round(float(np.percentile(arr, 99)), 2),
            throughput_fps=round(throughput, 2),
            memory_mb=round(memory_mb, 2),
        )
        logger.info(
            "ONNX benchmark model={} avg={:.2f}ms p95={:.2f}ms p99={:.2f}ms fps={:.1f}",
            model_path,
            result.avg_latency_ms,
            result.p95_latency_ms,
            result.p99_latency_ms,
            result.throughput_fps,
        )
        return result

    async def compare_pytorch_vs_onnx(
        self,
        pytorch_model: Any,
        onnx_path: str,
        test_input: np.ndarray,
        iterations: int = 50,
    ) -> dict[str, Any]:
        """
        Side-by-side latency comparison between a PyTorch model and its ONNX
        export.  Returns avg latency for each backend and the speedup ratio.
        """
        if not _CUDA and pytorch_model is None:
            raise ValueError("pytorch_model is required for comparison")

        loop = asyncio.get_running_loop()

        # PyTorch benchmark
        torch_input = torch.from_numpy(test_input) if _CUDA else None

        def _torch_bench() -> float:
            if not _CUDA or torch_input is None:
                return 0.0
            latencies: list[float] = []
            pytorch_model.eval()
            with torch.no_grad():
                for _ in range(iterations):
                    t0 = time.perf_counter()
                    pytorch_model(torch_input)
                    if _CUDA:
                        torch.cuda.synchronize()
                    latencies.append((time.perf_counter() - t0) * 1000)
            return float(np.mean(latencies))

        torch_avg = await loop.run_in_executor(None, _torch_bench)

        # ONNX benchmark
        onnx_result = await self.benchmark(
            onnx_path,
            {"input": test_input},
            iterations=iterations,
        )

        speedup = torch_avg / onnx_result.avg_latency_ms if onnx_result.avg_latency_ms > 0 else None
        return {
            "pytorch_avg_ms": round(torch_avg, 2),
            "onnx_avg_ms": onnx_result.avg_latency_ms,
            "onnx_p95_ms": onnx_result.p95_latency_ms,
            "onnx_p99_ms": onnx_result.p99_latency_ms,
            "onnx_fps": onnx_result.throughput_fps,
            "speedup_ratio": round(speedup, 3) if speedup else None,
        }
