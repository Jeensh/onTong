"""Knowledge Graph Store — InMemory and Redis implementations.

Stores typed, weighted Relationship edges between documents.
Follows the same ABC + factory pattern as CitationTracker/FeedbackTracker.
"""

from __future__ import annotations

import json
import logging
import time
from abc import ABC, abstractmethod
from collections import defaultdict

from backend.core.schemas import Relationship, GraphResult, GraphStats

logger = logging.getLogger(__name__)


class GraphStore(ABC):
    """Abstract base for relationship storage."""

    @abstractmethod
    def add(self, rel: Relationship) -> None:
        """Add a relationship (upsert by source+target+rel_type)."""

    @abstractmethod
    def remove(self, source: str, target: str, rel_type: str) -> None:
        """Remove a specific relationship."""

    @abstractmethod
    def remove_all(self, path: str) -> None:
        """Remove all relationships involving this path (as source or target)."""

    @abstractmethod
    def get(self, path: str, rel_type: str = "") -> list[Relationship]:
        """Get relationships where path is source or target. Filter by rel_type if given."""

    @abstractmethod
    def get_graph(self, center: str, depth: int = 1) -> GraphResult:
        """BFS traversal from center up to depth hops."""

    @abstractmethod
    def stats(self) -> GraphStats:
        """Return aggregate statistics."""

    @abstractmethod
    def clear(self) -> None:
        """Remove all relationships."""


def _rel_key(rel: Relationship) -> str:
    """Unique key for deduplication: source|target|rel_type."""
    return f"{rel.source}|{rel.target}|{rel.rel_type}"


class InMemoryGraphStore(GraphStore):
    """Dict-based graph store for development and testing."""

    def __init__(self) -> None:
        # source_path → list[Relationship]
        self._outgoing: dict[str, dict[str, Relationship]] = defaultdict(dict)
        # target_path → list[Relationship]
        self._incoming: dict[str, dict[str, Relationship]] = defaultdict(dict)

    def add(self, rel: Relationship) -> None:
        if not rel.created_at:
            rel = rel.model_copy(update={"created_at": time.time()})
        key = _rel_key(rel)
        self._outgoing[rel.source][key] = rel
        self._incoming[rel.target][key] = rel

    def remove(self, source: str, target: str, rel_type: str) -> None:
        key = f"{source}|{target}|{rel_type}"
        self._outgoing.get(source, {}).pop(key, None)
        self._incoming.get(target, {}).pop(key, None)

    def remove_all(self, path: str) -> None:
        # Remove outgoing
        for key, rel in list(self._outgoing.get(path, {}).items()):
            self._incoming.get(rel.target, {}).pop(key, None)
        self._outgoing.pop(path, None)

        # Remove incoming
        for key, rel in list(self._incoming.get(path, {}).items()):
            self._outgoing.get(rel.source, {}).pop(key, None)
        self._incoming.pop(path, None)

    def get(self, path: str, rel_type: str = "") -> list[Relationship]:
        rels: list[Relationship] = []
        seen: set[str] = set()
        for key, rel in self._outgoing.get(path, {}).items():
            if rel_type and rel.rel_type != rel_type:
                continue
            if key not in seen:
                rels.append(rel)
                seen.add(key)
        for key, rel in self._incoming.get(path, {}).items():
            if rel_type and rel.rel_type != rel_type:
                continue
            if key not in seen:
                rels.append(rel)
                seen.add(key)
        return rels

    def get_graph(self, center: str, depth: int = 1) -> GraphResult:
        all_rels: list[Relationship] = []
        visited: set[str] = set()
        frontier: set[str] = {center}

        for _ in range(depth):
            next_frontier: set[str] = set()
            for node in frontier:
                if node in visited:
                    continue
                visited.add(node)
                rels = self.get(node)
                for rel in rels:
                    all_rels.append(rel)
                    other = rel.target if rel.source == node else rel.source
                    if other not in visited:
                        next_frontier.add(other)
            frontier = next_frontier

        # Deduplicate
        seen: dict[str, Relationship] = {}
        for rel in all_rels:
            key = _rel_key(rel)
            if key not in seen:
                seen[key] = rel
        return GraphResult(center=center, relationships=list(seen.values()), depth=depth)

    def stats(self) -> GraphStats:
        nodes: set[str] = set()
        type_dist: dict[str, int] = defaultdict(int)
        total_edges = 0
        seen: set[str] = set()

        for source, rels in self._outgoing.items():
            for key, rel in rels.items():
                if key in seen:
                    continue
                seen.add(key)
                nodes.add(rel.source)
                nodes.add(rel.target)
                type_dist[rel.rel_type] += 1
                total_edges += 1

        return GraphStats(
            total_nodes=len(nodes),
            total_edges=total_edges,
            type_distribution=dict(type_dist),
        )

    def clear(self) -> None:
        self._outgoing.clear()
        self._incoming.clear()


