"""
Model Lifecycle Manager — zero-traffic-drop hot-reload, warm-swap,
checksum verification, and atomic pointer swaps with drain.
"""

from __future__ import annotations

import asyncio
import hashlib
import os
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from loguru import logger
from prometheus_client import Counter, Gauge, Histogram

# ---------------------------------------------------------------------------
# Prometheus
# ---------------------------------------------------------------------------

_LOAD_DURATION = Histogram(
    "arguslens_model_load_duration_seconds",
    "Time taken to load a model into memory",
    ["model_id"],
    buckets=[0.5, 1, 2, 5, 10, 30, 60],
)
_SWAP_TOTAL = Counter(
    "arguslens_model_swap_total",
    "Total number of model hot-swaps",
    ["model_id"],
)
_ACTIVE_MODEL_COUNT = Gauge(
    "arguslens_active_model_count",
    "Number of models currently loaded in memory",
)

# ---------------------------------------------------------------------------
# Domain types
# ---------------------------------------------------------------------------


@dataclass
class ModelVersion:
    version_id: str
    model_id: str
    model_path: str
    loaded_at: float
    inference_count: int = 0
    is_active: bool = False
    checksum: str = ""


# ---------------------------------------------------------------------------
# Manager
# ---------------------------------------------------------------------------


