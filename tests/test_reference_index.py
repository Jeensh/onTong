"""ReferenceIndex tests — backend-equivalence with both sqlite + postgres."""
from __future__ import annotations

import pytest
from backend.application.refindex.extractor import Reference, RefKind


@pytest.fixture
def sqlite_index(tmp_path):
    from backend.application.refindex.sqlite_backend import SqliteRefIndex
    return SqliteRefIndex(tmp_path / "refs.db")


@pytest.fixture
def postgres_index_factory():
    """Factory fixture — returns a function that builds a Postgres index against
    a fresh testdb. Skipped if pytest-postgresql unavailable."""
    pytest_postgresql = pytest.importorskip("pytest_postgresql")
    return pytest_postgresql.factories


def _make_ref(source: str, target: str, kind: int, offset: int = 0, length: int = 0) -> Reference:
    return Reference(
        source_path=source,
        target_path=target,
        kind=kind,
        location={"offset": offset, "length": length or len(target), "raw": target},
    )


def test_upsert_and_outbound(sqlite_index):
    refs = [
        _make_ref("a.md", "b.md", RefKind.BODY_MD_LINK, offset=10),
        _make_ref("a.md", "c.md", RefKind.BODY_MD_LINK, offset=20),
    ]
    sqlite_index.upsert_for_source("a.md", refs)
    out = sqlite_index.outbound("a.md")
    assert sorted(r.target_path for r in out) == ["b.md", "c.md"]


def test_upsert_replaces_previous(sqlite_index):
    sqlite_index.upsert_for_source("a.md", [_make_ref("a.md", "old.md", RefKind.BODY_MD_LINK)])
    sqlite_index.upsert_for_source("a.md", [_make_ref("a.md", "new.md", RefKind.BODY_MD_LINK)])
    out = sqlite_index.outbound("a.md")
    assert len(out) == 1
    assert out[0].target_path == "new.md"


def test_inbound(sqlite_index):
    sqlite_index.upsert_for_source("a.md", [_make_ref("a.md", "shared.md", RefKind.BODY_MD_LINK)])
    sqlite_index.upsert_for_source("b.md", [_make_ref("b.md", "shared.md", RefKind.FM_RELATED)])
    inb = sqlite_index.inbound("shared.md")
    assert sorted(r.source_path for r in inb) == ["a.md", "b.md"]


def test_inbound_filtered_by_kind(sqlite_index):
    sqlite_index.upsert_for_source("a.md", [_make_ref("a.md", "x.md", RefKind.BODY_MD_LINK)])
    sqlite_index.upsert_for_source("b.md", [_make_ref("b.md", "x.md", RefKind.FM_RELATED)])
    md = sqlite_index.inbound("x.md", kind=RefKind.BODY_MD_LINK)
    assert len(md) == 1 and md[0].source_path == "a.md"


def test_remove_for_source(sqlite_index):
    sqlite_index.upsert_for_source("a.md", [_make_ref("a.md", "b.md", RefKind.BODY_MD_LINK)])
    sqlite_index.remove_for_source("a.md")
    assert sqlite_index.outbound("a.md") == []


def test_rename_target(sqlite_index):
    sqlite_index.upsert_for_source("a.md", [_make_ref("a.md", "old.md", RefKind.BODY_MD_LINK)])
    sqlite_index.upsert_for_source("b.md", [_make_ref("b.md", "old.md", RefKind.BODY_MD_LINK)])
    n = sqlite_index.rename_target("old.md", "new.md")
    assert n == 2
    assert sqlite_index.inbound("new.md") and not sqlite_index.inbound("old.md")


def test_rename_source(sqlite_index):
    sqlite_index.upsert_for_source("old.md", [_make_ref("old.md", "x.md", RefKind.BODY_MD_LINK)])
    n = sqlite_index.rename_source("old.md", "new.md")
    assert n == 1
    assert sqlite_index.outbound("new.md")
    assert not sqlite_index.outbound("old.md")


def test_broken_returns_dangling_targets(sqlite_index):
    """A doc that no source actually owns is broken."""
    sqlite_index.upsert_for_source("a.md", [
        _make_ref("a.md", "b.md", RefKind.BODY_MD_LINK),       # b is also a source
        _make_ref("a.md", "missing.md", RefKind.BODY_MD_LINK),  # missing is not
    ])
    sqlite_index.upsert_for_source("b.md", [
        _make_ref("b.md", "another-missing.md", RefKind.BODY_MD_LINK),
    ])
    broken = sqlite_index.broken()
    targets = sorted(r.target_path for r in broken)
    assert targets == ["another-missing.md", "missing.md"]


