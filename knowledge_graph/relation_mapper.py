"""
RelationMapper — manages directed relations between entities.
Backed by EventGraph (networkx) + Redis edge index.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

import redis.asyncio as aioredis

from correlation.event_graph import EventGraph
from knowledge_graph.entity_manager import EntityManager

logger = logging.getLogger(__name__)

_REL_KEY = "argus:kg:rel"
_REL_TTL = 86400 * 7


class RelationMapper:
    """
    Maps and retrieves directed relations between entities.
    Relations are stored in Redis (for persistence) and EventGraph (for graph traversal).
    """

    def __init__(
        self,
        entity_manager: EntityManager,
        event_graph: EventGraph,
        redis_client: aioredis.Redis,
    ) -> None:
        self._entities = entity_manager
        self._graph = event_graph
        self._redis = redis_client

    async def map_relation(
        self,
        from_entity: str,
        to_entity: str,
        relation_type: str,
        properties: dict[str, Any] | None = None,
        strength: float = 0.5,
    ) -> str:
        import uuid
        rel_id = str(uuid.uuid4())
        record = {
            "relation_id": rel_id,
            "from": from_entity,
            "to": to_entity,
            "relation_type": relation_type,
            "strength": round(strength, 4),
            "properties": properties or {},
            "created_at": time.time(),
        }
        # Persist to Redis
        pipe = self._redis.pipeline()
        pipe.setex(f"{_REL_KEY}:{rel_id}", _REL_TTL, json.dumps(record))
        # Index: entity → outgoing relations
        pipe.lpush(f"{_REL_KEY}:out:{from_entity}", rel_id)
        pipe.expire(f"{_REL_KEY}:out:{from_entity}", _REL_TTL)
        # Index: entity → incoming relations
        pipe.lpush(f"{_REL_KEY}:in:{to_entity}", rel_id)
        pipe.expire(f"{_REL_KEY}:in:{to_entity}", _REL_TTL)
        await pipe.execute()

        # Add to event graph
        self._graph.add_relation(
            from_entity, to_entity,
            relation_type=relation_type,
            strength=strength,
        )
        logger.debug(
            "relation_mapper.map %s→%s type=%s strength=%.3f",
            from_entity,
            to_entity,
            relation_type,
            strength,
        )
        return rel_id

    async def get_related_entities(
        self,
        entity_id: str,
        relation_type: str | None = None,
        direction: str = "out",
    ) -> list[dict[str, Any]]:
        """direction: 'out' | 'in' | 'both'"""
        keys: list[str] = []
        if direction in ("out", "both"):
            keys.append(f"{_REL_KEY}:out:{entity_id}")
        if direction in ("in", "both"):
            keys.append(f"{_REL_KEY}:in:{entity_id}")

        rel_ids: list[str] = []
        for k in keys:
            raw_ids: list[bytes] = await self._redis.lrange(k, 0, -1)
            rel_ids.extend(r.decode() for r in raw_ids)

        relations: list[dict[str, Any]] = []
        for rid in rel_ids:
            raw = await self._redis.get(f"{_REL_KEY}:{rid}")
            if not raw:
                continue
            rel: dict[str, Any] = json.loads(raw)
            if relation_type and rel.get("relation_type") != relation_type:
                continue
            relations.append(rel)

        return relations

    async def find_indirect_relations(
        self,
        entity_a: str,
        entity_b: str,
        max_hops: int = 3,
    ) -> list[list[str]]:
        """Uses EventGraph path-finding (networkx)."""
        return self._graph.find_paths(entity_a, entity_b)
