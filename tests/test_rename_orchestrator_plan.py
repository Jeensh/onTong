"""RenameOrchestrator.plan() — impact analysis without side effects."""
from __future__ import annotations
import asyncio
import pytest


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
    from backend.application.refindex.extractor import Reference, RefKind
    from backend.application.rename.sqlite_audit import SqliteAuditStore
    from backend.application.rename.orchestrator import RenameOrchestrator

    ref_index = SqliteRefIndex(str(tmp_path / "refs.db"))
    audit = SqliteAuditStore(str(tmp_path / "audit.db"))

    # Seed: target.md has 3 inbound refs from 2 sources
    ref_index.upsert_for_source("a.md", [
        Reference("a.md", "target.md", RefKind.BODY_MD_LINK, {"offset": 10, "length": 9, "raw": "target.md"}),
        Reference("a.md", "target.md", RefKind.FM_RELATED,    {"offset": 30, "length": 9, "raw": "target.md"}),
    ])
    ref_index.upsert_for_source("b.md", [
        Reference("b.md", "target.md", RefKind.BODY_MD_LINK, {"offset": 20, "length": 9, "raw": "target.md"}),
    ])

    yield ref_index, audit
    _reset_for_test()


def test_plan_aggregates_inbound(setup):
    ref_index, audit = setup
    from backend.application.rename.orchestrator import RenameOrchestrator
    orch = RenameOrchestrator(ref_index, audit)
    plan = asyncio.get_event_loop().run_until_complete(
        orch.plan("target.md", "renamed.md", "alice")
    )
    assert plan.inbound_count == 3
    assert plan.unique_inbound_sources == 2
    assert plan.old_path == "target.md"
    assert plan.new_path == "renamed.md"
    assert sorted(it.source_path for it in plan.impact_items) == ["a.md", "b.md"]


def test_plan_records_audit_row(setup):
    ref_index, audit = setup
    from backend.application.rename.orchestrator import RenameOrchestrator
    orch = RenameOrchestrator(ref_index, audit)
    plan = asyncio.get_event_loop().run_until_complete(
        orch.plan("target.md", "renamed.md", "alice")
    )
    row = audit.get_audit(int(plan.audit_id))
    assert row is not None
    assert row.op == "rename_plan"
    assert row.actor == "alice"
    assert row.status == "success"


def test_plan_confirm_required_threshold(setup):
    ref_index, audit = setup
    # Add many more inbound refs
    from backend.application.refindex.extractor import Reference, RefKind
    for i in range(15):
        ref_index.upsert_for_source(f"src-{i}.md", [
            Reference(f"src-{i}.md", "target.md", RefKind.BODY_MD_LINK,
                      {"offset": 0, "length": 9, "raw": "target.md"}),
        ])
    from backend.application.rename.orchestrator import RenameOrchestrator
    orch = RenameOrchestrator(ref_index, audit)
    plan = asyncio.get_event_loop().run_until_complete(
        orch.plan("target.md", "renamed.md", "alice")
    )
    assert plan.confirm_required is True


def test_plan_impact_items_truncated(setup):
    """Plan returns at most MAX_IMPACT_PREVIEW (100) impact_items."""
    ref_index, audit = setup
    from backend.application.refindex.extractor import Reference, RefKind
    for i in range(150):
        ref_index.upsert_for_source(f"big-{i:03d}.md", [
            Reference(f"big-{i:03d}.md", "target.md", RefKind.BODY_MD_LINK,
                      {"offset": 0, "length": 9, "raw": "target.md"}),
        ])
    from backend.application.rename.orchestrator import RenameOrchestrator
    orch = RenameOrchestrator(ref_index, audit)
    plan = asyncio.get_event_loop().run_until_complete(
        orch.plan("target.md", "renamed.md", "alice")
    )
    # 150 + the 2 originals = 152 unique sources
    assert plan.unique_inbound_sources == 152
    # impact_items capped to 100
    assert len(plan.impact_items) == 100


def test_plan_uses_stem_inbound_for_wikilinks(setup):
    """Wikilinks reference target by stem, not full path."""
    ref_index, audit = setup
    from backend.application.refindex.extractor import Reference, RefKind
    # A wikilink ref pointing to "target" (stem of target.md)
    ref_index.upsert_for_source("c.md", [
        Reference("c.md", "target", RefKind.BODY_WIKILINK, {"offset": 5, "length": 6, "raw": "target"}),
    ])
    from backend.application.rename.orchestrator import RenameOrchestrator
    orch = RenameOrchestrator(ref_index, audit)
    plan = asyncio.get_event_loop().run_until_complete(
        orch.plan("target.md", "renamed.md", "alice")
    )
    # Should also pick up c.md via stem matching
    sources = sorted(it.source_path for it in plan.impact_items)
    assert "c.md" in sources