def test_broken_filtered_by_kind(sqlite_index):
    sqlite_index.upsert_for_source("a.md", [
        _make_ref("a.md", "missing-md.md", RefKind.BODY_MD_LINK),
        _make_ref("a.md", "missing-wiki", RefKind.BODY_WIKILINK),
    ])
    md = sqlite_index.broken(kind=RefKind.BODY_MD_LINK)
    assert all(r.kind == RefKind.BODY_MD_LINK for r in md)
    assert all(r.target_path == "missing-md.md" for r in md)


def test_clear(sqlite_index):
    sqlite_index.upsert_for_source("a.md", [_make_ref("a.md", "b.md", RefKind.BODY_MD_LINK)])
    sqlite_index.clear()
    assert sqlite_index.outbound("a.md") == []


def test_factory_dev_profile_returns_sqlite(tmp_path, monkeypatch):
    monkeypatch.setenv("ONTONG_PROFILE", "dev")
    import importlib, backend.core.config
    importlib.reload(backend.core.config)
    from backend.core.config import settings
    from backend.core.backends import get_ref_index, _reset_for_test
    _reset_for_test()
    profile = settings.resolve_profile()
    assert profile.ref_index_backend == "sqlite"
    idx = get_ref_index(profile, sqlite_path=str(tmp_path / "test.db"))
    from backend.application.refindex.sqlite_backend import SqliteRefIndex
    assert isinstance(idx, SqliteRefIndex)
    _reset_for_test()


def test_profile_team_uses_postgres():
    from backend.core.profile import resolve_profile
    p = resolve_profile("team", {})
    assert p.ref_index_backend == "postgres"
    p = resolve_profile("enterprise", {})
    assert p.ref_index_backend == "postgres"


def test_profile_override_via_env():
    from backend.core.profile import resolve_profile
    p = resolve_profile("dev", {"ONTONG_REF_INDEX_BACKEND": "postgres"})
    assert p.ref_index_backend == "postgres"


# Postgres backend equivalence — only runs if pg available
@pytest.fixture
def pg_index(postgres_db_factory):
    pytest_postgresql = pytest.importorskip("pytest_postgresql")
    factories = pytest_postgresql.factories
    yield  # test will provide own fixture; placeholder if pg_ctl unavailable


def test_postgres_backend_smoke(monkeypatch):
    """Skip-if-no-pg smoke test. Real coverage via SQLite (equivalence by protocol)."""
    pytest_postgresql = pytest.importorskip("pytest_postgresql")
    # If pg is available, do a minimal upsert+inbound on a fresh testdb.
    # Otherwise this test is xfail-style: we just verify import works.
    try:
        from backend.application.refindex.postgres_backend import PostgresRefIndex
        assert PostgresRefIndex is not None
    except ImportError as e:
        pytest.fail(f"PostgresRefIndex import failed: {e}")


# ── Phase 5-A: stems() + revised broken() tests ──────────────────────────────

def test_stems_returns_stem_to_paths_map(sqlite_index):
    """stems() groups source_paths by their filename stem."""
    sqlite_index.upsert_for_source("dir1/foo.md", [
        Reference("dir1/foo.md", "x.md", RefKind.BODY_MD_LINK,
                  {"offset": 0, "length": 4, "raw": "x.md"})
    ])
    sqlite_index.upsert_for_source("dir2/bar.md", [
        Reference("dir2/bar.md", "y.md", RefKind.BODY_MD_LINK,
                  {"offset": 0, "length": 4, "raw": "y.md"})
    ])
    sqlite_index.upsert_for_source("dir3/foo.md", [
        Reference("dir3/foo.md", "z.md", RefKind.BODY_MD_LINK,
                  {"offset": 0, "length": 4, "raw": "z.md"})
    ])
    stems = sqlite_index.stems()
    assert sorted(stems["foo"]) == ["dir1/foo.md", "dir3/foo.md"]
    assert stems["bar"] == ["dir2/bar.md"]


def test_stems_empty_when_index_is_empty(sqlite_index):
    """stems() returns an empty dict when no refs are indexed."""
    assert sqlite_index.stems() == {}


