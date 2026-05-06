"""Phase 2 — WikiIndexer writes authors[], doc_type, mtime_epoch into ChromaDB metadata.

Also verifies MetadataIndex stores the same fields natively so the BM25 post-filter
via meta_index.get_file_entry() works for FilterSpec queries.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _make_wiki_file(path: str, **meta_kwargs):
    from backend.core.schemas import WikiFile, DocumentMetadata
    meta = DocumentMetadata(**meta_kwargs)
    return WikiFile(
        path=path, title=path.rsplit("/", 1)[-1].removesuffix(".md"),
        content="body", raw_content="", metadata=meta, links=[],
    )


# ── compute_effective_authors ─────────────────────────────────────

def test_authors_explicit_list_preserved():
    from backend.application.wiki.wiki_indexer import compute_effective_authors
    from backend.core.schemas import DocumentMetadata
    m = DocumentMetadata(authors=["@동해", "@재인"], created_by="@민수")
    # Explicit authors win; created_by is ignored
    assert compute_effective_authors(m) == ["@동해", "@재인"]


def test_authors_fallback_to_created_updated_by():
    from backend.application.wiki.wiki_indexer import compute_effective_authors
    from backend.core.schemas import DocumentMetadata
    m = DocumentMetadata(created_by="@동해", updated_by="@재인")
    assert compute_effective_authors(m) == ["@동해", "@재인"]


def test_authors_fallback_dedupes():
    from backend.application.wiki.wiki_indexer import compute_effective_authors
    from backend.core.schemas import DocumentMetadata
    m = DocumentMetadata(created_by="@동해", updated_by="@동해")
    assert compute_effective_authors(m) == ["@동해"]


def test_authors_fallback_filters_empty():
    from backend.application.wiki.wiki_indexer import compute_effective_authors
    from backend.core.schemas import DocumentMetadata
    m = DocumentMetadata(created_by="", updated_by="@재인")
    assert compute_effective_authors(m) == ["@재인"]


# ── compute_mtime_epoch ───────────────────────────────────────────

def test_mtime_epoch_from_updated_iso():
    from backend.application.wiki.wiki_indexer import compute_mtime_epoch
    from backend.core.schemas import DocumentMetadata
    expected = datetime(2026, 4, 15, 12, 0, tzinfo=timezone.utc).timestamp()
    m = DocumentMetadata(updated="2026-04-15T12:00:00Z")
    assert compute_mtime_epoch(m) == expected


def test_mtime_epoch_fallback_to_created():
    from backend.application.wiki.wiki_indexer import compute_mtime_epoch
    from backend.core.schemas import DocumentMetadata
    expected = datetime(2026, 1, 1, tzinfo=timezone.utc).timestamp()
    m = DocumentMetadata(created="2026-01-01", updated="")
    assert compute_mtime_epoch(m) == expected


def test_mtime_epoch_zero_when_missing():
    from backend.application.wiki.wiki_indexer import compute_mtime_epoch
    from backend.core.schemas import DocumentMetadata
    assert compute_mtime_epoch(DocumentMetadata()) == 0.0


# ── _metadata_to_chroma output ────────────────────────────────────

def test_chroma_metadata_includes_new_fields():
    from backend.application.wiki.wiki_indexer import WikiIndexer
    wf = _make_wiki_file(
        "ERP/마스터데이터-관리-지침.md",
        doc_type="sop",
        authors=["@동해"],
        updated="2026-04-15T12:00:00Z",
        tags=["재고", "관리"],
        status="active",
    )
    meta = WikiIndexer._metadata_to_chroma(wf)
    assert meta["doc_type"] == "sop"
    assert meta["authors"] == "|@동해|"  # pipe-delimited for Chroma $contains
    assert meta["status"] == "active"
    expected_mt = datetime(2026, 4, 15, 12, 0, tzinfo=timezone.utc).timestamp()
    assert meta["mtime_epoch"] == expected_mt
    assert meta["path_depth_1"] == "ERP"
    assert meta["path_stem"] == "마스터데이터 관리 지침"


def test_chroma_metadata_authors_from_fallback():
    from backend.application.wiki.wiki_indexer import WikiIndexer
    wf = _make_wiki_file(
        "ERP/x.md",
        created_by="@동해", updated_by="@재인",
    )
    meta = WikiIndexer._metadata_to_chroma(wf)
    # Pipe-delimited: "|@동해|@재인|"
    assert meta["authors"].count("@동해") == 1
    assert meta["authors"].count("@재인") == 1


# ── MetadataIndex stores native types ─────────────────────────────

def test_meta_index_records_new_fields(tmp_path: Path):
    from backend.application.metadata.metadata_index import MetadataIndex
    mi = MetadataIndex(str(tmp_path))
    mi.on_file_saved(
        "ERP/x.md", domain="ERP", process="", tags=["재고"],
        updated="2026-04-15T12:00:00Z",
        created_by="@동해", updated_by="@재인",
        authors=["@동해", "@재인"],
        doc_type="sop",
        mtime_epoch=123456.0,
    )
    entry = mi.get_file_entry("ERP/x.md")
    assert entry is not None
    assert entry["authors"] == ["@동해", "@재인"]
    assert entry["doc_type"] == "sop"
    assert entry["mtime_epoch"] == 123456.0


def test_meta_index_rebuild_extended():
    """Rebuild with extended dicts populates authors/doc_type/mtime_epoch per file."""
    import tempfile
    from backend.application.metadata.metadata_index import MetadataIndex
    with tempfile.TemporaryDirectory() as td:
        mi = MetadataIndex(td)
        mi.rebuild(extended=[
            {
                "path": "ERP/a.md", "domain": "ERP", "process": "", "tags": ["재고"],
                "authors": ["@동해"], "doc_type": "sop", "mtime_epoch": 1000.0,
            },
            {
                "path": "MES/b.md", "domain": "MES", "process": "", "tags": [],
                "authors": ["@재인"], "doc_type": "spec", "mtime_epoch": 2000.0,
            },
        ])
        a = mi.get_file_entry("ERP/a.md")
        b = mi.get_file_entry("MES/b.md")
        assert a["authors"] == ["@동해"] and a["doc_type"] == "sop" and a["mtime_epoch"] == 1000.0
        assert b["authors"] == ["@재인"] and b["doc_type"] == "spec" and b["mtime_epoch"] == 2000.0


# ── Integration: filter_compiler predicate against a meta_index entry ─────

def test_filter_predicate_matches_meta_index_entry(tmp_path: Path):
    """FilterSpec → predicate → evaluates against a meta_index entry (+ injected path_depth_*)."""
    from backend.application.metadata.metadata_index import MetadataIndex
    from backend.application.agent.filter_compiler import compile_to_bm25_predicate
    from backend.application.wiki.wiki_indexer import _extract_path_depths

    mi = MetadataIndex(str(tmp_path))
    mi.on_file_saved(
        "ERP/마스터.md", domain="ERP", process="", tags=["재고", "관리"],
        updated="2026-04-15T12:00:00Z",
        authors=["@동해"],
        doc_type="sop",
        mtime_epoch=datetime(2026, 4, 15, 12, 0, tzinfo=timezone.utc).timestamp(),
    )
    entry = dict(mi.get_file_entry("ERP/마스터.md"))
    entry.update(_extract_path_depths("ERP/마스터.md"))

    pred = compile_to_bm25_predicate({
        "folders": ["ERP"],
        "authors": ["@동해"],
        "tags": {"include": ["재고"]},
        "types": ["sop"],
        "mtime_from": "2026-01-01",
    })
    assert pred(entry) is True

    # Negative: different author
    pred_neg = compile_to_bm25_predicate({"authors": ["@민수"]})
    assert pred_neg(entry) is False
