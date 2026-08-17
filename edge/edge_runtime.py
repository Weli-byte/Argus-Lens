"""
EdgeRuntime — the top-level controller for an ArgusLens edge node.

Responsibilities:
  1. Publish node identity and capabilities to Redis (discovery)
  2. Run heartbeat loop (30s) — updates node state in Redis
  3. Detect cloud connectivity loss → enter OfflineMode
  4. Restore connectivity → exit OfflineMode + trigger EdgeSyncManager
  5. Accept inference requests → route to AdaptiveModelLoader or cloud
  6. Coordinate EdgeScheduler for local task prioritization
"""

from __future__ import annotations

import asyncio
import json
import logging
import platform
import time
from typing import Any

import redis.asyncio as aioredis

from edge.edge_scheduler import BackpressureError, EdgeScheduler
from edge.edge_sync import EdgeSyncManager
from edge.local_cache import LocalEdgeCache
from edge.offline_mode import OfflineMode
from edge.types import EdgeNode, EdgeNodeState, InferenceStrategy

logger = logging.getLogger(__name__)

_HEARTBEAT_INTERVAL_S = 30.0
_CONNECTIVITY_CHECK_INTERVAL_S = 15.0
_NODE_KEY_TTL_S = 90                # 3× heartbeat interval
_NODE_REGISTRY_KEY = "argus:edge:nodes"