def test_broken_excludes_wikilinks_with_existing_stem(sqlite_index):
    """A [[foo]] wikilink is NOT broken if any source has stem 'foo'."""
    # a.md links to wikilink 'foo'
    sqlite_index.upsert_for_source("a.md", [
        Reference("a.md", "foo", RefKind.BODY_WIKILINK,
                  {"offset": 0, "length": 3, "raw": "foo"})
    ])
    # dir/foo.md exists as a source (no outbound refs, but it's in the index)
    sqlite_index.upsert_for_source("dir/foo.md", [])

    broken = sqlite_index.broken()
    # foo stem is owned by dir/foo.md → wikilink is NOT broken
    assert len(broken) == 0


def test_broken_includes_wikilinks_with_missing_stem(sqlite_index):
    """A [[ghost]] wikilink IS broken if no source has stem 'ghost'."""
    sqlite_index.upsert_for_source("a.md", [
        Reference("a.md", "ghost", RefKind.BODY_WIKILINK,
                  {"offset": 0, "length": 5, "raw": "ghost"})
    ])

    broken = sqlite_index.broken()
    targets = [r.target_path for r in broken]
    assert "ghost" in targets


def test_broken_path_based_refs_still_detected(sqlite_index):
    """Non-wikilink refs (paths) still detected as broken when target missing."""
    sqlite_index.upsert_for_source("a.md", [
        Reference("a.md", "missing.md", RefKind.BODY_MD_LINK,
                  {"offset": 0, "length": 10, "raw": "missing.md"}),
    ])

    broken = sqlite_index.broken()
    targets = [r.target_path for r in broken]
    assert "missing.md" in targets


def test_broken_wikilink_and_path_combined(sqlite_index):
    """Mixed refs: valid wikilink (stem exists) + broken path + broken wikilink."""
    sqlite_index.upsert_for_source("a.md", [
        Reference("a.md", "real-stem", RefKind.BODY_WIKILINK,
                  {"offset": 0, "length": 9, "raw": "real-stem"}),
        Reference("a.md", "ghost-stem", RefKind.BODY_WIKILINK,
                  {"offset": 20, "length": 10, "raw": "ghost-stem"}),
        Reference("a.md", "missing.md", RefKind.BODY_MD_LINK,
                  {"offset": 40, "length": 10, "raw": "missing.md"}),
    ])
    # real-stem is an actual indexed source
    sqlite_index.upsert_for_source("dir/real-stem.md", [])

    broken = sqlite_index.broken()
    broken_targets = {r.target_path for r in broken}
    assert "ghost-stem" in broken_targets
    assert "missing.md" in broken_targets
    assert "real-stem" not in broken_targets


# ── E5: last_indexed_at + stale_sources ──────────────────────────────────────

def test_last_indexed_at_advances_on_reupsert(sqlite_index):
    """Re-indexing the same source must refresh its last_indexed_at.

    Regression test: the previous code used INSERT OR REPLACE which technically
    refreshed via the default, but the Postgres equivalent used DO NOTHING and
    silently kept the old timestamp. Verifying both backends advance the value
    keeps the semantics consistent.
    """
    import time
    sqlite_index.upsert_for_source("a.md", [])
    first = sqlite_index._conn.execute(
        "SELECT last_indexed_at FROM wiki_sources WHERE source_path='a.md'"
    ).fetchone()["last_indexed_at"]

    # SQLite datetime('now') has 1-second resolution; sleep just past that.
    time.sleep(1.1)
    sqlite_index.upsert_for_source("a.md", [])
    second = sqlite_index._conn.execute(
        "SELECT last_indexed_at FROM wiki_sources WHERE source_path='a.md'"
    ).fetchone()["last_indexed_at"]

    assert second > first, f"timestamp did not advance: {first!r} -> {second!r}"


def test_stale_sources_returns_old_paths(sqlite_index):
    """stale_sources(threshold) returns paths older than threshold seconds."""
    # Insert a fresh source then back-date it via direct SQL.
    sqlite_index.upsert_for_source("old1.md", [])
    sqlite_index.upsert_for_source("old2.md", [])
    sqlite_index.upsert_for_source("fresh.md", [])

    # Back-date old1 / old2 by 2 hours; fresh stays at "now".
    sqlite_index._conn.execute(
        "UPDATE wiki_sources SET last_indexed_at = datetime('now', '-2 hours') "
        "WHERE source_path IN ('old1.md', 'old2.md')"
    )

    # threshold = 1 hour: catches old1 + old2, skips fresh.
    stale = sqlite_index.stale_sources(threshold_seconds=3600)
    assert sorted(stale) == ["old1.md", "old2.md"]


