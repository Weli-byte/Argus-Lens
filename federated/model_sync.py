"""
ModelSyncManager — distributes aggregated model weight updates to edge nodes.

Uses delta sync: only sends layers that changed by more than _DELTA_THRESHOLD,
reducing bandwidth.  Nodes download deltas, apply them locally, and confirm
via a Redis acknowledgement key.
"""

from __future__ import annotations

import asyncio
import json
import logging
import math
import time
import uuid
from typing import Any

import redis.asyncio as aioredis

from edge.types import FederatedRound

logger = logging.getLogger(__name__)

_DELTA_THRESHOLD = 1e-6     # ignore layers with trivial changes
_SYNC_KEY_PREFIX = "argus:fed:sync"
_ACK_KEY_PREFIX = "argus:fed:ack"
_SYNC_TTL_S = 3600          # 1 hour
_ACK_TIMEOUT_S = 120        # wait up to 2 min per node for ack


class ModelSyncManager:
    """
    Publishes aggregated weight deltas and tracks node acknowledgements.

    Args:
        redis_client: shared aioredis instance
        model_name:   model family identifier
    """

    def __init__(self, redis_client: aioredis.Redis, model_name: str) -> None:
        self._redis = redis_client
        self._model_name = model_name
        self._round_number = 0
        self._sync_id = str(uuid.uuid4())

    # ------------------------------------------------------------------
    # Distribution
    # ------------------------------------------------------------------

    async def distribute(
        self,
        aggregated_gradients: dict[str, list[float]],
        target_nodes: list[str],
        round_number: int,
    ) -> str:
        """
        Store aggregated deltas in Redis and notify all target nodes.
        Returns the sync_id for tracking.
        """
        sync_id = str(uuid.uuid4())
        self._round_number = round_number

        # Filter trivial changes
        deltas = self._filter_deltas(aggregated_gradients)
        if not deltas:
            logger.info("model_sync no_significant_deltas round=%d", round_number)
            return sync_id

        payload = {
            "sync_id": sync_id,
            "model_name": self._model_name,
            "round_number": round_number,
            "layer_count": len(deltas),
            "target_nodes": target_nodes,
            "timestamp": time.time(),
        }

        # Store full deltas (potentially large — stored separately)
        delta_key = f"{_SYNC_KEY_PREFIX}:{sync_id}:deltas"
        meta_key = f"{_SYNC_KEY_PREFIX}:{sync_id}:meta"

        await self._redis.setex(delta_key, _SYNC_TTL_S, json.dumps(deltas))
        await self._redis.setex(meta_key, _SYNC_TTL_S, json.dumps(payload))

        # Notify nodes via Redis pub/sub channel
        channel = f"argus:fed:sync_channel:{self._model_name}"
        await self._redis.publish(channel, json.dumps({
            "sync_id": sync_id,
            "round_number": round_number,
            "delta_key": delta_key,
            "meta_key": meta_key,
        }))

        logger.info(
            "model_sync distributed sync_id=%s round=%d layers=%d nodes=%d",
            sync_id, round_number, len(deltas), len(target_nodes),
        )
        return sync_id

    # ------------------------------------------------------------------
    # Acknowledgement tracking
    # ------------------------------------------------------------------

    async def wait_for_acks(
        self,
        sync_id: str,
        target_nodes: list[str],
        timeout_s: float = _ACK_TIMEOUT_S,
    ) -> dict[str, bool]:
        """
        Poll for node acknowledgements.  Returns {node_id: acked} mapping.
        """
        acked: dict[str, bool] = {n: False for n in target_nodes}
        deadline = time.monotonic() + timeout_s
        pending = set(target_nodes)

        while pending and time.monotonic() < deadline:
            for node_id in list(pending):
                ack_key = f"{_ACK_KEY_PREFIX}:{sync_id}:{node_id}"
                val = await self._redis.get(ack_key)
                if val is not None:
                    acked[node_id] = True
                    pending.discard(node_id)
            if pending:
                await asyncio.sleep(2.0)

        ack_rate = sum(acked.values()) / max(len(acked), 1)
        logger.info(
            "model_sync ack_complete sync_id=%s ack_rate=%.1f%%",
            sync_id, ack_rate * 100,
        )
        return acked

    async def acknowledge(self, sync_id: str, node_id: str) -> None:
        """Called by an edge node to confirm it received and applied the update."""
        ack_key = f"{_ACK_KEY_PREFIX}:{sync_id}:{node_id}"
        await self._redis.setex(ack_key, _SYNC_TTL_S, "1")
        logger.debug("model_sync ack node_id=%s sync_id=%s", node_id, sync_id)

    # ------------------------------------------------------------------
    # Delta fetch (called by edge node to download update)
    # ------------------------------------------------------------------

    async def fetch_deltas(self, sync_id: str) -> dict[str, list[float]] | None:
        """Retrieve stored gradient deltas for a sync round."""
        delta_key = f"{_SYNC_KEY_PREFIX}:{sync_id}:deltas"
        raw = await self._redis.get(delta_key)
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _filter_deltas(
        self, gradients: dict[str, list[float]]
    ) -> dict[str, list[float]]:
        """Remove layers whose L2 norm is below the threshold."""
        result: dict[str, list[float]] = {}
        for layer, vals in gradients.items():
            norm = math.sqrt(sum(v * v for v in vals)) if vals else 0.0
            if norm > _DELTA_THRESHOLD:
                result[layer] = vals
        return result

    async def sync_status(self, sync_id: str) -> dict[str, Any]:
        meta_key = f"{_SYNC_KEY_PREFIX}:{sync_id}:meta"
        raw = await self._redis.get(meta_key)
        if raw is None:
            return {"sync_id": sync_id, "found": False}
        data = json.loads(raw)
        data["found"] = True
        return data
