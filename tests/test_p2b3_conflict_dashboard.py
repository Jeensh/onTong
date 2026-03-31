"""Tests for conflict detection — incremental model.

Validates:
1. ConflictStore (InMemory) CRUD operations
2. ConflictDetectionService.check_file via mock ChromaDB
3. DuplicatePair schema and is_pair_resolved
4. get_pairs filter logic
"""

import time
import pytest
import numpy as np

from backend.application.conflict.conflict_store import (
    InMemoryConflictStore,
    StoredConflict,
    _canonical_key,
)
from backend.application.conflict.conflict_service import (
    ConflictDetectionService,
    DuplicatePair,
    is_pair_resolved,
    SIMILARITY_THRESHOLD,
)


# ── ConflictStore tests ──────────────────────────────────────────────


class TestInMemoryConflictStore:
    def test_replace_and_get(self):
        store = InMemoryConflictStore()
        pairs = [
            StoredConflict("a.md", "b.md", 0.97, time.time()),
            StoredConflict("a.md", "c.md", 0.96, time.time()),
        ]
        store.replace_for_file("a.md", pairs)
        result = store.get_all_pairs()
        assert len(result) == 2
        assert result[0].similarity >= result[1].similarity

    def test_canonical_ordering(self):
        store = InMemoryConflictStore()
        store.replace_for_file("z.md", [
            StoredConflict("z.md", "a.md", 0.95, time.time()),
        ])
        pair = store.get_all_pairs()[0]
        assert pair.file_a == "a.md"
        assert pair.file_b == "z.md"

    def test_replace_removes_old(self):
        store = InMemoryConflictStore()
        store.replace_for_file("a.md", [
            StoredConflict("a.md", "b.md", 0.97, time.time()),
        ])
        store.replace_for_file("a.md", [
            StoredConflict("a.md", "c.md", 0.96, time.time()),
        ])
        pairs = store.get_all_pairs()
        assert len(pairs) == 1
        assert pairs[0].file_b == "c.md"

    def test_remove_for_file(self):
        store = InMemoryConflictStore()
        store.replace_for_file("a.md", [
            StoredConflict("a.md", "b.md", 0.97, time.time()),
            StoredConflict("a.md", "c.md", 0.96, time.time()),
        ])
        store.remove_for_file("b.md")
        pairs = store.get_all_pairs()
        assert len(pairs) == 1
        assert "b.md" not in (pairs[0].file_a, pairs[0].file_b)

    def test_remove_nonexistent(self):
        store = InMemoryConflictStore()
        store.remove_for_file("nonexistent.md")  # should not raise

    def test_update_metadata(self):
        store = InMemoryConflictStore()
        store.replace_for_file("a.md", [
            StoredConflict("a.md", "b.md", 0.97, time.time(), {"status": "active"}, {}),
        ])
        store.update_metadata("a.md", {"status": "deprecated", "superseded_by": "b.md"})
        pair = store.get_all_pairs()[0]
        assert pair.meta_a["status"] == "deprecated"

    def test_clear(self):
        store = InMemoryConflictStore()
        store.replace_for_file("a.md", [
            StoredConflict("a.md", "b.md", 0.97, time.time()),
        ])
        store.clear()
        assert len(store.get_all_pairs()) == 0

    def test_bidirectional_index(self):
        store = InMemoryConflictStore()
        store.replace_for_file("a.md", [
            StoredConflict("a.md", "b.md", 0.97, time.time()),
        ])
        # Removing b.md should also remove the pair from a.md's perspective
        store.remove_for_file("b.md")
        assert len(store.get_all_pairs()) == 0


# ── is_pair_resolved tests ──────────────────────────────────────────


class TestIsPairResolved:
    def test_superseded_by(self):
        assert is_pair_resolved("a.md", "b.md", {"superseded_by": "b.md"}, {})

    def test_superseded_by_reverse(self):
        assert is_pair_resolved("a.md", "b.md", {}, {"superseded_by": "a.md"})

    def test_supersedes(self):
        assert is_pair_resolved("a.md", "b.md", {"supersedes": "b.md"}, {})

    def test_not_resolved(self):
        assert not is_pair_resolved("a.md", "b.md", {}, {})

    def test_unrelated_lineage(self):
        assert not is_pair_resolved("a.md", "b.md", {"superseded_by": "c.md"}, {})


# ── DuplicatePair schema ────────────────────────────────────────────


class TestDuplicatePair:
    def test_schema(self):
        p = DuplicatePair(
            file_a="a.md",
            file_b="b.md",
            similarity=0.92,
            meta_a={"domain": "IT"},
            meta_b={"domain": "IT"},
        )
        assert p.file_a == "a.md"
        assert p.similarity == 0.92

    def test_default_meta(self):
        p = DuplicatePair(file_a="a.md", file_b="b.md", similarity=0.9)
        assert p.meta_a == {}
        assert p.meta_b == {}
        assert p.resolved is False


# ── ConflictDetectionService tests ──────────────────────────────────


