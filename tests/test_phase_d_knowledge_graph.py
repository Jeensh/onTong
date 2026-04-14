"""Phase D — Knowledge Graph Unification tests.

Tests:
- Relationship model: creation, serialization
- InMemoryGraphStore: add, get, remove, remove_all, get_graph (BFS), stats
- GraphBuilder: metadata → related/supersedes, conflicts → conflicts
- GraphStats: type distribution
"""

import time
import pytest
from unittest.mock import MagicMock

from backend.core.schemas import Relationship, GraphResult, GraphStats
from backend.application.graph.graph_store import InMemoryGraphStore, _rel_key
from backend.application.graph.graph_builder import GraphBuilder


# ── Relationship Model ───────────────────────────────────────────

class TestRelationshipModel:
    def test_create(self):
        rel = Relationship(
            source="a.md", target="b.md", rel_type="related",
            strength=0.8, created_by="user:admin",
        )
        assert rel.source == "a.md"
        assert rel.target == "b.md"
        assert rel.rel_type == "related"
        assert rel.strength == 0.8

    def test_defaults(self):
        rel = Relationship(source="a.md", target="b.md", rel_type="cites")
        assert rel.strength == 1.0
        assert rel.created_by == "system"
        assert rel.created_at == 0.0
        assert rel.metadata == {}

    def test_serialization(self):
        rel = Relationship(
            source="a.md", target="b.md", rel_type="conflicts",
            metadata={"severity": "high"},
        )
        d = rel.model_dump()
        assert d["source"] == "a.md"
        assert d["metadata"]["severity"] == "high"
        # Round-trip
        rel2 = Relationship.model_validate(d)
        assert rel2.rel_type == "conflicts"


# ── InMemoryGraphStore ───────────────────────────────────────────

class TestInMemoryGraphStore:
    def test_add_and_get(self):
        store = InMemoryGraphStore()
        rel = Relationship(source="a.md", target="b.md", rel_type="related")
        store.add(rel)

        # Get from source side
        rels = store.get("a.md")
        assert len(rels) == 1
        assert rels[0].target == "b.md"

        # Get from target side
        rels = store.get("b.md")
        assert len(rels) == 1
        assert rels[0].source == "a.md"

    def test_get_with_type_filter(self):
        store = InMemoryGraphStore()
        store.add(Relationship(source="a.md", target="b.md", rel_type="related"))
        store.add(Relationship(source="a.md", target="c.md", rel_type="supersedes"))

        rels = store.get("a.md", rel_type="related")
        assert len(rels) == 1
        assert rels[0].target == "b.md"

    def test_remove(self):
        store = InMemoryGraphStore()
        store.add(Relationship(source="a.md", target="b.md", rel_type="related"))
        store.remove("a.md", "b.md", "related")

        assert len(store.get("a.md")) == 0
        assert len(store.get("b.md")) == 0

    def test_remove_all(self):
        store = InMemoryGraphStore()
        store.add(Relationship(source="a.md", target="b.md", rel_type="related"))
        store.add(Relationship(source="c.md", target="a.md", rel_type="supersedes"))
        store.add(Relationship(source="b.md", target="c.md", rel_type="related"))

        store.remove_all("a.md")

        # a.md relationships gone
        assert len(store.get("a.md")) == 0
        # b→c still exists
        assert len(store.get("b.md")) == 1
        assert store.get("b.md")[0].target == "c.md"

    def test_upsert_deduplication(self):
        store = InMemoryGraphStore()
        rel1 = Relationship(source="a.md", target="b.md", rel_type="related", strength=0.5)
        rel2 = Relationship(source="a.md", target="b.md", rel_type="related", strength=0.9)
        store.add(rel1)
        store.add(rel2)

        # Same key, so should be overwritten
        rels = store.get("a.md")
        assert len(rels) == 1
        assert rels[0].strength == 0.9

    def test_get_graph_depth_1(self):
        store = InMemoryGraphStore()
        store.add(Relationship(source="a.md", target="b.md", rel_type="related"))
        store.add(Relationship(source="b.md", target="c.md", rel_type="related"))
        store.add(Relationship(source="c.md", target="d.md", rel_type="related"))

        result = store.get_graph("a.md", depth=1)
        assert result.center == "a.md"
        # depth=1: only a→b visible
        paths = {r.target for r in result.relationships}
        assert "b.md" in paths
        # c.md should not appear at depth=1 from a.md
        assert "d.md" not in paths

    def test_get_graph_depth_2(self):
        store = InMemoryGraphStore()
        store.add(Relationship(source="a.md", target="b.md", rel_type="related"))
        store.add(Relationship(source="b.md", target="c.md", rel_type="related"))
        store.add(Relationship(source="c.md", target="d.md", rel_type="related"))

        result = store.get_graph("a.md", depth=2)
        targets = {r.target for r in result.relationships}
        assert "b.md" in targets
        assert "c.md" in targets
        # d.md is at depth 3, not visible at depth 2
        assert "d.md" not in targets

    def test_stats(self):
        store = InMemoryGraphStore()
        store.add(Relationship(source="a.md", target="b.md", rel_type="related"))
        store.add(Relationship(source="a.md", target="c.md", rel_type="supersedes"))
        store.add(Relationship(source="b.md", target="c.md", rel_type="conflicts"))

        stats = store.stats()
        assert stats.total_nodes == 3
        assert stats.total_edges == 3
        assert stats.type_distribution["related"] == 1
        assert stats.type_distribution["supersedes"] == 1
        assert stats.type_distribution["conflicts"] == 1

    def test_clear(self):
        store = InMemoryGraphStore()
        store.add(Relationship(source="a.md", target="b.md", rel_type="related"))
        store.clear()
        assert store.stats().total_edges == 0

    def test_auto_timestamp(self):
        store = InMemoryGraphStore()
        rel = Relationship(source="a.md", target="b.md", rel_type="related")
        assert rel.created_at == 0.0
        store.add(rel)
        stored = store.get("a.md")[0]
        assert stored.created_at > 0


