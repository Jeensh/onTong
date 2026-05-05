"""AuditStore tests parametrized over sqlite (postgres requires running DB)."""
from __future__ import annotations
import pytest


@pytest.fixture
def store(tmp_path):
    from backend.application.rename.sqlite_audit import SqliteAuditStore
    return SqliteAuditStore(str(tmp_path / "audit.db"))


def test_create_audit_returns_id(store):
    aid = store.create_audit("rename", "alice", {"old_path": "a.md", "new_path": "b.md"})
    assert aid > 0
    row = store.get_audit(aid)
    assert row.op == "rename"
    assert row.actor == "alice"
    assert row.status == "running"
    assert row.payload["old_path"] == "a.md"


def test_update_audit_status(store):
    aid = store.create_audit("rename", "alice", {})
    store.update_audit_status(aid, "success")
    row = store.get_audit(aid)
    assert row.status == "success"
    assert row.finished_at is not None


def test_update_audit_with_error(store):
    aid = store.create_audit("rename", "alice", {})
    store.update_audit_status(aid, "failed", error="boom")
    row = store.get_audit(aid)
    assert row.status == "failed"
    assert row.error == "boom"


def test_list_audits_filters(store):
    store.create_audit("rename", "alice", {})
    store.create_audit("rename", "bob", {})
    store.create_audit("delete", "alice", {})
    alice_only = store.list_audits(actor="alice")
    assert all(a.actor == "alice" for a in alice_only)
    assert len(alice_only) == 2

    rename_only = store.list_audits(op="rename")
    assert len(rename_only) == 2


def test_add_and_list_jobs(store):
    aid = store.create_audit("rename", "alice", {})
    n = store.add_jobs(aid, [("patch_inbound", "src1.md"), ("patch_inbound", "src2.md")])
    assert n == 2
    jobs = store.list_jobs(aid)
    assert len(jobs) == 2
    assert all(j.status == "pending" for j in jobs)


def test_update_job_status_and_attempts(store):
    aid = store.create_audit("rename", "alice", {})
    store.add_jobs(aid, [("patch_inbound", "x.md")])
    job_id = store.list_jobs(aid)[0].id
    store.update_job(job_id, status="running")
    store.update_job(job_id, status="failed", last_error="boom")
    j = store.list_jobs(aid)[0]
    assert j.status == "failed"
    assert j.last_error == "boom"
    assert j.attempts == 2  # incremented twice


def test_progress_counts(store):
    aid = store.create_audit("rename", "alice", {})
    store.add_jobs(aid, [
        ("patch_inbound", "a.md"),
        ("patch_inbound", "b.md"),
        ("patch_inbound", "c.md"),
    ])
    jobs = store.list_jobs(aid)
    store.update_job(jobs[0].id, status="done")
    store.update_job(jobs[1].id, status="failed", last_error="x")
    p = store.progress(aid)
    assert p["total"] == 3
    assert p["done"] == 1
    assert p["failed"] == 1
    assert p["pending"] == 1


def test_clear(store):
    aid = store.create_audit("rename", "alice", {})
    store.add_jobs(aid, [("x", "y.md")])
    store.clear()
    assert store.get_audit(aid) is None