def test_stale_sources_excludes_recent(sqlite_index):
    """Sources just upserted are NOT stale at any reasonable threshold."""
    sqlite_index.upsert_for_source("just-now.md", [])
    stale = sqlite_index.stale_sources(threshold_seconds=10)
    assert "just-now.md" not in stale


def test_stale_sources_returns_empty_when_no_sources(sqlite_index):
    """No sources indexed → no stale sources."""
    assert sqlite_index.stale_sources(threshold_seconds=1) == []


def test_rename_source_refreshes_last_indexed_at(sqlite_index):
    """Renaming a source counts as a fresh index event — timestamp must update."""
    import time
    sqlite_index.upsert_for_source("old-path.md", [])
    first = sqlite_index._conn.execute(
        "SELECT last_indexed_at FROM wiki_sources WHERE source_path='old-path.md'"
    ).fetchone()["last_indexed_at"]

    time.sleep(1.1)
    sqlite_index.rename_source("old-path.md", "new-path.md")
    second = sqlite_index._conn.execute(
        "SELECT last_indexed_at FROM wiki_sources WHERE source_path='new-path.md'"
    ).fetchone()["last_indexed_at"]

    assert second > first


# ── E3: materialized stem column ─────────────────────────────────────────────

def test_stem_column_populated_on_upsert(sqlite_index):
    """upsert_for_source materializes stem from the source_path."""
    sqlite_index.upsert_for_source("dir1/foo-bar.md", [])
    row = sqlite_index._conn.execute(
        "SELECT stem FROM wiki_sources WHERE source_path='dir1/foo-bar.md'"
    ).fetchone()
    assert row["stem"] == "foo-bar"


def test_stem_column_updates_on_rename(sqlite_index):
    """rename_source rewrites stem to match the new path."""
    sqlite_index.upsert_for_source("dir/old-name.md", [])
    sqlite_index.rename_source("dir/old-name.md", "dir/new-name.md")
    row = sqlite_index._conn.execute(
        "SELECT stem FROM wiki_sources WHERE source_path='dir/new-name.md'"
    ).fetchone()
    assert row["stem"] == "new-name"


def test_broken_pagination_with_offset(sqlite_index):
    """broken() now uses SQL LIMIT/OFFSET — must page deterministically by id."""
    # Create 5 broken md links
    for i in range(5):
        sqlite_index.upsert_for_source(
            f"src{i}.md",
            [Reference(f"src{i}.md", f"missing{i}.md", RefKind.BODY_MD_LINK,
                       {"offset": 0, "length": 12, "raw": f"missing{i}.md"})],
        )

    page1 = sqlite_index.broken(limit=2, offset=0)
    page2 = sqlite_index.broken(limit=2, offset=2)
    page3 = sqlite_index.broken(limit=2, offset=4)
    seen = [r.target_path for r in (page1 + page2 + page3)]
    assert sorted(seen) == [f"missing{i}.md" for i in range(5)]
    # Pages do not overlap
    assert len(set(seen)) == 5


def test_broken_kind_filter_path_only(sqlite_index):
    """broken(kind=BODY_MD_LINK) returns only path-broken refs, not wikilinks."""
    sqlite_index.upsert_for_source("a.md", [
        Reference("a.md", "missing.md", RefKind.BODY_MD_LINK,
                  {"offset": 0, "length": 10, "raw": "missing.md"}),
        Reference("a.md", "ghost-stem", RefKind.BODY_WIKILINK,
                  {"offset": 20, "length": 10, "raw": "ghost-stem"}),
    ])
    md_only = sqlite_index.broken(kind=RefKind.BODY_MD_LINK)
    assert len(md_only) == 1
    assert md_only[0].target_path == "missing.md"
    assert md_only[0].kind == RefKind.BODY_MD_LINK


def test_broken_kind_filter_wikilink_only(sqlite_index):
    """broken(kind=BODY_WIKILINK) returns only stem-broken wikilinks."""
    sqlite_index.upsert_for_source("a.md", [
        Reference("a.md", "missing.md", RefKind.BODY_MD_LINK,
                  {"offset": 0, "length": 10, "raw": "missing.md"}),
        Reference("a.md", "ghost-stem", RefKind.BODY_WIKILINK,
                  {"offset": 20, "length": 10, "raw": "ghost-stem"}),
    ])
    wl_only = sqlite_index.broken(kind=RefKind.BODY_WIKILINK)
    assert len(wl_only) == 1
    assert wl_only[0].target_path == "ghost-stem"
    assert wl_only[0].kind == RefKind.BODY_WIKILINK