class ModelLifecycleManager:
    """
    Thread-safe (asyncio.Lock) model registry that supports:

    * ``load_model``        — load and register a model version
    * ``hot_reload_model``  — zero-traffic-drop hot-reload via atomic pointer swap
    * ``warm_swap``         — convenience wrapper that resolves a checkpoint path
    * ``get_active_model``  — return the currently active model object
    * ``get_lifecycle_report`` — full status snapshot

    The registry keeps at most *max_loaded_models* in memory; loading a new
    model when at the limit evicts the oldest inactive version.
    """

    # Seconds to wait for in-flight inferences to drain before unloading old model
    _DRAIN_TIMEOUT = 30.0
    # Number of warm-up inferences for the new model before becoming primary
    _WARMUP_INFERENCES = 10

    def __init__(
        self,
        models_dir: str = "models",
        max_loaded_models: int = 3,
    ) -> None:
        self.models_dir = Path(models_dir)
        self.max_loaded_models = max_loaded_models

        # model_id → {"active": ModelVersion, "staging": ModelVersion | None, "obj": Any}
        self._registry: dict[str, dict[str, Any]] = {}
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Load
    # ------------------------------------------------------------------

    async def load_model(
        self,
        model_id: str,
        version_id: str,
        model_path: str,
        loader_fn: Any,  # callable(path) -> model_object
    ) -> ModelVersion:
        """
        Load a model from *model_path* using *loader_fn* and register it.
        Evicts the oldest inactive entry if the registry is at capacity.
        """
        if not self.verify_model_checksum(model_path):
            raise ValueError(f"Checksum verification failed for {model_path}")

        checksum = self._compute_checksum(model_path)
        start = time.monotonic()

        loop = asyncio.get_running_loop()
        model_obj = await loop.run_in_executor(None, loader_fn, model_path)

        duration = time.monotonic() - start
        _LOAD_DURATION.labels(model_id=model_id).observe(duration)

        version = ModelVersion(
            version_id=version_id,
            model_id=model_id,
            model_path=model_path,
            loaded_at=time.time(),
            is_active=True,
            checksum=checksum,
        )

        async with self._lock:
            await self._evict_if_needed()
            self._registry[model_id] = {
                "active": version,
                "staging": None,
                "obj": model_obj,
                "staging_obj": None,
                "in_flight": 0,
            }

        _ACTIVE_MODEL_COUNT.set(len(self._registry))
        logger.info(
            "Model loaded model_id={} version={} path={} duration={:.2f}s",
            model_id,
            version_id,
            model_path,
            duration,
        )
        return version

    # ------------------------------------------------------------------
    # Hot reload (zero-traffic-drop)
    # ------------------------------------------------------------------

    async def hot_reload_model(
        self,
        model_id: str,
        new_path: str,
        loader_fn: Any,
    ) -> ModelVersion:
        """
        Zero-traffic-drop model hot-reload:

        1. Load new model into staging slot
        2. Warm up with _WARMUP_INFERENCES dummy calls (via loader_fn's warmup if available)
        3. Atomic pointer swap (active ← staging)
        4. Drain old model: wait for in-flight inferences (max _DRAIN_TIMEOUT s)
        5. Unload old model object
        """
        if not self.verify_model_checksum(new_path):
            raise ValueError(f"Checksum verification failed for {new_path}")

        checksum = self._compute_checksum(new_path)
        version_id = str(uuid.uuid4())

        # Step 1: Load new model into staging
        logger.info("Hot-reload step 1/5: loading new model for model_id={}", model_id)
        start = time.monotonic()
        loop = asyncio.get_running_loop()
        new_obj = await loop.run_in_executor(None, loader_fn, new_path)
        _LOAD_DURATION.labels(model_id=model_id).observe(time.monotonic() - start)

        new_version = ModelVersion(
            version_id=version_id,
            model_id=model_id,
            model_path=new_path,
            loaded_at=time.time(),
            is_active=False,
            checksum=checksum,
        )

        async with self._lock:
            entry = self._registry.get(model_id)
            if entry is None:
                raise KeyError(f"Model '{model_id}' is not registered")
            entry["staging"] = new_version
            entry["staging_obj"] = new_obj
            old_version: ModelVersion = entry["active"]
            old_obj = entry["obj"]

        # Step 2: Warm up new model
        logger.info("Hot-reload step 2/5: warming up with {} dummy inferences", self._WARMUP_INFERENCES)
        warmup_fn = getattr(new_obj, "warmup", None)
        if warmup_fn:
            for _ in range(self._WARMUP_INFERENCES):
                await loop.run_in_executor(None, warmup_fn)
        else:
            logger.debug("No warmup() method on model — skipping warmup")

        # Step 3: Atomic pointer swap
        logger.info("Hot-reload step 3/5: atomic pointer swap")
        async with self._lock:
            entry = self._registry[model_id]
            entry["active"] = new_version
            entry["obj"] = new_obj
            entry["staging"] = None
            entry["staging_obj"] = None
            new_version.is_active = True
            old_version.is_active = False

        # Step 4: Drain old model in-flight requests
        logger.info("Hot-reload step 4/5: draining old model (max {}s)", self._DRAIN_TIMEOUT)
        drain_deadline = time.monotonic() + self._DRAIN_TIMEOUT
        while time.monotonic() < drain_deadline:
            async with self._lock:
                in_flight = self._registry[model_id].get("in_flight", 0)
            if in_flight <= 0:
                break
            await asyncio.sleep(0.1)

        # Step 5: Unload old model
        logger.info("Hot-reload step 5/5: unloading old model version={}", old_version.version_id)
        del old_obj  # let GC reclaim GPU memory

        _SWAP_TOTAL.labels(model_id=model_id).inc()
        logger.info(
            "Hot-reload complete model_id={} new_version={}",
            model_id,
            version_id,
        )
        return new_version

    # ------------------------------------------------------------------
    # Warm swap (convenience)
    # ------------------------------------------------------------------

    async def warm_swap(
        self,
        model_id: str,
        checkpoint_path: str,
        loader_fn: Any,
    ) -> ModelVersion:
        """Alias for hot_reload_model, resolving paths relative to models_dir."""
        full_path = str(self.models_dir / checkpoint_path)
        return await self.hot_reload_model(model_id, full_path, loader_fn)

    # ------------------------------------------------------------------
    # Checksum
    # ------------------------------------------------------------------

    def verify_model_checksum(self, model_path: str) -> bool:
        """
        Verify the file exists and is readable.  Returns False for missing or
        empty files.  SHA-256 integrity check is performed against stored
        checksums if a .sha256 sidecar file exists.
        """
        path = Path(model_path)
        if not path.exists() or not path.is_file():
            logger.error("Model file not found: {}", model_path)
            return False
        if path.stat().st_size == 0:
            logger.error("Model file is empty: {}", model_path)
            return False

        sidecar = path.with_suffix(path.suffix + ".sha256")
        if sidecar.exists():
            expected = sidecar.read_text().strip().split()[0]
            actual = self._compute_checksum(model_path)
            if actual != expected:
                logger.error(
                    "Checksum mismatch for {}: expected={} got={}",
                    model_path,
                    expected,
                    actual,
                )
                return False

        return True

    @staticmethod
    def _compute_checksum(model_path: str, chunk_size: int = 65536) -> str:
        h = hashlib.sha256()
        with open(model_path, "rb") as f:
            for chunk in iter(lambda: f.read(chunk_size), b""):
                h.update(chunk)
        return h.hexdigest()

    # ------------------------------------------------------------------
    # Model access
    # ------------------------------------------------------------------

    async def get_active_model(self, model_id: str) -> Any:
        """
        Return the active model object, incrementing the in-flight counter.
        Caller must call ``release_model`` when inference is complete.
        """
        async with self._lock:
            entry = self._registry.get(model_id)
            if entry is None:
                raise KeyError(f"Model '{model_id}' not loaded")
            entry["in_flight"] = entry.get("in_flight", 0) + 1
            return entry["obj"]

    async def release_model(self, model_id: str) -> None:
        """Decrement the in-flight counter after inference completes."""
        async with self._lock:
            entry = self._registry.get(model_id)
            if entry:
                entry["in_flight"] = max(0, entry.get("in_flight", 0) - 1)

    # ------------------------------------------------------------------
    # Eviction
    # ------------------------------------------------------------------

    async def _evict_if_needed(self) -> None:
        """Evict the oldest inactive model if at capacity.  Caller holds lock."""
        if len(self._registry) < self.max_loaded_models:
            return
        inactive = [
            (entry["active"].loaded_at, mid)
            for mid, entry in self._registry.items()
            if not entry["active"].is_active
        ]
        if not inactive:
            logger.warning("All models are active; cannot evict — exceeding max_loaded_models")
            return
        inactive.sort()
        _, evict_id = inactive[0]
        del self._registry[evict_id]
        _ACTIVE_MODEL_COUNT.set(len(self._registry))
        logger.info("Evicted inactive model model_id={}", evict_id)

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------

    def get_lifecycle_report(self) -> dict[str, Any]:
        """Return a full snapshot of the model registry."""
        report: dict[str, Any] = {}
        for model_id, entry in self._registry.items():
            version: ModelVersion = entry["active"]
            report[model_id] = {
                "version_id": version.version_id,
                "model_path": version.model_path,
                "loaded_at": version.loaded_at,
                "is_active": version.is_active,
                "checksum": version.checksum[:16] + "…",
                "inference_count": version.inference_count,
                "in_flight": entry.get("in_flight", 0),
                "has_staging": entry["staging"] is not None,
            }
        return report
