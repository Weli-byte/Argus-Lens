"""
EntityManager — manages system entities (persons, objects, events, metrics).
Redis-backed; Neo4j-ready interface.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from typing import Any

import redis.asyncio as aioredis

logger = logging.getLogger(__name__)

_ENTITY_KEY = "argus:kg:entity"
_TYPE_INDEX_KEY = "argus:kg:type"
_ENTITY_TTL = 86400 * 7  # 7 days


class EntityManager:
    """
    CRUD for knowledge graph entities.
    Each entity: {entity_id, entity_type, properties, created_at, updated_at}
    """

    def __init__(self, redis_client: aioredis.Redis) -> None:
        self._redis = redis_client

    async def register_entity(
        self,
        entity_type: str,
        entity_id: str | None = None,
        properties: dict[str, Any] | None = None,
    ) -> str:
        eid = entity_id or str(uuid.uuid4())
        now = time.time()
        record = {
            "entity_id": eid,
            "entity_type": entity_type,
            "properties": properties or {},
            "created_at": now,
            "updated_at": now,
        }
        pipe = self._redis.pipeline()
        pipe.setex(f"{_ENTITY_KEY}:{eid}", _ENTITY_TTL, json.dumps(record))
        pipe.sadd(f"{_TYPE_INDEX_KEY}:{entity_type}", eid)
        pipe.expire(f"{_TYPE_INDEX_KEY}:{entity_type}", _ENTITY_TTL)
        await pipe.execute()
        logger.debug(
            "entity_manager.register id=%s type=%s", eid, entity_type
        )
        return eid

    async def update_entity(
        self, entity_id: str, properties: dict[str, Any]
    ) -> bool:
        key = f"{_ENTITY_KEY}:{entity_id}"
        raw = await self._redis.get(key)
        if not raw:
            return False
        record: dict[str, Any] = json.loads(raw)
        record["properties"].update(properties)
        record["updated_at"] = time.time()
        await self._redis.setex(key, _ENTITY_TTL, json.dumps(record))
        logger.debug("entity_manager.update id=%s", entity_id)
        return True

    async def get_entity(self, entity_id: str) -> dict[str, Any] | None:
        raw = await self._redis.get(f"{_ENTITY_KEY}:{entity_id}")
        return json.loads(raw) if raw else None

    async def find_entities_by_type(
        self, entity_type: str
    ) -> list[dict[str, Any]]:
        raw_ids: set[bytes] = await self._redis.smembers(
            f"{_TYPE_INDEX_KEY}:{entity_type}"
        )
        entities: list[dict[str, Any]] = []
        for eid_bytes in raw_ids:
            entity = await self.get_entity(eid_bytes.decode())
            if entity:
                entities.append(entity)
        return entities

    async def delete_entity(self, entity_id: str) -> bool:
        raw = await self._redis.get(f"{_ENTITY_KEY}:{entity_id}")
        if not raw:
            return False
        record: dict[str, Any] = json.loads(raw)
        pipe = self._redis.pipeline()
        pipe.delete(f"{_ENTITY_KEY}:{entity_id}")
        pipe.srem(f"{_TYPE_INDEX_KEY}:{record['entity_type']}", entity_id)
        await pipe.execute()
        return True

    async def count_entities(self) -> dict[str, int]:
        """Count entities by type."""
        pattern = f"{_TYPE_INDEX_KEY}:*"
        keys: list[bytes] = await self._redis.keys(pattern)
        counts: dict[str, int] = {}
        for k in keys:
            key_str = k.decode()
            etype = key_str.removeprefix(f"{_TYPE_INDEX_KEY}:")
            counts[etype] = await self._redis.scard(k)
        return counts
