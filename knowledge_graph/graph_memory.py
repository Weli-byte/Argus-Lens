"""
GraphMemory — combines EntityManager + RelationMapper + LTM
to build a persistent knowledge graph from observed events.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from knowledge_graph.entity_manager import EntityManager
from knowledge_graph.relation_mapper import RelationMapper
from memory.long_term_memory import LongTermMemory

logger = logging.getLogger(__name__)


class GraphMemory:
    """
    Learns entity relationships from events and makes them queryable.
    """

    def __init__(
        self,
        entity_manager: EntityManager,
        relation_mapper: RelationMapper,
        long_term_memory: LongTermMemory,
    ) -> None:
        self._entities = entity_manager
        self._relations = relation_mapper
        self._ltm = long_term_memory

    async def memorize_event_relations(
        self,
        event: dict[str, Any],
        related_events: list[dict[str, Any]],
    ) -> None:
        """
        Register the event as an entity and create relations to related events.
        """
        event_id = event.get("event_id") or event.get("id") or str(id(event))
        event_type = event.get("type", "unknown_event")

        # Ensure event entity exists
        existing = await self._entities.get_entity(event_id)
        if not existing:
            await self._entities.register_entity(
                entity_type=event_type,
                entity_id=event_id,
                properties={
                    "timestamp": event.get("timestamp", time.time()),
                    "severity": event.get("severity", "unknown"),
                },
            )

        for related in related_events:
            related_id = related.get("event_id") or related.get("id") or str(id(related))
            related_type = related.get("type", "unknown_event")

            if not await self._entities.get_entity(related_id):
                await self._entities.register_entity(
                    entity_type=related_type,
                    entity_id=related_id,
                    properties={
                        "timestamp": related.get("timestamp", time.time()),
                        "severity": related.get("severity", "unknown"),
                    },
                )

            lag = abs(
                related.get("timestamp", 0) - event.get("timestamp", 0)
            )
            strength = max(0.0, 1.0 - lag / 300)  # decays over 5 min

            await self._relations.map_relation(
                from_entity=event_id,
                to_entity=related_id,
                relation_type="temporally_related",
                strength=strength,
                properties={"lag_seconds": round(lag, 2)},
            )

        logger.debug(
            "graph_memory.memorize event_id=%s related=%d",
            event_id,
            len(related_events),
        )

    async def recall_entity_history(
        self, entity_id: str, days: int = 7
    ) -> list[dict[str, Any]]:
        """Get all relations involving this entity (outgoing + incoming)."""
        relations = await self._relations.get_related_entities(
            entity_id, direction="both"
        )
        cutoff = time.time() - days * 86400
        filtered = [
            r for r in relations
            if r.get("created_at", 0) >= cutoff
        ]
        return sorted(filtered, key=lambda r: r.get("created_at", 0), reverse=True)

    async def get_graph_summary(self) -> dict[str, Any]:
        entity_counts = await self._entities.count_entities()
        from correlation.event_graph import EventGraph
        # Access the underlying graph stats via relation_mapper
        graph_stats = {}
        try:
            graph_stats = self._relations._graph.stats()
        except AttributeError:
            pass

        ltm_stats = await self._ltm.get_statistics()

        return {
            "entity_counts": entity_counts,
            "total_entities": sum(entity_counts.values()),
            "graph_edges": graph_stats.get("edges", 0),
            "ltm_total_memories": ltm_stats.get("total_entries", 0),
        }
