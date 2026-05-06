"""Tests for NL (natural language) filter extractor — converts user queries
into FilterSpec dicts so the agent can pre-filter wiki_search results.

Smart TDD — written before the implementation (per CLAUDE.md).
"""
from __future__ import annotations

from datetime import date

import pytest

from backend.application.agent.nl_filter_extractor import (
    extract_filter_spec,
    _extract_authors,
    _extract_folders,
    _extract_mtime,
    _extract_types,
)


# ── Authors ────────────────────────────────────────────────────

def test_extract_authors_single():
    assert _extract_authors("@동해가 쓴 문서") == ["@동해"]


def test_extract_authors_multiple():
    out = _extract_authors("@동해 @재인 협업")
    assert set(out) == {"@동해", "@재인"}


def test_extract_authors_none():
    assert _extract_authors("재고 관리 지침") == []


# ── Folders ────────────────────────────────────────────────────

def test_extract_folders_explicit_keyword():
    # Known domain folders: ERP, MES, SCM, 공정, 설비, 이슈, 제품, 표준, 인프라, 기획, 재무, 인사
    assert "ERP" in _extract_folders("ERP 폴더에서 찾아줘")


def test_extract_folders_korean_folder_name():
    # Korean folder names in the wiki
    assert "제품" in _extract_folders("제품 문서 중에")


def test_extract_folders_multiple():
    out = _extract_folders("공정 또는 설비 관련")
    assert set(out) >= {"공정", "설비"}


def test_extract_folders_none():
    assert _extract_folders("재고 관리") == []


# ── Types ──────────────────────────────────────────────────────

def test_extract_types_sop():
    assert "sop" in _extract_types("SOP 문서만 보여줘")


def test_extract_types_spec():
    assert "spec" in _extract_types("사양서 (spec) 문서들")


def test_extract_types_incident():
    assert "incident" in _extract_types("인시던트 포스트모템")


def test_extract_types_none():
    assert _extract_types("재고 관리") == []


# ── mtime ─────────────────────────────────────────────────────

def test_extract_mtime_recent_30_days():
    out = _extract_mtime("최근 30일 동안의 문서", today=date(2026, 4, 17))
    assert out["mtime_from"] == "2026-03-18"
    assert "mtime_to" not in out or out["mtime_to"] is None


def test_extract_mtime_recent_7_days():
    out = _extract_mtime("최근 7일", today=date(2026, 4, 17))
    assert out["mtime_from"] == "2026-04-10"


def test_extract_mtime_last_month():
    out = _extract_mtime("지난 달", today=date(2026, 4, 17))
    # March 2026: 03-01 ~ 03-31
    assert out["mtime_from"] == "2026-03-01"
    assert out["mtime_to"] == "2026-03-31"


def test_extract_mtime_this_month():
    out = _extract_mtime("이번 달", today=date(2026, 4, 17))
    assert out["mtime_from"] == "2026-04-01"


def test_extract_mtime_year_month():
    out = _extract_mtime("2026년 3월 이후", today=date(2026, 4, 17))
    assert out["mtime_from"] == "2026-03-01"


def test_extract_mtime_no_match():
    assert _extract_mtime("재고 관리 지침", today=date(2026, 4, 17)) == {}


# ── End-to-end ────────────────────────────────────────────────

def test_extract_filter_spec_combined():
    spec = extract_filter_spec(
        "ERP 폴더에서 @동해가 지난 달 쓴 SOP 문서",
        today=date(2026, 4, 17),
    )
    assert spec["folders"] == ["ERP"]
    assert spec["authors"] == ["@동해"]
    assert "sop" in spec["types"]
    assert spec["mtime_from"] == "2026-03-01"
    assert spec["mtime_to"] == "2026-03-31"


def test_extract_filter_spec_empty():
    spec = extract_filter_spec("재고 관리", today=date(2026, 4, 17))
    assert spec == {}


def test_extract_filter_spec_returns_dict():
    spec = extract_filter_spec("", today=date(2026, 4, 17))
    assert spec == {}
