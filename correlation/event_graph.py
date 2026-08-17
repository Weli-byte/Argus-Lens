"""
EventGraph — in-memory directed graph of events and their relations.
networkx DiGraph backend; Neo4j-ready interface.
"""

from __future__ import annotations

import logging
import time
from typing import Any

try:
    import networkx as nx  # type: ignore[import]
    _NX_AVAILABLE = True
except ImportError:
    nx = None  # type: ignore[assignment]
    _NX_AVAILABLE = False

logger = logging.getLogger(__name__)


class EventGraph:
    """
    DAG of system events with weighted, typed edges.
    Falls back to dict-based adjacency if networkx is unavailable.
    """

    def __init__(self) -> None:
        if _NX_AVAILABLE:
            self._graph: Any = nx.DiGraph()
        else:
            self._graph = None
        # Always maintain adjacency dict for fallback + fast lookup
        self._nodes: dict[str, dict[str, Any]] = {}
        self._edges: list[dict[str, Any]] = []

    def add_event(self, event_id: str, event_data: dict[str, Any]) -> None:
        data = {**event_data, "_added_at": time.time()}
        self._nodes[event_id] = data
        if _NX_AVAILABLE and self._graph is not None:
            self._graph.add_node(event_id, **data)
        logger.debug("event_graph.add_event id=%s", event_id)

    def add_relation(
        self,
        event_id_a: str,
        event_id_b: str,
        relation_type: str,
        strength: float,
        lag_seconds: float = 0.0,
    ) -> None:
        edge = {
            "from": event_id_a,
            "to": event_id_b,
            "relation_type": relation_type,
            "strength": round(strength, 4),
            "lag_seconds": round(lag_seconds, 2),
            "_added_at": time.time(),
        }
        self._edges.append(edge)
        if _NX_AVAILABLE and self._graph is not None:
            self._graph.add_edge(
                event_id_a,
                event_id_b,
                relation_type=relation_type,
                strength=strength,
                lag_seconds=lag_seconds,
            )
        logger.debug(
            "event_graph.add_relation %s→%s type=%s strength=%.3f",
            event_id_a,
            event_id_b,
            relation_type,
            strength,
        )

    def find_paths(
        self, start_event: str, end_event: str
    ) -> list[list[str]]:
        if not _NX_AVAILABLE or self._graph is None:
            return []
        try:
            paths = list(
                nx.all_simple_paths(self._graph, source=start_event, target=end_event, cutoff=6)
            )
            return paths
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return []

    def get_high_centrality_events(self, top_k: int = 5) -> list[dict[str, Any]]:
        if not _NX_AVAILABLE or self._graph is None or len(self._graph.nodes) == 0:
            return []
        centrality: dict[str, float] = nx.betweenness_centrality(self._graph)
        ranked = sorted(centrality.items(), key=lambda x: x[1], reverse=True)[:top_k]
        result = []
        for node_id, score in ranked:
            node_data = dict(self._graph.nodes.get(node_id, {}))
            node_data.pop("_added_at", None)
            result.append(
                {
                    "event_id": node_id,
                    "centrality_score": round(score, 4),
                    "data": node_data,
                }
            )
        return result

    def export_for_frontend(self) -> dict[str, Any]:
        nodes = [
            {
                "id": eid,
                **{k: v for k, v in data.items() if not k.startswith("_")},
            }
            for eid, data in self._nodes.items()
        ]
        edges = [
            {k: v for k, v in e.items() if not k.startswith("_")}
            for e in self._edges
        ]
        return {
            "nodes": nodes,
            "edges": edges,
            "node_count": len(nodes),
            "edge_count": len(edges),
        }

    def prune_old_events(self, max_age_seconds: float = 3600) -> int:
        cutoff = time.time() - max_age_seconds
        old_ids = [
            eid
            for eid, data in self._nodes.items()
            if data.get("_added_at", 0) < cutoff
        ]
        for eid in old_ids:
            del self._nodes[eid]
            if _NX_AVAILABLE and self._graph is not None and self._graph.has_node(eid):
                self._graph.remove_node(eid)
        self._edges = [
            e for e in self._edges
            if e.get("_added_at", 0) >= cutoff
        ]
        if old_ids:
            logger.debug("event_graph.pruned count=%d", len(old_ids))
        return len(old_ids)

    def stats(self) -> dict[str, int]:
        return {
            "nodes": len(self._nodes),
            "edges": len(self._edges),
        }