class EdgeRuntime:
    """
    Initialise once per process.  Manages the full lifecycle of an edge node.

    Args:
        redis_client:   shared aioredis client (may be None for fully offline nodes)
        cloud_url:      base URL of the central ArgusLens cloud API
        node_id:        stable identifier (defaults to hostname)
        strategy:       InferenceStrategy enum value
    """

    def __init__(
        self,
        redis_client: aioredis.Redis | None,
        cloud_url: str = "",
        node_id: str = "",
        strategy: InferenceStrategy = InferenceStrategy.ADAPTIVE,
        auth_token: str = "",
    ) -> None:
        self._redis = redis_client
        self._cloud_url = cloud_url
        self._auth_token = auth_token

        hostname = platform.node()
        self._node = EdgeNode(
            node_id=node_id or hostname,
            hostname=hostname,
            inference_strategy=strategy,
        )

        # Sub-components
        self._local_cache = LocalEdgeCache(maxsize=4096)
        self._offline_mode = OfflineMode(self._local_cache)
        self._scheduler = EdgeScheduler(worker_count=4)
        self._sync_manager: EdgeSyncManager | None = None

        self._tasks: list[asyncio.Task] = []
        self._running = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self, hardware_caps: Any = None) -> EdgeNode:
        """
        Start all background loops.  Call after AdaptiveModelLoader.initialize().
        hardware_caps: HardwareCapabilities from AdaptiveModelLoader (optional).
        """
        if hardware_caps:
            self._node.gpu_count = hardware_caps.gpu_count
            self._node.gpu_vram_mb = hardware_caps.total_vram_mb
            self._node.cpu_cores = hardware_caps.cpu_cores
            self._node.ram_mb = hardware_caps.ram_mb
            self._node.model_precision = hardware_caps.recommended_precision
            from edge.types import HardwareProfile
            self._node.hardware_profile = hardware_caps.profile

        self._node.capabilities = self._detect_capabilities()
        self._node.state = EdgeNodeState.ONLINE

        if self._cloud_url:
            self._sync_manager = EdgeSyncManager(
                cloud_url=self._cloud_url,
                offline_mode=self._offline_mode,
                node_id=self._node.node_id,
                auth_token=self._auth_token,
            )
            await self._sync_manager.start()

        await self._scheduler.start()
        await self._publish_node()

        self._running = True
        self._tasks = [
            asyncio.create_task(self._heartbeat_loop(), name="edge_heartbeat"),
            asyncio.create_task(self._connectivity_loop(), name="edge_connectivity"),
        ]
        logger.info(
            "edge_runtime started node_id=%s strategy=%s",
            self._node.node_id, self._node.inference_strategy.value,
        )
        return self._node

    async def stop(self) -> None:
        self._running = False
        for t in self._tasks:
            t.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()

        await self._scheduler.stop()

        if self._sync_manager:
            await self._sync_manager.stop()

        self._node.state = EdgeNodeState.SHUTDOWN
        await self._publish_node()
        if self._redis:
            await self._redis.srem(_NODE_REGISTRY_KEY, self._node.node_id)

        logger.info("edge_runtime stopped node_id=%s", self._node.node_id)

    # ------------------------------------------------------------------
    # Inference routing
    # ------------------------------------------------------------------

    async def infer(
        self,
        model_name: str,
        inputs: dict[str, Any],
        session_id: str = "",
        *,
        priority: int = 5,
    ) -> dict[str, Any]:
        """
        Route inference based on current strategy and connectivity.
        Returns inference output or buffers to offline queue on failure.
        """
        strategy = self._node.inference_strategy

        if strategy == InferenceStrategy.EDGE_ONLY or self._offline_mode.is_offline:
            return await self._local_infer(model_name, inputs)

        if strategy == InferenceStrategy.CLOUD_FIRST:
            result = await self._cloud_infer(model_name, inputs, session_id)
            if result is not None:
                return result
            return await self._local_infer(model_name, inputs)

        if strategy == InferenceStrategy.EDGE_FIRST:
            result = await self._local_infer(model_name, inputs)
            return result

        if strategy == InferenceStrategy.HYBRID:
            local_task = asyncio.create_task(self._local_infer(model_name, inputs))
            cloud_task = asyncio.create_task(self._cloud_infer(model_name, inputs, session_id))
            done, pending = await asyncio.wait(
                [local_task, cloud_task], return_when=asyncio.FIRST_COMPLETED
            )
            for t in pending:
                t.cancel()
            result = list(done)[0].result()
            return result if result else {}

        # ADAPTIVE — edge first, cloud fallback
        result = await self._local_infer(model_name, inputs)
        return result

    async def _local_infer(self, model_name: str, inputs: dict[str, Any]) -> dict[str, Any]:
        try:
            from model_serving.adaptive_loader import AdaptiveModelLoader
            loader: AdaptiveModelLoader = getattr(self, "_loader", None)  # type: ignore[assignment]
            if loader and loader._ready:
                return await loader.infer(model_name, inputs)
        except Exception as exc:
            logger.warning("edge_runtime local_infer_failed model=%s: %s", model_name, exc)
        return {}

    async def _cloud_infer(
        self, model_name: str, inputs: dict[str, Any], session_id: str
    ) -> dict[str, Any] | None:
        if not self._cloud_url:
            return None
        try:
            import aiohttp
            url = f"{self._cloud_url}/api/v1/infer/{model_name}"
            headers = {}
            if self._auth_token:
                headers["Authorization"] = f"Bearer {self._auth_token}"
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    json={"inputs": inputs, "session_id": session_id},
                    timeout=aiohttp.ClientTimeout(total=5),
                    headers=headers,
                ) as resp:
                    if resp.status == 200:
                        return await resp.json()
        except Exception as exc:
            logger.debug("edge_runtime cloud_infer_failed model=%s: %s", model_name, exc)
            await self._handle_connectivity_loss()
        return None

    # ------------------------------------------------------------------
    # Heartbeat and connectivity
    # ------------------------------------------------------------------

    async def _heartbeat_loop(self) -> None:
        while self._running:
            try:
                await asyncio.sleep(_HEARTBEAT_INTERVAL_S)
                self._node.last_heartbeat = __import__("datetime").datetime.utcnow()
                await self._publish_node()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.debug("edge_runtime heartbeat_error: %s", exc)

    async def _connectivity_loop(self) -> None:
        while self._running:
            try:
                await asyncio.sleep(_CONNECTIVITY_CHECK_INTERVAL_S)
                reachable = await self._check_cloud_reachable()
                if reachable and self._offline_mode.is_offline:
                    await self._offline_mode.exit_offline()
                    self._node.state = EdgeNodeState.SYNCING
                    await self._publish_node()
                    if self._sync_manager:
                        # Trigger immediate sync after reconnect
                        await self._sync_manager._drain_offline_buffer()
                        await self._sync_manager._flush_priority_queue()
                    self._node.state = EdgeNodeState.ONLINE
                    await self._publish_node()
                elif not reachable and not self._offline_mode.is_offline:
                    await self._handle_connectivity_loss()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.debug("edge_runtime connectivity_loop_error: %s", exc)

    async def _check_cloud_reachable(self) -> bool:
        if not self._cloud_url:
            return False
        try:
            import aiohttp
            url = f"{self._cloud_url}/health"
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=3)) as resp:
                    return resp.status == 200
        except Exception:
            return False

    async def _handle_connectivity_loss(self) -> None:
        if self._offline_mode.is_offline:
            return
        await self._offline_mode.enter_offline()
        self._node.state = EdgeNodeState.DEGRADED
        await self._publish_node()
        logger.warning("edge_runtime connectivity_lost — entering offline mode")

    # ------------------------------------------------------------------
    # Node registry
    # ------------------------------------------------------------------

    async def _publish_node(self) -> None:
        if not self._redis:
            return
        try:
            key = f"argus:edge:node:{self._node.node_id}"
            await self._redis.setex(key, _NODE_KEY_TTL_S, json.dumps(self._node.to_dict()))
            await self._redis.sadd(_NODE_REGISTRY_KEY, self._node.node_id)
        except Exception as exc:
            logger.debug("edge_runtime publish_node_error: %s", exc)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _detect_capabilities(self) -> list[str]:
        caps = ["vision", "temporal"]
        try:
            import torch
            if torch.cuda.is_available():
                caps.append("gpu_inference")
        except ImportError:
            pass
        try:
            import onnxruntime  # noqa: F401
            caps.append("onnx_inference")
        except ImportError:
            pass
        return caps

    def attach_loader(self, loader: Any) -> None:
        """Attach AdaptiveModelLoader after initialization."""
        self._loader = loader

    @property
    def node(self) -> EdgeNode:
        return self._node

    def stats(self) -> dict[str, Any]:
        return {
            "node": self._node.to_dict(),
            "scheduler": self._scheduler.stats(),
            "offline": asyncio.get_event_loop().run_until_complete(self._offline_mode.stats())
            if not asyncio.get_event_loop().is_running()
            else {"note": "use async stats()"},
            "sync": self._sync_manager.stats() if self._sync_manager else {},
        }

    async def async_stats(self) -> dict[str, Any]:
        return {
            "node": self._node.to_dict(),
            "scheduler": self._scheduler.stats(),
            "offline": await self._offline_mode.stats(),
            "sync": self._sync_manager.stats() if self._sync_manager else {},
        }