# ── GraphBuilder ─────────────────────────────────────────────────

class TestGraphBuilder:
    def _mock_meta_index(self, files: dict) -> MagicMock:
        mock = MagicMock()
        mock._load.return_value = {"files": files}
        return mock

    def test_build_related(self):
        store = InMemoryGraphStore()
        meta = self._mock_meta_index({
            "a.md": {"related": ["b.md", "c.md"], "created_by": "admin"},
            "b.md": {"related": [], "created_by": "user1"},
        })
        builder = GraphBuilder(store, meta)
        count = builder.rebuild_all()

        assert count == 2  # a→b, a→c
        rels = store.get("a.md", rel_type="related")
        targets = {r.target for r in rels}
        assert targets == {"b.md", "c.md"}

    def test_build_supersedes(self):
        store = InMemoryGraphStore()
        meta = self._mock_meta_index({
            "v2.md": {"supersedes": "v1.md", "created_by": "admin"},
            "v1.md": {},
        })
        builder = GraphBuilder(store, meta)
        count = builder.rebuild_all()

        assert count == 1
        rels = store.get("v2.md", rel_type="supersedes")
        assert len(rels) == 1
        assert rels[0].target == "v1.md"

    def test_build_conflicts(self):
        store = InMemoryGraphStore()
        meta = self._mock_meta_index({})

        mock_conflict_store = MagicMock()
        mock_conflict = MagicMock()
        mock_conflict.file_a = "a.md"
        mock_conflict.file_b = "b.md"
        mock_conflict.similarity = 0.9
        mock_conflict.resolved = False
        mock_conflict.detected_at = 1000.0
        mock_conflict.conflict_type = "factual_contradiction"
        mock_conflict.severity = "high"
        mock_conflict_store.get_all_pairs.return_value = [mock_conflict]

        builder = GraphBuilder(store, meta, conflict_store=mock_conflict_store)
        count = builder.rebuild_all()

        assert count == 1
        rels = store.get("a.md", rel_type="conflicts")
        assert len(rels) == 1
        assert rels[0].strength == 0.9
        assert rels[0].metadata["severity"] == "high"

    def test_skip_resolved_conflicts(self):
        store = InMemoryGraphStore()
        meta = self._mock_meta_index({})

        mock_conflict_store = MagicMock()
        mock_conflict = MagicMock()
        mock_conflict.file_a = "a.md"
        mock_conflict.file_b = "b.md"
        mock_conflict.resolved = True
        mock_conflict_store.get_all_pairs.return_value = [mock_conflict]

        builder = GraphBuilder(store, meta, conflict_store=mock_conflict_store)
        count = builder.rebuild_all()
        assert count == 0

    def test_rebuild_file(self):
        store = InMemoryGraphStore()
        meta = self._mock_meta_index({
            "a.md": {"related": ["b.md"], "created_by": "admin"},
            "b.md": {"related": ["a.md"], "created_by": "user1"},
        })
        builder = GraphBuilder(store, meta)
        builder.rebuild_all()

        # Modify a.md's relations
        meta._load.return_value = {"files": {
            "a.md": {"related": ["c.md"], "created_by": "admin"},
            "b.md": {"related": ["a.md"], "created_by": "user1"},
        }}
        builder.rebuild_file("a.md")

        # a.md now points to c.md, not b.md
        rels_a = store.get("a.md", rel_type="related")
        outgoing = [r for r in rels_a if r.source == "a.md"]
        assert len(outgoing) == 1
        assert outgoing[0].target == "c.md"

    def test_full_rebuild_clears_old(self):
        store = InMemoryGraphStore()
        store.add(Relationship(source="x.md", target="y.md", rel_type="old_type"))
        meta = self._mock_meta_index({})
        builder = GraphBuilder(store, meta)
        builder.rebuild_all()

        assert store.stats().total_edges == 0

    def test_combined_sources(self):
        store = InMemoryGraphStore()
        meta = self._mock_meta_index({
            "a.md": {"related": ["b.md"], "created_by": "admin"},
        })

        mock_conflict_store = MagicMock()
        mock_conflict = MagicMock()
        mock_conflict.file_a = "a.md"
        mock_conflict.file_b = "c.md"
        mock_conflict.similarity = 0.85
        mock_conflict.resolved = False
        mock_conflict.detected_at = 1000.0
        mock_conflict.conflict_type = "scope_overlap"
        mock_conflict.severity = "medium"
        mock_conflict_store.get_all_pairs.return_value = [mock_conflict]

        builder = GraphBuilder(store, meta, conflict_store=mock_conflict_store)
        count = builder.rebuild_all()

        assert count == 2  # 1 related + 1 conflict
        stats = store.stats()
        assert stats.type_distribution.get("related", 0) == 1
        assert stats.type_distribution.get("conflicts", 0) == 1


# ── GraphResult / GraphStats models ─────────────────────────────

class TestGraphModels:
    def test_graph_result_defaults(self):
        result = GraphResult(center="a.md")
        assert result.relationships == []
        assert result.depth == 1

    def test_graph_stats_defaults(self):
        stats = GraphStats()
        assert stats.total_nodes == 0
        assert stats.total_edges == 0
        assert stats.type_distribution == {}
