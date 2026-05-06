"""Tests for FilterSpec → Chroma where / BM25 predicate compiler.

Covers:
- Single-field filters (path, folders, tags, authors, types, mtime, status, acl)
- Boolean combinations via Chroma $and/$or
- BM25 predicate evaluation on metadata dicts
- Edge cases (empty spec, invalid dates)
"""

from __future__ import annotations

import pytest

from backend.application.agent.filter_compiler import (
    compile_to_chroma_where,
    compile_to_bm25_predicate,
)


class TestEmptyAndInvalid:
    def test_empty_spec_returns_none(self):
        assert compile_to_chroma_where(None) is None
        assert compile_to_chroma_where({}) is None

    def test_empty_predicate_returns_none(self):
        assert compile_to_bm25_predicate(None) is None
        assert compile_to_bm25_predicate({}) is None


class TestPathFilter:
    def test_single_depth(self):
        where = compile_to_chroma_where({"path": "wiki/ERP/**"})
        assert where == {"path_depth_1": "ERP"}

    def test_two_depths(self):
        where = compile_to_chroma_where({"path": "wiki/ERP/마스터데이터"})
        assert where == {"$and": [
            {"path_depth_1": "ERP"},
            {"path_depth_2": "마스터데이터"},
        ]}

    def test_no_wiki_prefix(self):
        where = compile_to_chroma_where({"path": "ERP/**"})
        assert where == {"path_depth_1": "ERP"}


class TestFoldersFilter:
    def test_single_folder(self):
        where = compile_to_chroma_where({"folders": ["ERP"]})
        assert where == {"path_depth_1": "ERP"}

    def test_multiple_folders(self):
        where = compile_to_chroma_where({"folders": ["ERP", "MES"]})
        assert where == {"$or": [
            {"path_depth_1": "ERP"},
            {"path_depth_1": "MES"},
        ]}

    def test_nested_folder(self):
        where = compile_to_chroma_where({"folders": ["ERP/마스터데이터"]})
        assert where == {"$and": [
            {"path_depth_1": "ERP"},
            {"path_depth_2": "마스터데이터"},
        ]}

    def test_multiple_nested_folders(self):
        where = compile_to_chroma_where({"folders": ["ERP/마스터데이터", "MES"]})
        assert where == {"$or": [
            {"$and": [{"path_depth_1": "ERP"}, {"path_depth_2": "마스터데이터"}]},
            {"path_depth_1": "MES"},
        ]}


class TestTagsFilter:
    def test_include_or_mode(self):
        where = compile_to_chroma_where({"tags": {"include": ["재고", "주문"], "mode": "OR"}})
        assert where == {"tags": {"$in": ["재고", "주문"]}}

    def test_include_and_mode(self):
        where = compile_to_chroma_where({"tags": {"include": ["재고", "주문"], "mode": "AND"}})
        assert where == {"$and": [
            {"tags": {"$in": ["재고"]}},
            {"tags": {"$in": ["주문"]}},
        ]}

    def test_exclude(self):
        where = compile_to_chroma_where({"tags": {"exclude": ["draft"]}})
        assert where == {"tags": {"$nin": ["draft"]}}

    def test_include_and_exclude(self):
        where = compile_to_chroma_where({
            "tags": {"include": ["재고"], "exclude": ["draft"]}
        })
        assert where == {"$and": [
            {"tags": {"$in": ["재고"]}},
            {"tags": {"$nin": ["draft"]}},
        ]}


class TestAuthorsFilter:
    def test_single_author(self):
        where = compile_to_chroma_where({"authors": ["@동해"]})
        assert where == {"authors": {"$in": ["@동해"]}}

    def test_multiple_authors(self):
        where = compile_to_chroma_where({"authors": ["@동해", "@재인"]})
        assert where == {"authors": {"$in": ["@동해", "@재인"]}}


class TestTypesFilter:
    def test_single_type(self):
        where = compile_to_chroma_where({"types": ["sop"]})
        assert where == {"doc_type": "sop"}

    def test_multiple_types(self):
        where = compile_to_chroma_where({"types": ["sop", "spec"]})
        assert where == {"doc_type": {"$in": ["sop", "spec"]}}


