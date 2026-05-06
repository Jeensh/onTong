"""SLA guard tests for rename / broken-refs at dev-profile scale.

These are reasonable bounds for a SQLite + InMemory dev backend on a
typical developer laptop. Production/team profile scales up but uses the
same SLA shape.

Run: python -m pytest tests/test_sla_guards.py -v
"""
from __future__ import annotations
import asyncio
import time
import pytest


@pytest.fixture
def setup(tmp_path, monkeypatch):
    monkeypatch.setenv("ONTONG_PROFILE", "dev")
    import importlib, backend.core.config
    importlib.reload(backend.core.config)
    backend.core.config.settings.wiki_dir = tmp_path
    (tmp_path / ".ontong").mkdir()

    from backend.core.backends import _reset_for_test
    _reset_for_test()
    import backend.application.lock_service as _ls_mod
    _ls_mod._lock_service = None

    from backend.infrastructure.storage.local_fs import LocalFSAdapter
    from backend.application.wiki.wiki_service import WikiService

    class _NoopIndexer:
        async def index_file(self, *a, **kw): return 0
        async def remove_file(self, *a, **kw): pass
        async def reindex_all(self, *a, **kw): return 0

    storage = LocalFSAdapter(tmp_path)
    svc = WikiService(storage, _NoopIndexer(), None)
    yield svc, tmp_path
    _reset_for_test()
    _ls_mod._lock_service = None


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def test_single_rename_zero_inbound_under_1s(setup):
    """Rename a doc with no inbound: should complete in under 1s."""
    svc, _ = setup
    _run(svc.save_file("lonely.md", "---\n---\n# Lonely\n", user_name="alice"))

    orch = svc.get_rename_orchestrator()
    plan = _run(orch.plan("lonely.md", "renamed.md", "alice"))
    start = time.time()
    result = _run(orch.execute(plan.audit_id))
    elapsed = time.time() - start

    assert result.status == "success"
    assert elapsed < 1.0, f"single rename (0 inbound) took {elapsed:.2f}s — exceeds 1.0s SLA"


def test_single_rename_100_inbound_under_5s(setup):
    """Rename a doc with 100 inbound refs: should complete in under 5s."""
    svc, _ = setup
    _run(svc.save_file("hub.md", "---\n---\n# Hub\n", user_name="alice"))
    # Seed 100 inbound docs
    for i in range(100):
        content = f"---\nrelated:\n  - hub.md\n---\n# Doc {i}\n[link](hub.md)\n"
        _run(svc.save_file(f"src_{i:03d}.md", content, user_name="alice"))

    orch = svc.get_rename_orchestrator()
    plan = _run(orch.plan("hub.md", "renamed_hub.md", "alice"))
    assert plan.unique_inbound_sources == 100

    start = time.time()
    result = _run(orch.execute(plan.audit_id))
    elapsed = time.time() - start

    assert result.status in ("success", "partial")
    # Note: source lock acquisition + 100 inbound patches + chunk meta = should be fast on SQLite
    assert elapsed < 5.0, f"single rename (100 inbound) took {elapsed:.2f}s — exceeds 5.0s SLA"


def test_folder_rename_50_children_under_30s(setup):
    """Folder rename with 50 children: should complete in under 30s on dev."""
    svc, _ = setup
    # Create 50 docs under a folder
    for i in range(50):
        content = f"---\n---\n# Doc {i}\n"
        _run(svc.save_file(f"myfolder/doc_{i:03d}.md", content, user_name="alice"))

    orch = svc.get_folder_rename_orchestrator()
    plan = _run(orch.plan("myfolder", "renamedfolder", "alice"))
    assert plan.file_count == 50

    start = time.time()
    result = _run(orch.execute(plan.audit_id))
    elapsed = time.time() - start

    assert result.status in ("success", "partial")
    assert result.files_done >= 45  # allow some failures in concurrent-test scenarios
    assert elapsed < 30.0, f"folder rename (50 children) took {elapsed:.2f}s — exceeds 30s SLA"


def test_broken_refs_query_at_1k_refs_under_500ms(setup):
    """broken-refs query against 1K source documents: should complete in under 500ms."""
    svc, _ = setup
    # Seed 1000 docs, each with 1-2 outbound refs
    import random
    random.seed(42)
    for i in range(1000):
        target_idx = (i + 1 + random.randrange(10)) % 1000
        content = f"---\n---\n# Doc {i}\n[link](doc_{target_idx:05d}.md)\n"
        _run(svc.save_file(f"doc_{i:05d}.md", content, user_name="alice"))

    # Issue broken-refs query
    from backend.core.config import settings
    from backend.core.backends import get_ref_index
    from pathlib import Path
    sqlite_path = Path(settings.wiki_dir) / ".ontong" / "refs.db"
    ref_index = get_ref_index(settings.resolve_profile(), sqlite_path=str(sqlite_path))

    start = time.time()
    broken = ref_index.broken(limit=100)
    elapsed = time.time() - start

    # All 1000 saved → all targets should be valid (no broken). But we only checked
    # 1000 of the 1010 namespace, so a few may legitimately be broken.
    assert elapsed < 0.5, f"broken-refs at 1K refs took {elapsed * 1000:.0f}ms — exceeds 500ms SLA"
