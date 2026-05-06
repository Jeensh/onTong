"""H14 — measure ACL leak window between storage.move and ChromaDB metadata update.

Currently the rename orchestrator does:
    1. storage.move(old, new)
    2. ref_index.rename_source(old, new)
    3. for each inbound: storage.read + patch + write
    4. chunk_updater.update_for_path_rename(old, new)  <- chunk meta updated last

Between (1) and (4), if ACL changes (e.g. moving a private doc into a public
folder), the chunk in ChromaDB still has the OLD access_scope. A search
during this window could return the chunk for an unauthorized user.

This test measures the gap. In dev profile (no ChromaDB connection), the
gap is ~0 because chunk_meta is a no-op. In production, the gap depends on
how fast the orchestrator iterates.

Test does NOT FAIL on dev. It records the gap as a metric.
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


def test_acl_leak_window_measurement(setup):
    """Measure the gap between storage.move (rename committed at FS level) and
    chunk metadata update completion.

    Records a metric for production calibration. Dev profile gap is ~0 because
    chunk_updater is a no-op."""
    svc, tmp_path = setup
    # Seed 5 inbound docs to make the rename non-trivial
    _run(svc.save_file("private.md", "---\n---\n# Private\n", user_name="alice"))
    for i in range(5):
        _run(svc.save_file(f"src_{i}.md",
                           f"---\nrelated:\n  - private.md\n---\n# Src {i}\n",
                           user_name="alice"))

    # Patch storage.move to record exact timestamp
    orch = svc.get_rename_orchestrator()

    move_done_ts = [0.0]
    chunk_meta_done_ts = [0.0]

    original_move = orch._content.storage.move

    async def timed_move(old, new):
        result = await original_move(old, new)
        move_done_ts[0] = time.time()
        return result

    orch._content.storage.move = timed_move

    if orch._chunk_updater is None:
        # Dev profile may not have a chunk_updater (no chroma). Substitute a stub.
        class _StubUpdater:
            async def update_for_path_rename(self, *a, **kw):
                chunk_meta_done_ts[0] = time.time()
                return {"meta_updated": 0, "reindex_triggered": False, "error": None}
        orch._chunk_updater = _StubUpdater()
    else:
        original_update = orch._chunk_updater.update_for_path_rename
        async def timed_update(*a, **kw):
            r = await original_update(*a, **kw)
            chunk_meta_done_ts[0] = time.time()
            return r
        orch._chunk_updater.update_for_path_rename = timed_update

    plan = _run(orch.plan("private.md", "still-private.md", "alice"))
    result = _run(orch.execute(plan.audit_id))
    assert result.status in ("success", "partial")

    leak_window_ms = (chunk_meta_done_ts[0] - move_done_ts[0]) * 1000.0
    # Print for visibility in pytest output
    print(f"\n[ACL leak window measurement] {leak_window_ms:.1f}ms (5 inbound)")

    # On dev profile + 5 inbound + SQLite: typical leak window is 1-50ms.
    # We assert it's under 5 seconds as a sanity check (real production
    # SLA depends on chroma latency and inbound count).
    assert leak_window_ms < 5000.0, (
        f"ACL leak window {leak_window_ms:.1f}ms exceeds 5s sanity bound"
    )
