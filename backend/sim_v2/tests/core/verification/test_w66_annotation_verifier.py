"""W66 — Annotation parity verifier tests."""
from __future__ import annotations

import json

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from backend.sim_v2.core.ontology.domain_layer.production_domain_loader import (
    ActionView,
    load_actions,
)
from backend.sim_v2.core.verification.annotation_verifier import (
    AnnotationVerification,
    extract_contract_annotations,
    extract_declared_annotations,
    verify_action_annotations,
    verify_action_annotations_batch,
)
from backend.sim_v2.demos.uc10_production_inspector.run import (
    PRODUCTION_DB_PATH,
    open_readonly_session,
)


requires_production_db = pytest.mark.skipif(
    not PRODUCTION_DB_PATH.exists(),
    reason=f"production data/ontology.db missing at {PRODUCTION_DB_PATH}",
)


# ─────────────────────────────────────────────────────────────────────────────
# Fixture
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def fixture_db():
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE actions (
                fqn TEXT, effects_json TEXT, repo_id TEXT
            )
        """))
        conn.execute(text("""
            CREATE TABLE code_methods (
                fqn TEXT, modifiers_json TEXT, repo_id TEXT
            )
        """))
    yield engine
    engine.dispose()


def _insert_action(engine, fqn, effects, repo_id="r"):
    with engine.begin() as conn:
        conn.execute(
            text("INSERT INTO actions(fqn, effects_json, repo_id) "
                 "VALUES (:f, :e, :r)"),
            {"f": fqn,
             "e": json.dumps(effects) if effects is not None else None,
             "r": repo_id},
        )


def _insert_method(engine, fqn, modifiers, repo_id="r"):
    with engine.begin() as conn:
        conn.execute(
            text("INSERT INTO code_methods(fqn, modifiers_json, repo_id) "
                 "VALUES (:f, :m, :r)"),
            {"f": fqn,
             "m": json.dumps(modifiers) if modifiers is not None else None,
             "r": repo_id},
        )


def _action(fqn, code_method_fqn=None, repo_id="r"):
    return ActionView(
        fqn=fqn, label="", code_method_fqn=code_method_fqn, repo_id=repo_id,
    )


# ─────────────────────────────────────────────────────────────────────────────
# extract_contract_annotations
# ─────────────────────────────────────────────────────────────────────────────


def test_extract_contract_filters_modifiers():
    """Plain `public`, `static` are NOT annotations — filtered out."""
    j = json.dumps(["public", "static", "@Transactional"])
    assert extract_contract_annotations(j) == ("transactional",)


def test_extract_contract_drops_non_contract_annotations():
    """@Autowired, @Query, @Component etc. are implementation-only."""
    j = json.dumps([
        "@Autowired", "@Query(\"SELECT...\")", "@Component", "public",
    ])
    assert extract_contract_annotations(j) == ()


def test_extract_contract_handles_transactional_with_args():
    j = json.dumps(["@Transactional(readOnly = true)", "public"])
    assert extract_contract_annotations(j) == ("transactional",)


def test_extract_contract_handles_post_mapping_with_path():
    j = json.dumps(["@PostMapping(\"/batch\")", "public"])
    assert extract_contract_annotations(j) == ("rest_endpoint",)


def test_extract_contract_dedupes_rest_mapping_variants():
    """@PostMapping + @GetMapping both map to `rest_endpoint` → dedupe to one."""
    j = json.dumps(["@PostMapping(\"/a\")", "@GetMapping(\"/b\")"])
    assert extract_contract_annotations(j) == ("rest_endpoint",)


def test_extract_contract_multiple_distinct_kinds():
    j = json.dumps(["@Override", "@Transactional"])
    assert extract_contract_annotations(j) == ("overrides", "transactional")


def test_extract_contract_empty_for_no_annotations():
    j = json.dumps(["public", "static"])
    assert extract_contract_annotations(j) == ()


def test_extract_contract_empty_for_none():
    assert extract_contract_annotations(None) == ()


def test_extract_contract_empty_for_malformed_json():
    assert extract_contract_annotations("{not json") == ()


def test_extract_contract_empty_for_non_list():
    assert extract_contract_annotations(json.dumps({"x": "y"})) == ()


def test_extract_contract_skips_non_string_entries():
    j = json.dumps(["@Override", 42, None, "@Transactional"])
    assert extract_contract_annotations(j) == ("overrides", "transactional")


def test_extract_contract_async_and_scheduled():
    j = json.dumps(["@Async", "@Scheduled(cron = \"0 0 * * *\")"])
    assert extract_contract_annotations(j) == ("asynchronous", "scheduled")


def test_extract_contract_cache_annotations():
    j = json.dumps(["@Cacheable", "@CacheEvict"])
    assert extract_contract_annotations(j) == ("cache_evicting", "cacheable")


def test_extract_contract_event_handler():
    j = json.dumps(["@EventListener"])
    assert extract_contract_annotations(j) == ("event_handler",)


# ─────────────────────────────────────────────────────────────────────────────
# extract_declared_annotations
# ─────────────────────────────────────────────────────────────────────────────


def test_extract_declared_transactional():
    j = json.dumps([{"kind": "transactional"}])
    assert extract_declared_annotations(j) == ("transactional",)


def test_extract_declared_rest_endpoint():
    j = json.dumps([
        {"kind": "rest_endpoint", "http_method": "POST", "path": "/batch"},
    ])
    assert extract_declared_annotations(j) == ("rest_endpoint",)


def test_extract_declared_ignores_non_contract_effects():
    j = json.dumps([
        {"kind": "raises", "exception": "X"},
        {"kind": "writes_table", "table": "T"},
        {"kind": "transactional"},   # this one counts
    ])
    assert extract_declared_annotations(j) == ("transactional",)


def test_extract_declared_lenient_type_key():
    j = json.dumps([{"type": "overrides"}])
    assert extract_declared_annotations(j) == ("overrides",)


def test_extract_declared_empty_for_none():
    assert extract_declared_annotations(None) == ()


def test_extract_declared_empty_for_malformed():
    assert extract_declared_annotations("{nope") == ()


def test_extract_declared_dedupes():
    j = json.dumps([
        {"kind": "transactional"},
        {"kind": "transactional"},
    ])
    assert extract_declared_annotations(j) == ("transactional",)


# ─────────────────────────────────────────────────────────────────────────────
# Verifier per-status
# ─────────────────────────────────────────────────────────────────────────────


def test_no_recommendation_when_code_method_fqn_missing(fixture_db):
    a = _action("a.x")
    with Session(fixture_db) as session:
        v = verify_action_annotations(session, a)
    assert v.status == "NO_RECOMMENDATION"


def test_method_not_found(fixture_db):
    _insert_action(fixture_db, "a.x", None)
    a = _action("a.x", code_method_fqn="com.x.foo()")
    with Session(fixture_db) as session:
        v = verify_action_annotations(session, a)
    assert v.status == "METHOD_NOT_FOUND"


def test_verified_when_both_empty(fixture_db):
    _insert_action(fixture_db, "a.x", None)
    _insert_method(fixture_db, "com.x.foo()", ["public"])
    a = _action("a.x", code_method_fqn="com.x.foo()")
    with Session(fixture_db) as session:
        v = verify_action_annotations(session, a)
    assert v.status == "VERIFIED"


def test_verified_when_both_have_transactional(fixture_db):
    _insert_action(fixture_db, "a.x", [{"kind": "transactional"}])
    _insert_method(fixture_db, "com.x.foo()",
                   ["@Transactional(readOnly = true)", "public"])
    a = _action("a.x", code_method_fqn="com.x.foo()")
    with Session(fixture_db) as session:
        v = verify_action_annotations(session, a)
    assert v.status == "VERIFIED"


def test_undeclared_when_method_transactional_but_action_silent(fixture_db):
    """The dominant production case."""
    _insert_action(fixture_db, "a.x", None)
    _insert_method(fixture_db, "com.x.foo()",
                   ["@Transactional", "public"])
    a = _action("a.x", code_method_fqn="com.x.foo()")
    with Session(fixture_db) as session:
        v = verify_action_annotations(session, a)
    assert v.status == "UNDECLARED_ANNOTATION"
    assert v.undeclared_only == ("transactional",)


def test_undeclared_when_method_override_but_action_silent(fixture_db):
    _insert_action(fixture_db, "a.x", None)
    _insert_method(fixture_db, "com.x.foo()", ["@Override", "public"])
    a = _action("a.x", code_method_fqn="com.x.foo()")
    with Session(fixture_db) as session:
        v = verify_action_annotations(session, a)
    assert v.status == "UNDECLARED_ANNOTATION"
    assert "overrides" in v.undeclared_only


def test_missing_when_action_declares_but_method_silent(fixture_db):
    _insert_action(fixture_db, "a.x", [{"kind": "transactional"}])
    _insert_method(fixture_db, "com.x.foo()", ["public"])
    a = _action("a.x", code_method_fqn="com.x.foo()")
    with Session(fixture_db) as session:
        v = verify_action_annotations(session, a)
    assert v.status == "MISSING_ANNOTATION"
    assert v.missing_only == ("transactional",)


def test_divergent_when_both_non_empty_but_differ(fixture_db):
    _insert_action(fixture_db, "a.x", [{"kind": "transactional"}])
    _insert_method(fixture_db, "com.x.foo()",
                   ["@Override", "public"])
    a = _action("a.x", code_method_fqn="com.x.foo()")
    with Session(fixture_db) as session:
        v = verify_action_annotations(session, a)
    assert v.status == "DIVERGENT_ANNOTATIONS"
    assert "overrides" in v.undeclared_only
    assert "transactional" in v.missing_only


def test_implementation_only_annotations_ignored(fixture_db):
    """@Autowired is filtered → action with no effects + method with @Autowired
    is VERIFIED (not UNDECLARED)."""
    _insert_action(fixture_db, "a.x", None)
    _insert_method(fixture_db, "com.x.foo()",
                   ["@Autowired", "@Query(\"SELECT...\")", "public"])
    a = _action("a.x", code_method_fqn="com.x.foo()")
    with Session(fixture_db) as session:
        v = verify_action_annotations(session, a)
    assert v.status == "VERIFIED"


def test_batch_preserves_order(fixture_db):
    _insert_action(fixture_db, "a.1", None)
    _insert_action(fixture_db, "a.2", None)
    _insert_method(fixture_db, "com.x.foo()", ["@Transactional", "public"])
    _insert_method(fixture_db, "com.x.bar()", ["public"])
    actions = [
        _action("a.1", code_method_fqn="com.x.foo()"),
        _action("a.2", code_method_fqn="com.x.bar()"),
    ]
    with Session(fixture_db) as session:
        verifs = verify_action_annotations_batch(session, actions)
    assert [v.action_fqn for v in verifs] == ["a.1", "a.2"]


def test_annotation_verification_is_frozen():
    v = AnnotationVerification(
        action_fqn="a", code_method_fqn=None, status="NO_RECOMMENDATION",
    )
    with pytest.raises(Exception):
        v.status = "VERIFIED"  # type: ignore[misc]


# ─────────────────────────────────────────────────────────────────────────────
# Production smoke
# ─────────────────────────────────────────────────────────────────────────────


@requires_production_db
def test_production_yields_at_least_one_undeclared():
    """slab-design-real has 5 @Transactional + 22 @Override + 1 @PostMapping;
    most of them won't appear in any action's effects_json → UNDECLARED."""
    session = open_readonly_session()
    try:
        actions = load_actions(session, "slab-design-real")
        verifs = verify_action_annotations_batch(session, actions)
        undeclared = [v for v in verifs if v.status == "UNDECLARED_ANNOTATION"]
        assert len(undeclared) > 0
    finally:
        session.close()


@requires_production_db
def test_production_undeclared_includes_recognizable_kinds():
    """Production findings should mention `transactional` / `overrides` /
    `rest_endpoint` (the contract-bearing annotation kinds)."""
    session = open_readonly_session()
    try:
        actions = load_actions(session, "slab-design-real")
        verifs = verify_action_annotations_batch(session, actions)
        all_kinds: set[str] = set()
        for v in verifs:
            for k in v.undeclared_only:
                all_kinds.add(k)
        recognized = {"transactional", "overrides", "rest_endpoint"}
        assert all_kinds & recognized
    finally:
        session.close()
