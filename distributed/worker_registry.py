import redis.asyncio as redis
import json
import time
from typing import List, Dict, Optional
from core.config import settings
from monitoring.log_pipeline import logger

class WorkerRegistry:
    """
    Distributed Node Discovery and Health Tracking via Redis.
    Allows multiple ArgusLens nodes (GPUs) to form a cluster.
    """
    def __init__(self):
        self.redis = redis.from_url(settings.REDIS_URL, decode_responses=True, protocol=2)
        self.worker_prefix = "arguslens:worker:"
        self.ttl = 15 # Seconds before worker is considered dead

    async def register_heartbeat(self, worker_id: str, capacity: dict):
        """Called by a worker every 5 seconds to say 'I am alive'."""
        key = f"{self.worker_prefix}{worker_id}"
        payload = {
            "timestamp": time.time(),
            "capacity": capacity # e.g., {"gpu_mem_free": 8, "active_tasks": 2}
        }
        await self.redis.setex(key, self.ttl, json.dumps(payload))
        
    async def get_active_workers(self) -> Dict[str, dict]:
        """Returns all workers that have pinged within the TTL."""
        workers = {}
        # Fetch all keys matching prefix
        keys = await self.redis.keys(f"{self.worker_prefix}*")
        for key in keys:
            data_str = await self.redis.get(key)
            if data_str:
                worker_id = key.replace(self.worker_prefix, "")
                workers[worker_id] = json.loads(data_str)
        return workers

    async def get_least_loaded_worker(self) -> Optional[str]:
        """Simple Load Balancing Strategy: Least Active Tasks."""
        workers = await self.get_active_workers()
        if not workers:
            return None
            
        # Sort by active_tasks ascending
        sorted_workers = sorted(
            workers.items(), 
            key=lambda item: item[1].get("capacity", {}).get("active_tasks", 0)
        )
        return sorted_workers[0][0] # Returns the worker_id