class RedisGraphStore(GraphStore):
    """Redis-backed graph store using sorted sets for adjacency."""

    PREFIX = "ontong:graph"

    def __init__(self, redis_client) -> None:
        self._r = redis_client

    def _out_key(self, path: str) -> str:
        return f"{self.PREFIX}:out:{path}"

    def _in_key(self, path: str) -> str:
        return f"{self.PREFIX}:in:{path}"

    def _encode(self, rel: Relationship) -> str:
        return json.dumps(rel.model_dump(), ensure_ascii=False)

    def _decode(self, data: str) -> Relationship:
        return Relationship.model_validate(json.loads(data))

    def add(self, rel: Relationship) -> None:
        if not rel.created_at:
            rel = rel.model_copy(update={"created_at": time.time()})
        key = _rel_key(rel)
        encoded = self._encode(rel)
        pipe = self._r.pipeline()
        # Store in both directions with the key as member identifier
        pipe.hset(self._out_key(rel.source), key, encoded)
        pipe.hset(self._in_key(rel.target), key, encoded)
        # Track all nodes for stats
        pipe.sadd(f"{self.PREFIX}:nodes", rel.source, rel.target)
        pipe.execute()

    def remove(self, source: str, target: str, rel_type: str) -> None:
        key = f"{source}|{target}|{rel_type}"
        pipe = self._r.pipeline()
        pipe.hdel(self._out_key(source), key)
        pipe.hdel(self._in_key(target), key)
        pipe.execute()

    def remove_all(self, path: str) -> None:
        pipe = self._r.pipeline()
        # Get all outgoing to clean up incoming side
        out_data = self._r.hgetall(self._out_key(path))
        for raw in out_data.values():
            rel = self._decode(raw)
            pipe.hdel(self._in_key(rel.target), _rel_key(rel))

        # Get all incoming to clean up outgoing side
        in_data = self._r.hgetall(self._in_key(path))
        for raw in in_data.values():
            rel = self._decode(raw)
            pipe.hdel(self._out_key(rel.source), _rel_key(rel))

        pipe.delete(self._out_key(path))
        pipe.delete(self._in_key(path))
        pipe.execute()

    def get(self, path: str, rel_type: str = "") -> list[Relationship]:
        rels: list[Relationship] = []
        seen: set[str] = set()

        for raw in self._r.hvals(self._out_key(path)):
            rel = self._decode(raw)
            if rel_type and rel.rel_type != rel_type:
                continue
            key = _rel_key(rel)
            if key not in seen:
                rels.append(rel)
                seen.add(key)

        for raw in self._r.hvals(self._in_key(path)):
            rel = self._decode(raw)
            if rel_type and rel.rel_type != rel_type:
                continue
            key = _rel_key(rel)
            if key not in seen:
                rels.append(rel)
                seen.add(key)

        return rels

    def get_graph(self, center: str, depth: int = 1) -> GraphResult:
        all_rels: list[Relationship] = []
        visited: set[str] = set()
        frontier: set[str] = {center}

        for _ in range(depth):
            next_frontier: set[str] = set()
            for node in frontier:
                if node in visited:
                    continue
                visited.add(node)
                rels = self.get(node)
                for rel in rels:
                    all_rels.append(rel)
                    other = rel.target if rel.source == node else rel.source
                    if other not in visited:
                        next_frontier.add(other)
            frontier = next_frontier

        seen: dict[str, Relationship] = {}
        for rel in all_rels:
            key = _rel_key(rel)
            if key not in seen:
                seen[key] = rel
        return GraphResult(center=center, relationships=list(seen.values()), depth=depth)

    def stats(self) -> GraphStats:
        node_count = self._r.scard(f"{self.PREFIX}:nodes") or 0
        type_dist: dict[str, int] = defaultdict(int)
        total_edges = 0

        # Scan all outgoing keys
        cursor = 0
        while True:
            cursor, keys = self._r.scan(cursor, match=f"{self.PREFIX}:out:*", count=100)
            for okey in keys:
                for raw in self._r.hvals(okey):
                    rel = self._decode(raw)
                    type_dist[rel.rel_type] += 1
                    total_edges += 1
            if cursor == 0:
                break

        return GraphStats(
            total_nodes=node_count,
            total_edges=total_edges,
            type_distribution=dict(type_dist),
        )

    def clear(self) -> None:
        cursor = 0
        while True:
            cursor, keys = self._r.scan(cursor, match=f"{self.PREFIX}:*", count=100)
            if keys:
                self._r.delete(*keys)
            if cursor == 0:
                break


def create_graph_store() -> GraphStore:
    """Factory: Redis if available, else InMemory."""
    try:
        import redis
        r = redis.Redis(host="localhost", port=6379, db=0, decode_responses=True)
        r.ping()
        logger.info("Redis graph store connected")
        return RedisGraphStore(r)
    except Exception:
        logger.info("Using in-memory graph store (Redis unavailable)")
        return InMemoryGraphStore()
