"""agent_tools — graph query integration tests.

Exercises the read-only Code / Ontology / Mapping tools against the live
SQLite DB seeded by `slab-design-real`. Skipped when that repo is not in
the DB (CI without seeded data).

These are integration tests, not unit tests — they verify the tools wire
correctly to the existing stores and return shapes the LLM can consume.
"""

from __future__ import annotations

import pytest

from backend.application.agent_tools import code_tools, mapping_tools, ontology_tools
from backend.modeling.code_layer.store import CodeLayerStore

REPO_ID = "slab-design-real"


@pytest.fixture(scope="module")
def seeded() -> bool:
    """True when the slab-design-real repo is loaded; otherwise skip."""
    types = CodeLayerStore().list_types(repo_id=REPO_ID)
    if not types:
        pytest.skip(f"repo {REPO_ID!r} not seeded — run import first")
    return True


# ── Code tools ────────────────────────────────────────────────────────


def test_code_lookup_returns_code_type(seeded: bool) -> None:
    out = code_tools.code_lookup(
        fqn="com.example.slabdesign.store.sd.std.oracle.jpo.HrSpecJpo"
    )
    assert out is not None
    assert out["kind"] == "code_type"
    assert out["simple_name"] == "HrSpecJpo"
    assert out["field_count"] >= 1
    assert out["method_count"] >= 1
    # class_kind preserved (not overwritten by wrapper kind)
    assert out["class_kind"] in ("class", "interface", "enum", "annotation", "record")


def test_code_lookup_unknown_returns_none(seeded: bool) -> None:
    assert code_tools.code_lookup(fqn="com.does.not.Exist") is None


def test_code_search_kind_filter(seeded: bool) -> None:
    types = code_tools.code_search(
        query="HrSpec", kind="code_type", repo_id=REPO_ID, limit=10
    )
    assert types
    assert all(h["kind"] == "code_type" for h in types)
    # Highest score first
    assert types[0]["score"] >= types[-1]["score"]


def test_code_search_methods(seeded: bool) -> None:
    methods = code_tools.code_search(
        query="getHrPlantCd", kind="code_method", repo_id=REPO_ID, limit=5
    )
    assert methods
    assert all(h["kind"] == "code_method" for h in methods)


def test_find_related_jpos_shares_pks(seeded: bool) -> None:
    related = code_tools.find_related_jpos(
        jpo_fqn="com.example.slabdesign.store.sd.std.oracle.jpo.HrSpecJpo",
        limit=10,
    )
    # Should find at least one sibling JPO sharing PK columns
    assert related, "expected at least one related JPO"
    for r in related:
        assert r["overlap_size"] >= 1
        assert isinstance(r["shared_pk_columns"], list)


def test_get_method_body_round_trip(seeded: bool) -> None:
    # Pick any method via search
    hits = code_tools.code_search(
        query="getHrPlantCd", kind="code_method", repo_id=REPO_ID, limit=1
    )
    assert hits
    method_fqn = hits[0]["fqn"]
    body = code_tools.get_method_body(method_fqn=method_fqn)
    assert body is not None
    assert body["fqn"] == method_fqn
    # body_text may be None for some methods, but key must exist
    assert "body_text" in body


def test_find_in_same_package(seeded: bool) -> None:
    siblings = code_tools.find_in_same_package(
        fqn="com.example.slabdesign.store.sd.std.oracle.jpo.HrSpecJpo",
        kind=None,
        limit=20,
    )
    # Should find sibling JPOs in the same package
    assert siblings
    for s in siblings:
        assert s["package"] == "com.example.slabdesign.store.sd.std.oracle.jpo"


def test_find_subclasses_handles_no_match(seeded: bool) -> None:
    # JPOs typically don't have subclasses — should return [] cleanly
    subs = code_tools.find_subclasses(
        type_fqn="com.example.slabdesign.store.sd.std.oracle.jpo.HrSpecJpo"
    )
    assert isinstance(subs, list)


