"""UC24 — Return-type remediation demo verification — W58.3."""
from __future__ import annotations

import pytest

from backend.sim_v2.demos.uc10_production_inspector.run import (
    PRODUCTION_DB_PATH,
    open_readonly_session,
)
from backend.sim_v2.demos.uc24_return_type_remediation.run import (
    DEFAULT_REPOS,
    RepoReturnTypeRemediation,
    main,
    remediate_repo,
)


requires_production_db = pytest.mark.skipif(
    not PRODUCTION_DB_PATH.exists(),
    reason=f"production data/ontology.db missing at {PRODUCTION_DB_PATH}",
)


def test_main_returns_zero_without_db(monkeypatch):
    from backend.sim_v2.demos.uc24_return_type_remediation import run as runmod
    monkeypatch.setattr(runmod, "open_readonly_session", lambda *_a, **_kw: None)
    assert main() == 0


@requires_production_db
def test_main_returns_zero():
    assert main() == 0


@requires_production_db
def test_remediate_slab_design_real_yields_steps():
    session = open_readonly_session()
    try:
        r = remediate_repo(session, "slab-design-real")
        assert isinstance(r, RepoReturnTypeRemediation)
        # 8 PRIMITIVE_MISMATCH + 1 OBJECT_REF_MISMATCH + 1 IMPLICIT_OUTPUT
        # → at least 10 actionable steps
        assert len(r.report.steps) >= 10
    finally:
        session.close()


@requires_production_db
def test_remediate_slab_design_real_includes_change_primitive():
    """BigDecimal return → float→decimal primitive change."""
    session = open_readonly_session()
    try:
        r = remediate_repo(session, "slab-design-real")
        changes = [s for s in r.report.steps
                   if s.kind == "CHANGE_PRIMITIVE_TYPE"]
        assert len(changes) > 0
        assert any(
            s.method_return == "BigDecimal"
            and '"decimal"' in s.expected_output
            for s in changes
        )
    finally:
        session.close()


@requires_production_db
def test_remediate_slab_design_real_includes_wrap_as_list_for_orders():
    session = open_readonly_session()
    try:
        r = remediate_repo(session, "slab-design-real")
        wraps = [s for s in r.report.steps if s.kind == "WRAP_AS_LIST"]
        assert any(
            s.action_fqn == "action.scm.order.extract_designable_orders"
            for s in wraps
        )
    finally:
        session.close()


@requires_production_db
def test_remediate_slab_design_real_includes_declare_output():
    """The known case: Slab설계_실행 has no output but method returns SDSlabEntity."""
    session = open_readonly_session()
    try:
        r = remediate_repo(session, "slab-design-real")
        declares = [s for s in r.report.steps if s.kind == "DECLARE_OUTPUT"]
        assert len(declares) > 0
    finally:
        session.close()


@requires_production_db
def test_remediate_slab_design_real_includes_propose_new_term():
    """ProductCategory / BatchResult don't have existing terms → new term proposed."""
    session = open_readonly_session()
    try:
        r = remediate_repo(session, "slab-design-real")
        proposes = [s for s in r.report.steps if s.kind == "PROPOSE_NEW_TERM"]
        assert len(proposes) > 0
        proposed_classes = {s.proposed_class for s in proposes}
        # Either ProductCategory or BatchResult should appear
        assert proposed_classes & {"ProductCategory", "BatchResult"}
    finally:
        session.close()


@requires_production_db
def test_remediate_unknown_repo_yields_empty():
    session = open_readonly_session()
    try:
        r = remediate_repo(session, "no-such-repo")
        assert r.report.steps == []
    finally:
        session.close()


def test_default_repos_covers_v1_and_v2():
    assert "slab-design-real" in DEFAULT_REPOS
    assert "slab-design-real-v2" in DEFAULT_REPOS