class TestMtimeFilter:
    def test_mtime_from(self):
        where = compile_to_chroma_where({"mtime_from": "2026-01-01"})
        assert "mtime_epoch" in where
        assert "$gte" in where["mtime_epoch"]
        assert where["mtime_epoch"]["$gte"] > 0

    def test_mtime_to(self):
        where = compile_to_chroma_where({"mtime_to": "2026-04-01"})
        assert where["mtime_epoch"]["$lte"] > 0

    def test_mtime_range(self):
        where = compile_to_chroma_where({
            "mtime_from": "2026-01-01",
            "mtime_to": "2026-04-01",
        })
        assert "$and" in where
        conds = where["$and"]
        assert any("$gte" in c.get("mtime_epoch", {}) for c in conds)
        assert any("$lte" in c.get("mtime_epoch", {}) for c in conds)

    def test_invalid_date_raises(self):
        with pytest.raises(ValueError):
            compile_to_chroma_where({"mtime_from": "not-a-date"})


class TestStatusFilter:
    def test_single_status(self):
        where = compile_to_chroma_where({"statuses": ["active"]})
        assert where == {"status": "active"}

    def test_multiple_statuses(self):
        where = compile_to_chroma_where({"statuses": ["active", "review"]})
        assert where == {"status": {"$in": ["active", "review"]}}


class TestACLFilter:
    def test_single_acl(self):
        where = compile_to_chroma_where({"acl": ["public"]})
        assert where == {"acl_read": {"$in": ["public"]}}

    def test_multiple_acl(self):
        where = compile_to_chroma_where({"acl": ["public", "team:mes"]})
        assert where == {"acl_read": {"$in": ["public", "team:mes"]}}


class TestCombinedFilters:
    def test_folders_plus_authors(self):
        where = compile_to_chroma_where({
            "folders": ["ERP"],
            "authors": ["@동해"],
        })
        assert where == {"$and": [
            {"path_depth_1": "ERP"},
            {"authors": {"$in": ["@동해"]}},
        ]}

    def test_all_fields(self):
        where = compile_to_chroma_where({
            "folders": ["ERP"],
            "tags": {"include": ["재고"]},
            "authors": ["@동해"],
            "types": ["sop"],
            "statuses": ["active"],
            "mtime_from": "2026-01-01",
        })
        assert "$and" in where
        assert len(where["$and"]) == 6


class TestBM25Predicate:
    def test_folder_match(self):
        pred = compile_to_bm25_predicate({"folders": ["ERP"]})
        assert pred({"path_depth_1": "ERP"}) is True
        assert pred({"path_depth_1": "MES"}) is False

    def test_tag_include(self):
        pred = compile_to_bm25_predicate({"tags": {"include": ["재고"]}})
        assert pred({"tags": ["재고", "관리"]}) is True
        assert pred({"tags": ["관리"]}) is False

    def test_tag_and_mode(self):
        pred = compile_to_bm25_predicate({
            "tags": {"include": ["재고", "주문"], "mode": "AND"}
        })
        assert pred({"tags": ["재고", "주문"]}) is True
        assert pred({"tags": ["재고"]}) is False

    def test_tag_exclude(self):
        pred = compile_to_bm25_predicate({"tags": {"exclude": ["draft"]}})
        assert pred({"tags": ["재고"]}) is True
        assert pred({"tags": ["draft"]}) is False

    def test_author_in(self):
        pred = compile_to_bm25_predicate({"authors": ["@동해"]})
        assert pred({"authors": ["@동해", "@재인"]}) is True
        assert pred({"authors": ["@민수"]}) is False
        assert pred({"authors": []}) is False

    def test_mtime_range(self):
        pred = compile_to_bm25_predicate({
            "mtime_from": "2026-01-01",
            "mtime_to": "2026-04-01",
        })
        # 2026-02-15
        import datetime
        mid = datetime.datetime(2026, 2, 15, tzinfo=datetime.timezone.utc).timestamp()
        before = datetime.datetime(2025, 12, 1, tzinfo=datetime.timezone.utc).timestamp()
        after = datetime.datetime(2026, 5, 1, tzinfo=datetime.timezone.utc).timestamp()
        assert pred({"mtime_epoch": mid}) is True
        assert pred({"mtime_epoch": before}) is False
        assert pred({"mtime_epoch": after}) is False

    def test_combined(self):
        pred = compile_to_bm25_predicate({
            "folders": ["ERP"],
            "authors": ["@동해"],
        })
        assert pred({"path_depth_1": "ERP", "authors": ["@동해"]}) is True
        assert pred({"path_depth_1": "ERP", "authors": ["@민수"]}) is False
        assert pred({"path_depth_1": "MES", "authors": ["@동해"]}) is False


class TestBooleanDSLDelegation:
    """When 'boolean' field is present, delegate to DSL parser."""

    def test_boolean_dsl_parsed(self):
        where = compile_to_chroma_where({"boolean": "folder:ERP AND author:@동해"})
        # should produce $and of two clauses
        assert "$and" in where