class MockChroma:
    """Mock ChromaDB that simulates HNSW behavior."""

    def __init__(self, file_embeddings: dict[str, list], file_metadatas: dict[str, dict]):
        self._file_embs = file_embeddings
        self._file_metas = file_metadatas

    def get_file_embeddings(self, file_path: str) -> dict:
        embs = self._file_embs.get(file_path, [])
        metas = [self._file_metas.get(file_path, {"file_path": file_path})] * len(embs)
        return {"ids": [f"{file_path}_{i}" for i in range(len(embs))],
                "embeddings": embs, "metadatas": metas}

    def query_by_embedding(self, embedding, n_results=10, where=None):
        """Simulate HNSW: compute cosine distance against all stored embeddings."""
        query = np.array(embedding)
        q_norm = np.linalg.norm(query)
        if q_norm == 0:
            return {"ids": [[]], "metadatas": [[]], "distances": [[]]}

        results = []
        for fp, embs in self._file_embs.items():
            for i, emb in enumerate(embs):
                e = np.array(emb)
                e_norm = np.linalg.norm(e)
                if e_norm == 0:
                    continue
                cos_sim = np.dot(query, e) / (q_norm * e_norm)
                distance = 1.0 - cos_sim
                results.append((f"{fp}_{i}", self._file_metas.get(fp, {"file_path": fp}), distance))

        results.sort(key=lambda x: x[2])
        results = results[:n_results]

        return {
            "ids": [[r[0] for r in results]],
            "metadatas": [[r[1] for r in results]],
            "distances": [[r[2] for r in results]],
        }

    def get_all_embeddings(self):
        all_ids, all_embs, all_metas = [], [], []
        for fp, embs in self._file_embs.items():
            meta = self._file_metas.get(fp, {"file_path": fp})
            for i, emb in enumerate(embs):
                all_ids.append(f"{fp}_{i}")
                all_embs.append(emb)
                all_metas.append(meta)
        return {"ids": all_ids, "embeddings": all_embs, "metadatas": all_metas}


class TestConflictDetectionService:
    def _make_service(self):
        file_embs = {
            "a.md": [[1.0, 0.0, 0.0], [0.9, 0.1, 0.0]],
            "b.md": [[0.95, 0.05, 0.0]],
            "c.md": [[0.0, 0.0, 1.0]],
        }
        file_metas = {
            "a.md": {"file_path": "a.md", "domain": "IT"},
            "b.md": {"file_path": "b.md", "domain": "IT"},
            "c.md": {"file_path": "c.md", "domain": "HR"},
        }
        chroma = MockChroma(file_embs, file_metas)
        store = InMemoryConflictStore()
        return ConflictDetectionService(chroma, store), store

    def test_check_file_finds_similar(self):
        svc, store = self._make_service()
        pairs = svc.check_file("a.md", threshold=0.9)
        assert len(pairs) >= 1
        found_b = any(p.file_b == "b.md" or p.file_a == "b.md" for p in pairs)
        assert found_b, f"Expected a.md<->b.md pair, got {[(p.file_a, p.file_b) for p in pairs]}"

    def test_check_file_excludes_dissimilar(self):
        svc, store = self._make_service()
        pairs = svc.check_file("a.md", threshold=0.9)
        found_c = any("c.md" in (p.file_a, p.file_b) for p in pairs)
        assert not found_c, "c.md should not pair with a.md at threshold 0.9"

    def test_check_file_stores_in_store(self):
        svc, store = self._make_service()
        svc.check_file("a.md", threshold=0.9)
        assert len(store.get_all_pairs()) >= 1

    def test_check_file_no_embeddings(self):
        chroma = MockChroma({}, {})
        store = InMemoryConflictStore()
        svc = ConflictDetectionService(chroma, store)
        pairs = svc.check_file("nonexistent.md")
        assert pairs == []

    def test_remove_file(self):
        svc, store = self._make_service()
        svc.check_file("a.md", threshold=0.9)
        svc.remove_file("a.md")
        assert len(store.get_all_pairs()) == 0

    def test_get_pairs_filter(self):
        svc, store = self._make_service()
        svc.check_file("a.md", threshold=0.9)

        # Update metadata to resolve
        store.update_metadata("a.md", {"superseded_by": "b.md"})

        resolved = svc.get_pairs(filter_mode="resolved")
        unresolved = svc.get_pairs(filter_mode="unresolved")
        all_pairs = svc.get_pairs(filter_mode="all")

        assert len(resolved) >= 1
        assert all(p.resolved for p in resolved)
        assert all(not p.resolved for p in unresolved)
        assert len(all_pairs) == len(resolved) + len(unresolved)

    def test_full_scan(self):
        svc, store = self._make_service()
        progress_calls = []
        svc.full_scan(threshold=0.9, progress_callback=lambda c, t: progress_calls.append((c, t)))
        assert len(store.get_all_pairs()) >= 1
        assert len(progress_calls) >= 1

    def test_find_duplicates_backward_compat(self):
        svc, store = self._make_service()
        svc.check_file("a.md", threshold=0.9)
        pairs = svc.find_duplicates(threshold=0.9)
        assert isinstance(pairs, list)
        assert all(isinstance(p, DuplicatePair) for p in pairs)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
