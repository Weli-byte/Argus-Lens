"""
FederatedCoordinator — orchestrates federated learning rounds.

Round lifecycle:
  1. IDLE          → coordinator receives enough node registrations
  2. COLLECTING    → broadcast start signal; wait for gradient updates from nodes
  3. AGGREGATING   → run GradientAggregator.aggregate()
  4. DISTRIBUTING  → run ModelSyncManager.distribute()
  5. VALIDATING    → wait for ACKs from all nodes
  6. COMPLETE      → log metrics, reset to IDLE for next round
  7. FAILED        → on timeout or poisoning detection

Minimum participants, round timeout, and aggregation method are configurable.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import redis.asyncio as aioredis

from edge.types import FederatedRound, FederatedUpdate
from federated.gradient_aggregator import GradientAggregator
from federated.model_sync import ModelSyncManager
from federated.privacy_layer import PrivacyBudget, PrivacyLayer

logger = logging.getLogger(__name__)

_ROUND_KEY = "argus:fed:round:{model}"
_UPDATE_KEY = "argus:fed:update:{model}:{round}:{node}"
_REGISTRATION_KEY = "argus:fed:nodes:{model}"
_ROUND_TTL_S = 7200
_COLLECTION_TIMEOUT_S = 300     # wait up to 5 min for gradient updates
_MIN_PARTICIPANTS = 2


@dataclass
class RoundResult:
    round_number: int
    model_name: str
    state: FederatedRound
    participants: list[str]
    global_loss: float
    global_accuracy: float
    aggregated_layers: int
    duration_s: float
    sync_id: str | None
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict[str, Any]:
        return {
            "round_number": self.round_number,
            "model_name": self.model_name,
            "state": self.state.value,
            "participants": self.participants,
            "global_loss": self.global_loss,
            "global_accuracy": self.global_accuracy,
            "aggregated_layers": self.aggregated_layers,
            "duration_s": round(self.duration_s, 3),
            "sync_id": self.sync_id,
            "timestamp": self.timestamp.isoformat(),
        }


class FederatedCoordinator:
    """
    Central federated learning coordinator (runs on the cloud/central node).
    Edge nodes submit FederatedUpdate objects; coordinator aggregates and
    redistributes.
    """

    def __init__(
        self,
        redis_client: aioredis.Redis,
        model_name: str,
        *,
        min_participants: int = _MIN_PARTICIPANTS,
        collection_timeout_s: float = _COLLECTION_TIMEOUT_S,
        aggregation_method: str = "fedavg",
        privacy_budget: PrivacyBudget | None = None,
        enable_poisoning_detection: bool = True,
    ) -> None:
        self._redis = redis_client
        self._model_name = model_name
        self._min_participants = min_participants
        self._collection_timeout_s = collection_timeout_s
        self._enable_poisoning_detection = enable_poisoning_detection

        self._aggregator = GradientAggregator(method=aggregation_method)
        self._privacy = PrivacyLayer(privacy_budget)
        self._sync = ModelSyncManager(redis_client, model_name)

        self._current_round = 0
        self._state = FederatedRound.IDLE
        self._round_results: list[RoundResult] = []
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Node registration
    # ------------------------------------------------------------------

    async def register_node(self, node_id: str) -> None:
        """Edge node calls this to participate in federated rounds."""
        key = _REGISTRATION_KEY.format(model=self._model_name)
        await self._redis.sadd(key, node_id)
        logger.debug("federated_coordinator node_registered node_id=%s model=%s", node_id, self._model_name)

    async def unregister_node(self, node_id: str) -> None:
        key = _REGISTRATION_KEY.format(model=self._model_name)
        await self._redis.srem(key, node_id)

    async def registered_nodes(self) -> list[str]:
        key = _REGISTRATION_KEY.format(model=self._model_name)
        members = await self._redis.smembers(key)
        return list(members)

    # ------------------------------------------------------------------
    # Update submission (called by edge nodes)
    # ------------------------------------------------------------------

    async def submit_update(self, update: FederatedUpdate) -> bool:
        """
        An edge node submits its local gradient update.
        Returns False if no active round is accepting updates.
        """
        if self._state != FederatedRound.COLLECTING_GRADIENTS:
            return False
        if update.round_number != self._current_round:
            return False

        key = _UPDATE_KEY.format(
            model=self._model_name,
            round=self._current_round,
            node=update.node_id,
        )
        await self._redis.setex(key, _ROUND_TTL_S, json.dumps(update.to_dict()))
        logger.debug(
            "federated_coordinator update_received node=%s round=%d",
            update.node_id, update.round_number,
        )
        return True

    # ------------------------------------------------------------------
    # Round execution
    # ------------------------------------------------------------------

    async def run_round(self) -> RoundResult | None:
        """
        Execute one complete federated learning round.
        Call this from a background task or scheduled trigger.
        """
        async with self._lock:
            if self._state != FederatedRound.IDLE:
                logger.warning("federated_coordinator round_already_running state=%s", self._state.value)
                return None

            self._current_round += 1
            round_num = self._current_round
            t_start = time.monotonic()
            self._state = FederatedRound.COLLECTING_GRADIENTS
            await self._publish_round_state()

        try:
            # Phase 1: collect updates
            updates = await self._collect_updates(round_num)
            if len(updates) < self._min_participants:
                return await self._fail_round(round_num, "insufficient_participants", t_start)

            # Phase 2: poisoning check
            if self._enable_poisoning_detection:
                suspects = self._aggregator.detect_poisoning(updates)
                if suspects:
                    updates = [u for u in updates if u.node_id not in suspects]
                    if len(updates) < self._min_participants:
                        return await self._fail_round(round_num, "all_poisoned", t_start)

            # Phase 3: aggregate
            async with self._lock:
                self._state = FederatedRound.AGGREGATING
                await self._publish_round_state()

            metrics = self._aggregator.compute_global_metrics(updates)
            aggregated = self._aggregator.aggregate(updates, min_participants=self._min_participants)
            if aggregated is None:
                return await self._fail_round(round_num, "aggregation_failed", t_start)

            # Phase 4: apply differential privacy
            noised, epsilon = self._privacy.apply_gaussian(aggregated)
            logger.info(
                "federated_coordinator privacy_applied round=%d epsilon=%.4f",
                round_num, epsilon,
            )

            # Phase 5: distribute
            async with self._lock:
                self._state = FederatedRound.DISTRIBUTING
                await self._publish_round_state()

            nodes = [u.node_id for u in updates]
            sync_id = await self._sync.distribute(noised, nodes, round_num)

            # Phase 6: validate (wait for acks)
            async with self._lock:
                self._state = FederatedRound.VALIDATING
                await self._publish_round_state()

            await self._sync.wait_for_acks(sync_id, nodes, timeout_s=60.0)

            # Complete
            duration = time.monotonic() - t_start
            result = RoundResult(
                round_number=round_num,
                model_name=self._model_name,
                state=FederatedRound.COMPLETE,
                participants=nodes,
                global_loss=metrics.get("global_loss", 0.0),
                global_accuracy=metrics.get("global_accuracy", 0.0),
                aggregated_layers=len(aggregated),
                duration_s=duration,
                sync_id=sync_id,
            )

            async with self._lock:
                self._state = FederatedRound.IDLE
                self._round_results.append(result)
                await self._publish_round_state()

            logger.info(
                "federated_coordinator round_complete round=%d participants=%d "
                "loss=%.4f acc=%.4f duration_s=%.2f",
                round_num, len(nodes), result.global_loss, result.global_accuracy, duration,
            )
            return result

        except Exception as exc:
            logger.error("federated_coordinator round_error round=%d: %s", round_num, exc)
            return await self._fail_round(round_num, str(exc), t_start)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _collect_updates(self, round_num: int) -> list[FederatedUpdate]:
        """Wait for gradient updates from registered nodes."""
        registered = await self.registered_nodes()
        deadline = time.monotonic() + self._collection_timeout_s
        updates: list[FederatedUpdate] = []

        while time.monotonic() < deadline:
            updates = await self._fetch_updates(round_num, registered)
            if len(updates) >= self._min_participants:
                break
            await asyncio.sleep(5.0)

        logger.info(
            "federated_coordinator updates_collected round=%d count=%d",
            round_num, len(updates),
        )
        return updates

    async def _fetch_updates(
        self, round_num: int, node_ids: list[str]
    ) -> list[FederatedUpdate]:
        updates = []
        for node_id in node_ids:
            key = _UPDATE_KEY.format(model=self._model_name, round=round_num, node=node_id)
            raw = await self._redis.get(key)
            if raw:
                try:
                    updates.append(FederatedUpdate.from_dict(json.loads(raw)))
                except Exception as exc:
                    logger.debug("federated_coordinator parse_error node=%s: %s", node_id, exc)
        return updates

    async def _fail_round(
        self, round_num: int, reason: str, t_start: float
    ) -> RoundResult:
        duration = time.monotonic() - t_start
        result = RoundResult(
            round_number=round_num,
            model_name=self._model_name,
            state=FederatedRound.FAILED,
            participants=[],
            global_loss=0.0,
            global_accuracy=0.0,
            aggregated_layers=0,
            duration_s=duration,
            sync_id=None,
        )
        async with self._lock:
            self._state = FederatedRound.IDLE
            self._round_results.append(result)
            await self._publish_round_state()
        logger.warning("federated_coordinator round_failed round=%d reason=%s", round_num, reason)
        return result

    async def _publish_round_state(self) -> None:
        key = _ROUND_KEY.format(model=self._model_name)
        await self._redis.setex(key, _ROUND_TTL_S, json.dumps({
            "model_name": self._model_name,
            "current_round": self._current_round,
            "state": self._state.value,
        }))

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def stats(self) -> dict[str, Any]:
        return {
            "model_name": self._model_name,
            "current_round": self._current_round,
            "state": self._state.value,
            "total_rounds": len(self._round_results),
            "successful_rounds": sum(1 for r in self._round_results if r.state == FederatedRound.COMPLETE),
            "privacy": self._privacy.stats(),
        }

    @property
    def round_results(self) -> list[RoundResult]:
        return list(self._round_results)
