"""Tests for filter DSL parser (Boolean filter expressions → Chroma where).

Supports:
- atoms: field:value (field ∈ {path, folder, tag, author, type, mtime, status, acl})
- Boolean: AND, OR, NOT/!
- Parentheses for grouping
- Quoted values with spaces
- mtime operators: >, <, >=, <=
"""

from __future__ import annotations

import pytest

from backend.application.agent.filter_dsl import parse_dsl, DSLError


class TestAtom:
    def test_folder(self):
        assert parse_dsl("folder:ERP") == {"path_depth_1": "ERP"}

    def test_tag(self):
        assert parse_dsl("tag:재고") == {"tags": {"$in": ["재고"]}}

    def test_author(self):
        assert parse_dsl("author:@동해") == {"authors": {"$in": ["@동해"]}}

    def test_type(self):
        assert parse_dsl("type:sop") == {"doc_type": "sop"}

    def test_status(self):
        assert parse_dsl("status:active") == {"status": "active"}

    def test_acl(self):
        assert parse_dsl("acl:public") == {"acl_read": {"$in": ["public"]}}


class TestMtime:
    def test_mtime_gte(self):
        result = parse_dsl("mtime:>=2026-01-01")
        assert "mtime_epoch" in result
        assert "$gte" in result["mtime_epoch"]

    def test_mtime_lt(self):
        result = parse_dsl("mtime:<2026-04-01")
        assert "$lt" in result["mtime_epoch"]

    def test_mtime_gt(self):
        result = parse_dsl("mtime:>2026-01-01")
        assert "$gt" in result["mtime_epoch"]


class TestQuotedValue:
    def test_double_quoted(self):
        assert parse_dsl('tag:"재고 관리"') == {"tags": {"$in": ["재고 관리"]}}

    def test_single_quoted(self):
        assert parse_dsl("tag:'재고 관리'") == {"tags": {"$in": ["재고 관리"]}}


class TestAndOr:
    def test_explicit_and(self):
        result = parse_dsl("folder:ERP AND author:@동해")
        assert result == {"$and": [
            {"path_depth_1": "ERP"},
            {"authors": {"$in": ["@동해"]}},
        ]}

    def test_implicit_and(self):
        """Space-separated atoms default to AND."""
        result = parse_dsl("folder:ERP author:@동해")
        assert result == {"$and": [
            {"path_depth_1": "ERP"},
            {"authors": {"$in": ["@동해"]}},
        ]}

    def test_or(self):
        result = parse_dsl("tag:재고 OR tag:주문")
        assert result == {"$or": [
            {"tags": {"$in": ["재고"]}},
            {"tags": {"$in": ["주문"]}},
        ]}

    def test_case_insensitive_keywords(self):
        result = parse_dsl("folder:ERP and author:@동해")
        assert "$and" in result


class TestParens:
    def test_or_inside_and(self):
        result = parse_dsl("(tag:재고 OR tag:주문) AND author:@동해")
        assert result == {"$and": [
            {"$or": [{"tags": {"$in": ["재고"]}}, {"tags": {"$in": ["주문"]}}]},
            {"authors": {"$in": ["@동해"]}},
        ]}

    def test_nested_parens(self):
        result = parse_dsl("(folder:ERP AND (tag:재고 OR tag:주문))")
        assert "$and" in result


class TestNot:
    def test_not_author(self):
        result = parse_dsl("!author:@민수")
        assert result == {"authors": {"$nin": ["@민수"]}}

    def test_not_tag(self):
        result = parse_dsl("NOT tag:draft")
        assert result == {"tags": {"$nin": ["draft"]}}

    def test_combined_with_not(self):
        result = parse_dsl("folder:ERP AND !author:@민수")
        assert result == {"$and": [
            {"path_depth_1": "ERP"},
            {"authors": {"$nin": ["@민수"]}},
        ]}


class TestErrors:
    def test_unmatched_paren_raises(self):
        with pytest.raises(DSLError):
            parse_dsl("(folder:ERP")

    def test_unknown_field_raises(self):
        with pytest.raises(DSLError):
            parse_dsl("unknown:value")

    def test_empty_returns_empty(self):
        assert parse_dsl("") == {}
        assert parse_dsl("   ") == {}


class TestRoundtripWithCompiler:
    """DSL → where, then used by compiler as boolean field."""

    def test_boolean_in_spec(self):
        from backend.application.agent.filter_compiler import compile_to_chroma_where
        where = compile_to_chroma_where({
            "boolean": "(tag:재고 OR tag:주문) AND author:@동해"
        })
        assert "$and" in where
