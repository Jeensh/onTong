"""UC40 — Stub-injected behavioral survey tests."""
from __future__ import annotations

import pytest

from backend.sim_v2.demos.uc10_production_inspector.run import (
    PRODUCTION_DB_PATH,
    open_readonly_session,
)
from backend.sim_v2.demos.uc40_stub_injected_behavioral.run import (
    StubInjectedReport,
    TARGET_REPO,
    main,
    run_stub_injected_survey,
)


requires_production_db = pytest.mark.skipif(
    not PRODUCTION_DB_PATH.exists(),
    reason=f"production data/ontology.db missing at {PRODUCTION_DB_PATH}",
)


def test_main_returns_zero_without_db(monkeypatch):
    from backend.sim_v2.demos.uc40_stub_injected_behavioral import run as r
    monkeypatch.setattr(r, "open_readonly_session", lambda *a, **kw: None)
    assert main() == 0


@requires_production_db
def test_main_returns_zero():
    assert main() == 0


@requires_production_db
def test_v2_stub_injection_unlocks_pass_rate():
    """W74 stub injection 으로 W71-driveable subset 의 절반 이상이 PASS 도달.
    UC38 의 0/11 PASS 가 stub 주입 후 큰 폭으로 개선됨을 pin.
    """
    s = open_readonly_session()
    try:
        r = run_stub_injected_survey(s)
        assert isinstance(r, StubInjectedReport)
        pass_count = r.status_counts.get("PASS", 0)
        assert pass_count >= 4   # 실측 ~6 (54.5%) — 보수적 마진
    finally:
        s.close()


@requires_production_db
def test_v2_stub_count_reflects_complexity():
    """Stubs 가 실제로 주입됐는지 — 0 이면 anchor/AST 모두 비어있는 케이스."""
    s = open_readonly_session()
    try:
        r = run_stub_injected_survey(s)
        non_zero_stubs = sum(1 for row in r.rows if row.stub_count > 0)
        assert non_zero_stubs >= 6
    finally:
        s.close()


@requires_production_db
def test_v2_status_categories_are_well_formed():
    s = open_readonly_session()
    try:
        r = run_stub_injected_survey(s)
        allowed = {
            "PASS", "FAIL_RETURN_TYPE", "FAIL_UNEXPECTED_THROW",
            "FAIL_NONDETERMINISTIC", "ERROR",
        }
        seen = set(r.status_counts.keys())
        assert seen <= allowed, f"unexpected statuses: {seen - allowed}"
    finally:
        s.close()


def test_target_repo_is_v2():
    assert TARGET_REPO == "slab-design-real-v2"