# ── Ontology tools ────────────────────────────────────────────────────


def test_domain_search_returns_terms(seeded: bool) -> None:
    out = ontology_tools.domain_search(
        query="주문", repo_id=REPO_ID, kind="term", limit=10
    )
    # 29 BusinessTerms loaded from recommend bulk, "주문" should match
    assert out, "expected at least one term match for 주문"
    assert all(h["match_kind"] == "term" for h in out)


def test_domain_search_empty_query() -> None:
    assert ontology_tools.domain_search(query="", repo_id=REPO_ID) == []


def test_term_lookup_unknown_returns_none(seeded: bool) -> None:
    assert ontology_tools.term_lookup(term_fqn="term.does.not.exist") is None


def test_find_terms_in_domain_filter(seeded: bool) -> None:
    out = ontology_tools.find_terms_in_domain(domain="scm", repo_id=REPO_ID)
    # All hits must have domain == scm
    assert all(t["domain"] == "scm" for t in out)


# ── Mapping tools ─────────────────────────────────────────────────────


def test_find_existing_mapping_present(seeded: bool) -> None:
    # ValidationResult is mapped via recommend bulk
    out = mapping_tools.find_existing_mapping(
        code_fqn="com.example.slabdesign.feature.sd.process.working.wrapper.ValidationResult"
    )
    assert out is not None
    assert out["term_fqn"] == "term.scm.validation_result"
    assert out["scope"] in ("primary", "partial", "alias")


def test_find_existing_mapping_absent_returns_none(seeded: bool) -> None:
    out = mapping_tools.find_existing_mapping(code_fqn="com.does.not.Exist")
    assert out is None


def test_lookup_anchor_binding_empty_safe(seeded: bool) -> None:
    # Most methods have no AnchorBinding yet — must return [] cleanly
    out = mapping_tools.lookup_anchor_binding(
        method_fqn="com.does.not.Exist.method"
    )
    assert out == []


def test_find_unmapped_methods_in_class(seeded: bool) -> None:
    out = mapping_tools.find_unmapped_methods_in_class(
        type_fqn="com.example.slabdesign.store.sd.std.oracle.jpo.HrSpecJpo",
        limit=50,
    )
    # JPOs have many getters/setters typically with no mapping yet
    assert isinstance(out, list)


# ── Cold-start safety ─────────────────────────────────────────────────


def test_tools_handle_empty_args_gracefully() -> None:
    """All tools must return safe fallbacks for missing entities,
    not raise — agent observations need to stay graceful."""
    assert code_tools.code_lookup(fqn="x.y.z") is None
    assert code_tools.find_subclasses(type_fqn="x.y.z") == []
    assert code_tools.find_implementations(interface_fqn="x.y.z") == []
    assert code_tools.find_callers(method_fqn="x.y.z(M)") == []
    assert code_tools.find_callees(method_fqn="x.y.z(M)") == []
    assert code_tools.find_field_readers(field_fqn="x.y.z#field") == []
    assert code_tools.find_field_writers(field_fqn="x.y.z#field") == []
    assert code_tools.get_method_body(method_fqn="x.y.z(M)") is None
    assert code_tools.get_method_anchors(method_fqn="x.y.z(M)") == []
    assert code_tools.find_related_jpos(jpo_fqn="x.y.z") == []
    assert code_tools.find_in_same_package(fqn="x.y.z") == []
    assert ontology_tools.term_lookup(term_fqn="x.y.z") is None
    assert ontology_tools.action_lookup(action_fqn="x.y.z") is None
    assert ontology_tools.find_term_realizations(term_fqn="x.y.z") == []
    assert ontology_tools.find_action_realizations(action_fqn="x.y.z") == []
    assert mapping_tools.find_existing_mapping(code_fqn="x.y.z") is None
    assert mapping_tools.lookup_anchor_binding(method_fqn="x.y.z") == []
