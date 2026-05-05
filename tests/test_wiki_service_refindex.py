"""WikiService → RefIndex hotpath wiring tests.

Verifies that save/delete/move on the wiki triggers the right RefIndex calls.
Uses sqlite backend (dev profile) with a tmp_path wiki dir.
"""
from __future__ import annotations

import pytest
import asyncio
from pathlib import Path

from backend.application.refindex.extractor import RefKind


@pytest.fixture
def wiki_service(tmp_path, monkeypatch):
    """Build a WikiService with sqlite RefIndex pointed at tmp_path/.ontong/refs.db."""
    monkeypatch.setenv("ONTONG_PROFILE", "dev")
    # Make settings.wiki_dir point to tmp_path so save writes there + RefIndex lives there
    import importlib, backend.core.config
    importlib.reload(backend.core.config)
    backend.core.config.settings.wiki_dir = tmp_path

    from backend.core.backends import _reset_for_test
    _reset_for_test()

    from backend.infrastructure.storage.local_fs import LocalFSAdapter
    from backend.application.wiki.wiki_indexer import WikiIndexer
    from backend.application.wiki.wiki_search import WikiSearchService
    from backend.application.wiki.wiki_service import WikiService

    # Stub indexer: avoid Chroma/BM25 in tests
    class _NoopIndexer:
        async def index_file(self, *a, **kw): return 0
        async def remove_file(self, *a, **kw): pass
        async def reindex_all(self, *a, **kw): return 0

    storage = LocalFSAdapter(tmp_path)
    svc = WikiService(storage, _NoopIndexer(), WikiSearchService())

    yield svc

    _reset_for_test()


@pytest.fixture
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.mark.asyncio
async def test_save_extracts_and_indexes_references(wiki_service):
    raw = """---
related:
  - other.md
---
# Doc

See [link](other.md) and [[wikistem]].
"""
    await wiki_service.save_file("source.md", raw, user_name="alice")

    ref_index = wiki_service._get_ref_index_lazy()
    assert ref_index is not None
    out = ref_index.outbound("source.md")
    assert len(out) >= 3  # FM_RELATED + BODY_MD_LINK + BODY_WIKILINK
    targets = sorted(r.target_path for r in out)
    assert "other.md" in targets
    assert "wikistem" in targets


@pytest.mark.asyncio
async def test_save_replaces_previous_references(wiki_service):
    """Re-save replaces refs for the same source."""
    raw1 = "---\nrelated:\n  - old.md\n---\n# A\n[old](old.md)\n"
    raw2 = "---\nrelated:\n  - new.md\n---\n# A\n[new](new.md)\n"
    await wiki_service.save_file("a.md", raw1, user_name="alice")
    await wiki_service.save_file("a.md", raw2, user_name="alice")

    ref_index = wiki_service._get_ref_index_lazy()
    out = ref_index.outbound("a.md")
    targets = sorted(r.target_path for r in out)
    assert "new.md" in targets
    assert "old.md" not in targets


@pytest.mark.asyncio
async def test_delete_removes_references(wiki_service):
    raw = "---\nrelated:\n  - x.md\n---\n# A\n"
    await wiki_service.save_file("a.md", raw, user_name="alice")
    await wiki_service.delete_file("a.md")

    ref_index = wiki_service._get_ref_index_lazy()
    assert ref_index.outbound("a.md") == []


@pytest.mark.asyncio
async def test_move_file_renames_source_in_index(wiki_service):
    raw = "---\nrelated:\n  - target.md\n---\n# A\n[link](target.md)\n"
    await wiki_service.save_file("old.md", raw, user_name="alice")
    await wiki_service.move_file("old.md", "new.md")

    ref_index = wiki_service._get_ref_index_lazy()
    # Old source has no refs
    assert ref_index.outbound("old.md") == []
    # New source has the refs
    new_refs = ref_index.outbound("new.md")
    assert any(r.target_path == "target.md" for r in new_refs)


@pytest.mark.asyncio
async def test_skips_system_paths(wiki_service):
    """_skills/, _personas/, .ontong/ should not be indexed."""
    raw = "# Skill\n[link](other.md)\n"
    await wiki_service.save_file("_skills/my_skill.md", raw, user_name="alice")

    ref_index = wiki_service._get_ref_index_lazy()
    assert ref_index.outbound("_skills/my_skill.md") == []


@pytest.mark.asyncio
async def test_inbound_visible_after_save(wiki_service):
    """Inbound refs are queryable after their source is saved."""
    await wiki_service.save_file("a.md", "---\nrelated:\n  - shared.md\n---\n# A\n", "alice")
    await wiki_service.save_file("b.md", "---\nrelated:\n  - shared.md\n---\n# B\n", "alice")

    ref_index = wiki_service._get_ref_index_lazy()
    inb = ref_index.inbound("shared.md")
    assert sorted(r.source_path for r in inb) == ["a.md", "b.md"]


@pytest.mark.asyncio
async def test_save_failure_in_refindex_is_non_fatal(wiki_service, monkeypatch, tmp_path):
    """If RefIndex blows up, save() should still succeed."""
    raw = "---\n---\n# A\n"

    # Force the lazy resolver to return a broken index
    class _BrokenIndex:
        def upsert_for_source(self, *a, **kw): raise RuntimeError("fake DB error")
    wiki_service._ref_index_cache = _BrokenIndex()

    # Save should not raise
    await wiki_service.save_file("a.md", raw, user_name="alice")
    # File should still be on disk
    assert (tmp_path / "a.md").exists()
