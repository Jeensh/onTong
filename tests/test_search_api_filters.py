"""Phase 3 — REST search endpoints accept `filters` JSON param and apply it.

We hit the logic helpers directly (no httpx server boot) to avoid FastAPI wiring.
The key behaviors:
  - `_parse_filters` rejects malformed JSON and non-dict payloads.
  - `_build_bm25_predicate` returns None when spec empty.
  - `_build_bm25_predicate` closure looks up meta_index + injects path_depth_*.
  - End-to-end: a BM25 search with filters skips docs not matching the predicate.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest


def test_parse_filters_none():
    from backend.api import search as search_api
    assert search_api._parse_filters(None) is None
    assert search_api._parse_filters("") is None


def test_parse_filters_empty_dict_returns_none():
    from backend.api import search as search_api
    # Empty object → no effective filter (normalize to None)
    assert search_api._parse_filters("{}") is None


def test_parse_filters_valid_dict():
    from backend.api import search as search_api
    spec = search_api._parse_filters('{"folders": ["ERP"]}')
    assert spec == {"folders": ["ERP"]}


def test_parse_filters_rejects_bad_json():
    from fastapi import HTTPException
    from backend.api import search as search_api
    with pytest.raises(HTTPException):
        search_api._parse_filters("{not json}")


def test_parse_filters_rejects_non_dict():
    from fastapi import HTTPException
    from backend.api import search as search_api
    with pytest.raises(HTTPException):
        search_api._parse_filters("[1, 2, 3]")


def test_build_bm25_predicate_none_when_spec_empty():
    from backend.api import search as search_api
    search_api._meta_index = None
    assert search_api._build_bm25_predicate(None) is None
    assert search_api._build_bm25_predicate({}) is None


def test_build_bm25_predicate_folder_match(tmp_path: Path):
    """Predicate returns True for matching folder, False otherwise."""
    from backend.application.metadata.metadata_index import MetadataIndex
    from backend.api import search as search_api

    mi = MetadataIndex(str(tmp_path))
    mi.on_file_saved(
        "ERP/x.md", domain="ERP", process="", tags=[],
        updated="2026-04-15T12:00:00Z",
        authors=["@동해"], doc_type="sop", mtime_epoch=0.0,
    )
    mi.on_file_saved(
        "MES/y.md", domain="MES", process="", tags=[],
        authors=["@재인"], doc_type="spec", mtime_epoch=0.0,
    )
    search_api._meta_index = mi

    pred = search_api._build_bm25_predicate({"folders": ["ERP"]})
    assert pred is not None

    # BM25Document is a simple namedtuple-style object with `file_path`
    class _Doc:
        def __init__(self, fp): self.file_path = fp

    assert pred(_Doc("ERP/x.md")) is True
    assert pred(_Doc("MES/y.md")) is False


def test_build_bm25_predicate_author_match(tmp_path: Path):
    from backend.application.metadata.metadata_index import MetadataIndex
    from backend.api import search as search_api

    mi = MetadataIndex(str(tmp_path))
    mi.on_file_saved(
        "ERP/a.md", domain="ERP", process="", tags=[],
        authors=["@동해"], doc_type="sop", mtime_epoch=0.0,
    )
    mi.on_file_saved(
        "ERP/b.md", domain="ERP", process="", tags=[],
        authors=["@재인"], doc_type="sop", mtime_epoch=0.0,
    )
    search_api._meta_index = mi

    pred = search_api._build_bm25_predicate({"authors": ["@동해"]})
    class _Doc:
        def __init__(self, fp): self.file_path = fp

    assert pred(_Doc("ERP/a.md")) is True
    assert pred(_Doc("ERP/b.md")) is False
