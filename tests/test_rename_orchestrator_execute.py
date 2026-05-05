"""RenameOrchestrator.execute() — end-to-end with stubbed Chroma/Indexer."""
from __future__ import annotations
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock


@pytest.fixture
def setup(tmp_path, monkeypatch):
    monkeypatch.setenv("ONTONG_PROFILE", "dev")
    import importlib, backend.core.config
    importlib.reload(backend.core.config)
    backend.core.config.settings.wiki_dir = tmp_path

    from backend.core.backends import _reset_for_test
    _reset_for_test()
    (tmp_path / ".ontong").mkdir()

    from backend.application.refindex.sqlite_backend import SqliteRefIndex
    from backend.application.refindex.extractor import Reference, RefKind, ReferenceExtractor
    from backend.application.rename.sqlite_audit import SqliteAuditStore
    from backend.application.snapshot.sqlite_store import SqliteSnapshotStore
    from backend.application.occ.sqlite_store import SqliteVersionStore
    from backend.application.occ.manager import OCCManager

    ref_index = SqliteRefIndex(str(tmp_path / "refs.db"))
    audit = SqliteAuditStore(str(tmp_path / "audit.db"))
    snap = SqliteSnapshotStore(str(tmp_path / "snap.db"))
    vstore = SqliteVersionStore(str(tmp_path / "v.db"))
    occ = OCCManager(vstore)

    # Seed real files via storage adapter
    from backend.infrastructure.storage.local_fs import LocalFSAdapter
    storage = LocalFSAdapter(tmp_path)

    asyncio.get_event_loop().run_until_complete(
        storage.write("target.md", "---\n---\n# Target\n", user_name="alice")
    )
    asyncio.get_event_loop().run_until_complete(
        storage.write("a.md", "---\nrelated:\n  - target.md\n---\n# A\n[link](target.md)\n", user_name="alice")
    )
    asyncio.get_event_loop().run_until_complete(
        storage.write("b.md", "---\n---\n# B\n[ref](target.md)\n", user_name="alice")
    )

    # Index those refs
    ext = ReferenceExtractor()
    for p in ["a.md", "b.md", "target.md"]:
        wf = asyncio.get_event_loop().run_until_complete(storage.read(p))
        ref_index.upsert_for_source(p, ext.extract(p, wf.raw_content))
    occ.issue("target.md")
    occ.issue("a.md")
    occ.issue("b.md")

    # Mock content_store with .storage attribute
    content_store = MagicMock()
    content_store.storage = storage

    # Mock chunk_updater
    chunk_updater = AsyncMock()
    chunk_updater.update_for_path_rename = AsyncMock(
        return_value={"meta_updated": 0, "reindex_triggered": False, "error": None}
    )

    from backend.application.rename.orchestrator import RenameOrchestrator
    orch = RenameOrchestrator(
        ref_index=ref_index,
        audit_store=audit,
        content_store=content_store,
        occ_manager=occ,
        snapshot_store=snap,
        chunk_updater=chunk_updater,
    )

    yield orch, ref_index, audit, snap, occ, storage, chunk_updater, tmp_path

    _reset_for_test()


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def test_execute_renames_file_and_patches_inbound(setup):
    orch, ref_index, audit, snap, occ, storage, chunk_updater, tmp_path = setup
    plan = _run(orch.plan("target.md", "renamed.md", "alice"))
    result = _run(orch.execute(plan.audit_id))

    assert result.status in ("success", "partial")
    # File moved
    assert not (tmp_path / "target.md").exists()
    assert (tmp_path / "renamed.md").exists()
    # Inbound patched
    a_content = (tmp_path / "a.md").read_text(encoding="utf-8")
    b_content = (tmp_path / "b.md").read_text(encoding="utf-8")
    assert "renamed.md" in a_content
    assert "renamed.md" in b_content
    assert "target.md" not in a_content
    assert "target.md" not in b_content
    # RefIndex source key updated
    assert ref_index.outbound("target.md") == []
    # New source has refs
    assert any(r.target_path == "renamed.md" for r in ref_index.outbound("a.md"))


def test_execute_creates_pre_rename_snapshot(setup):
    orch, ref_index, audit, snap, occ, storage, chunk_updater, tmp_path = setup
    plan = _run(orch.plan("target.md", "renamed.md", "alice"))
    _run(orch.execute(plan.audit_id))

    # Pre-rename snapshot at OLD path
    snaps = snap.list("target.md")
    assert any(s.reason == "pre_rename" for s in snaps)


def test_execute_advances_occ_version(setup):
    """OCC: after rename, old path has no version, new path has the old version."""
    orch, ref_index, audit, snap, occ, storage, chunk_updater, tmp_path = setup
    old_v = occ.current("target.md")
    plan = _run(orch.plan("target.md", "renamed.md", "alice"))
    _run(orch.execute(plan.audit_id))

    assert occ.current("target.md") is None
    assert occ.current("renamed.md") == old_v


def test_execute_calls_chunk_updater(setup):
    orch, _, _, _, _, _, chunk_updater, _ = setup
    plan = _run(orch.plan("target.md", "renamed.md", "alice"))
    _run(orch.execute(plan.audit_id))
    chunk_updater.update_for_path_rename.assert_called_once()
    args = chunk_updater.update_for_path_rename.call_args
    assert args.args[0] == "target.md"
    assert args.args[1] == "renamed.md"


def test_execute_audit_progress(setup):
    orch, _, audit, _, _, _, _, _ = setup
    plan = _run(orch.plan("target.md", "renamed.md", "alice"))
    result = _run(orch.execute(plan.audit_id))

    audit_row = audit.get_audit(int(plan.audit_id))
    assert audit_row.status in ("success", "partial")
    progress = audit.progress(int(plan.audit_id))
    assert progress["total"] >= 2  # 2 inbound jobs + 1 chunk_meta = 3


def test_execute_with_no_inbound_still_succeeds(setup):
    """A doc with no inbound refs renames cleanly."""
    orch, ref_index, _, _, _, storage, _, tmp_path = setup
    _run(storage.write("lonely.md", "---\n---\n# Lonely\n", user_name="alice"))
    ref_index.upsert_for_source("lonely.md", [])
    plan = _run(orch.plan("lonely.md", "lonely_renamed.md", "alice"))
    result = _run(orch.execute(plan.audit_id))

    assert result.status == "success"
    assert result.inbound_done == 0
    assert (tmp_path / "lonely_renamed.md").exists()


def test_execute_releases_locks_on_success(setup):
    orch, _, _, _, _, _, _, _ = setup
    plan = _run(orch.plan("target.md", "renamed.md", "alice"))
    _run(orch.execute(plan.audit_id))

    from backend.application.lock_service import get_lock_service
    svc = get_lock_service()
    # Source lock released (target.md is the pre-rename path)
    assert svc.status("target.md") is None or svc.status("renamed.md") is None
    # No leftover inbound locks
    assert svc.status("a.md") is None
    assert svc.status("b.md") is None
