"""Phase 3 SSE progress event smoke tests."""
from __future__ import annotations
import asyncio
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

    # Subscribe BEFORE running execute()
    from backend.infrastructure.events.event_bus import event_bus

    received: list[tuple[str, dict]] = []

    event_bus.on("rename_started", lambda d: received.append(("rename_started", d)))
    event_bus.on("rename_progress", lambda d: received.append(("rename_progress", d)))
    event_bus.on("rename_finished", lambda d: received.append(("rename_finished", d)))

    from backend.infrastructure.storage.local_fs import LocalFSAdapter
    from backend.application.wiki.wiki_service import WikiService

    class _NoopIndexer:
        async def index_file(self, *a, **kw): return 0
        async def remove_file(self, *a, **kw): pass
        async def reindex_all(self, *a, **kw): return 0

    storage = LocalFSAdapter(tmp_path)
    svc = WikiService(storage, _NoopIndexer(), None)

    asyncio.get_event_loop().run_until_complete(
        svc.save_file("target.md", "---\n---\n# T\n", user_name="alice")
    )
    asyncio.get_event_loop().run_until_complete(
        svc.save_file("a.md", "---\nrelated:\n  - target.md\n---\n# A\n", user_name="alice")
    )

    yield svc, received
    _reset_for_test()


def test_execute_publishes_rename_started_and_finished(setup):
    svc, received = setup
    orch = svc.get_rename_orchestrator()
    plan = asyncio.get_event_loop().run_until_complete(
        orch.plan("target.md", "renamed.md", "alice")
    )
    asyncio.get_event_loop().run_until_complete(orch.execute(plan.audit_id))

    types_received = {t for t, _ in received}
    assert "rename_started" in types_received
    assert "rename_finished" in types_received


def test_finished_event_includes_status_and_counts(setup):
    svc, received = setup
    orch = svc.get_rename_orchestrator()
    plan = asyncio.get_event_loop().run_until_complete(
        orch.plan("target.md", "renamed.md", "alice")
    )
    asyncio.get_event_loop().run_until_complete(orch.execute(plan.audit_id))

    finished = [d for t, d in received if t == "rename_finished"]
    assert len(finished) >= 1
    last = finished[-1]
    assert "status" in last
    assert last["status"] in ("success", "partial")
    assert "done" in last
