"""
RecoveryEngine — executes component recovery procedures.

Supported recovery actions:
  - restart_worker:   signal Celery to restart a worker process
  - reload_model:     call AdaptiveModelLoader to unload + reload a model
  - clear_queue:      drain stale items from inference priority queue
  - flush_cache:      evict stale inference cache entries
  - reduce_load:      lower concurrency limit temporarily

Each action is idempotent — calling it when already in the desired state
produces no side effects.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

import redis.asyncio as aioredis

logger = logging.getLogger(__name__)

_RECOVERY_LOCK_TTL_S = 120      # prevent concurrent recovery for same component
_RECOVERY_LOCK_KEY = "argus:recovery:lock:{component}"


class RecoveryEngine:
    """
    Provides async recovery actions callable by SelfHealingSystem.
    """

    def __init__(self, redis_client: aioredis.Redis) -> None:
        self._redis = redis_client
        self._recovery_log: list[dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Recovery actions
    # ------------------------------------------------------------------

    async def restart_worker(self, worker_name: str) -> bool:
        """
        Sends SIGTERM to the named Celery worker via Redis control channel.
        The worker restarts via supervisor / systemd restart policy.
        """
        if not await self._acquire_lock(f"worker:{worker_name}"):
            logger.info("recovery_engine restart_worker already_in_progress worker=%s", worker_name)
            return False

        try:
            channel = f"argus:worker:control:{worker_name}"
            await self._redis.publish(channel, "restart")
            self._log("restart_worker", worker_name, success=True)
            logger.info("recovery_engine restart_worker sent worker=%s", worker_name)
            return True
        except Exception as exc:
            self._log("restart_worker", worker_name, success=False, error=str(exc))
            logger.error("recovery_engine restart_worker_failed worker=%s: %s", worker_name, exc)
            return False

    async def reload_model(self, model_name: str, loader: Any = None) -> bool:
        """Unload and reload a model variant via AdaptiveModelLoader."""
        if not await self._acquire_lock(f"model:{model_name}"):
            return False

        try:
            if loader and hasattr(loader, "_runtimes"):
                rt = loader._runtimes.get(model_name)
                if rt:
                    await rt.unload()
                    await rt.load()
                    self._log("reload_model", model_name, success=True)
                    logger.info("recovery_engine reload_model complete model=%s", model_name)
                    return True
            logger.warning("recovery_engine reload_model no_loader model=%s", model_name)
            return False
        except Exception as exc:
            self._log("reload_model", model_name, success=False, error=str(exc))
            logger.error("recovery_engine reload_model_failed model=%s: %s", model_name, exc)
            return False

    async def clear_queue(self, queue_key: str = "argus:inference_queue") -> int:
        """Delete the contents of a Redis queue. Returns items cleared."""
        if not await self._acquire_lock(f"queue:{queue_key}"):
            return 0

        try:
            length = await self._redis.llen(queue_key)
            await self._redis.delete(queue_key)
            self._log("clear_queue", queue_key, success=True, items=length)
            logger.info("recovery_engine clear_queue key=%s items=%d", queue_key, length)
            return length
        except Exception as exc:
            self._log("clear_queue", queue_key, success=False, error=str(exc))
            logger.error("recovery_engine clear_queue_failed key=%s: %s", queue_key, exc)
            return 0

    async def flush_cache(self, pattern: str = "argus:inference:*") -> int:
        """Delete matching Redis cache keys. Returns keys flushed."""
        if not await self._acquire_lock(f"cache:{pattern}"):
            return 0

        try:
            keys = await self._redis.keys(pattern)
            if keys:
                await self._redis.delete(*keys)
            self._log("flush_cache", pattern, success=True, keys=len(keys))
            logger.info("recovery_engine flush_cache pattern=%s keys=%d", pattern, len(keys))
            return len(keys)
        except Exception as exc:
            self._log("flush_cache", pattern, success=False, error=str(exc))
            return 0

    async def reduce_load(self, factor: float = 0.5) -> bool:
        """
        Publish a load-reduction directive that workers will honor on next poll.
        Workers read the config key and reduce their local concurrency.
        """
        if not await self._acquire_lock("load_reduction"):
            return False

        try:
            import json
            config_key = "argus:system:load_config"
            await self._redis.setex(
                config_key,
                300,  # expires in 5 minutes — auto-revert
                json.dumps({"concurrency_factor": factor, "issued_at": time.time()}),
            )
            self._log("reduce_load", "global", success=True, factor=factor)
            logger.info("recovery_engine reduce_load factor=%.2f", factor)
            return True
        except Exception as exc:
            self._log("reduce_load", "global", success=False, error=str(exc))
            return False

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _acquire_lock(self, component: str) -> bool:
        key = _RECOVERY_LOCK_KEY.format(component=component)
        acquired = await self._redis.set(key, "1", ex=_RECOVERY_LOCK_TTL_S, nx=True)
        return bool(acquired)

    def _log(self, action: str, target: str, success: bool, **kwargs: Any) -> None:
        self._recovery_log.append({
            "action": action,
            "target": target,
            "success": success,
            "timestamp": time.time(),
            **kwargs,
        })
        if len(self._recovery_log) > 200:
            self._recovery_log = self._recovery_log[-200:]

    def stats(self) -> dict[str, Any]:
        total = len(self._recovery_log)
        successes = sum(1 for r in self._recovery_log if r.get("success"))
        return {
            "total_actions": total,
            "successful_actions": successes,
            "failed_actions": total - successes,
        }

    def recent_log(self, n: int = 20) -> list[dict[str, Any]]:
        return list(self._recovery_log[-n:])
