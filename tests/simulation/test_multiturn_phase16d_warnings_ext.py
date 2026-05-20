"""Phase 16D — extended integrity warnings (W1c + W4).

QA 페르소나 16C 권고. 16C 의 W1b ("body_unsupported_rule_only") 가 alias gap 인지
다른 원인인지 unclear → root cause 더 명확하게:

  W1c: verdict ∈ {yes, likely_yes} + matched_var=="" + rule_signals ≥ 2
       → `body_unsupported_alias_gap` (Korean↔English alias 미커버 가능성)

  W4: target.code_method_fqn 또는 className 이 `*Test` / `Mock*` / `*Stub*` 패턴
       → `target_is_test` warning (ranking 이 test class 를 production 으로 잘못 선택)
"""
from __future__ import annotations

import pytest


# ─────────────────────────────────────────────────────────────────────────────
# W1c — body_unsupported_alias_gap
# ─────────────────────────────────────────────────────────────────────────────


def test_w1c_alias_gap_when_yes_matched_var_empty_and_rule_strong() -> None:
    """verdict=yes + matched_var='' + rule_signals=3 → alias_gap warning."""
    from backend.section3.agents.multiturn.gate_hypothesis import (
        _compute_integrity_warnings,
    )
    warnings = _compute_integrity_warnings(
        verdict="yes",
        reasoning="body 변수 매칭 약함 이나 rule 3 행 (matched var='', op='<')",
        body_signals=1,
        rule_signals=3,
        fixture_compat={
            "compat": False, "matched_params": [],
            "mismatch_reason": "var miss",
        },
        matched_var="",   # 새 인자
    )
    msg = " ".join(warnings).lower()
    assert any("alias" in w.lower() for w in warnings), (
        f"alias_gap warning 발화 기대. warnings={warnings}"
    )


def test_w1c_no_alias_warning_when_matched_var_present() -> None:
    """matched_var 비어있지 않으면 alias_gap warning X."""
    from backend.section3.agents.multiturn.gate_hypothesis import (
        _compute_integrity_warnings,
    )
    warnings = _compute_integrity_warnings(
        verdict="yes",
        reasoning="body 안에 정확한 expression `margin < 1.0`",
        body_signals=5,
        rule_signals=2,
        fixture_compat={
            "compat": True, "matched_params": ["margin"], "mismatch_reason": "",
        },
        matched_var="margin",
    )
    assert not any("alias" in w.lower() for w in warnings), (
        f"matched_var 있으면 alias_gap X. warnings={warnings}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# W4 — target_is_test
# ─────────────────────────────────────────────────────────────────────────────


def test_w4_target_is_test_when_method_fqn_contains_test() -> None:
    """target_fqn 이 *Test* 패턴 → target_is_test warning."""
    from backend.section3.agents.multiturn.gate_hypothesis import (
        _compute_integrity_warnings,
    )
    warnings = _compute_integrity_warnings(
        verdict="yes",
        reasoning="...",
        body_signals=3, rule_signals=0,
        fixture_compat={"compat": True, "matched_params": ["x"], "mismatch_reason": ""},
        matched_var="x",
        target_fqn="com.x.SdOrderValidatorTest.dg103_test()",
    )
    assert any("test" in w.lower() for w in warnings), (
        f"target_is_test warning 발화 기대. warnings={warnings}"
    )


def test_w4_target_is_mock_when_classname_starts_with_mock() -> None:
    """Mock* 패턴 → target_is_test warning."""
    from backend.section3.agents.multiturn.gate_hypothesis import (
        _compute_integrity_warnings,
    )
    warnings = _compute_integrity_warnings(
        verdict="likely_yes",
        reasoning="...",
        body_signals=2, rule_signals=0,
        fixture_compat={"compat": True, "matched_params": ["x"], "mismatch_reason": ""},
        matched_var="x",
        target_fqn="com.x.MockOrderService.process()",
    )
    assert any("test" in w.lower() or "mock" in w.lower() for w in warnings), (
        f"target_is_test (Mock pattern) warning 발화 기대. warnings={warnings}"
    )


def test_w4_no_warning_for_production_target() -> None:
    """production target (Test/Mock 패턴 아님) → warning X."""
    from backend.section3.agents.multiturn.gate_hypothesis import (
        _compute_integrity_warnings,
    )
    warnings = _compute_integrity_warnings(
        verdict="yes",
        reasoning="...",
        body_signals=5, rule_signals=2,
        fixture_compat={"compat": True, "matched_params": ["x"], "mismatch_reason": ""},
        matched_var="x",
        target_fqn="com.x.SdOrderValidator.validate(SDOrderEntity)",
    )
    # production target — W4 미발화 + 다른 warning 도 미발화 (일관)
    assert not any("test" in w.lower() or "mock" in w.lower() for w in warnings)


# ─────────────────────────────────────────────────────────────────────────────
# backward compat — 새 인자 없이도 동작
# ─────────────────────────────────────────────────────────────────────────────


def test_backward_compat_no_new_args() -> None:
    """matched_var / target_fqn 없이 호출 — 기존 W1/W2/W3 만 동작."""
    from backend.section3.agents.multiturn.gate_hypothesis import (
        _compute_integrity_warnings,
    )
    warnings = _compute_integrity_warnings(
        verdict="yes",
        reasoning="body 안에 정확한 expression",
        body_signals=5, rule_signals=2,
        fixture_compat={"compat": True, "matched_params": ["margin"], "mismatch_reason": ""},
    )
    # 정상 케이스 — warning 0
    assert warnings == []


# ─────────────────────────────────────────────────────────────────────────────
# build_gate_hypothesis 가 W4 (target_fqn) 까지 surface
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_build_gate_hypothesis_surfaces_w4_for_test_target(tmp_path, monkeypatch) -> None:
    """target.code_method_fqn 이 Test 패턴이면 sources 에 target_is_test surface."""
    from backend.modeling.persistence import database as db_mod
    db_path = tmp_path / "phase16d.db"
    monkeypatch.setenv("ONTONG_DB_PATH", str(db_path))
    db_mod.reset_engine_for_tests()

    from backend.modeling.code_layer import orm as _code_orm  # noqa: F401
    from backend.modeling.domain_layer import orm as _domain_orm  # noqa: F401
    from backend.modeling.mapping_layer import orm as _mapping_orm  # noqa: F401
    from backend.modeling.view_layer import orm as _view_orm  # noqa: F401
    from backend.application.authoring import orm as _authoring_orm  # noqa: F401
    from backend.section3.agents.multiturn import orm as _multiturn_orm  # noqa: F401
    db_mod.bootstrap_database()

    from backend.section3.agents.multiturn.gate_hypothesis import (
        build_gate_hypothesis,
    )
    from backend.section3.agents.multiturn.ontology_client import MockOntologyClient
    from backend.section3.agents.multiturn.schemas import ActionRef, CodeLocation

    client = MockOntologyClient(catalog={
        "method_bodies": {"com.x.SdEdgingTest.dg103_test": "if (x < 1.0) throw;"},
    })
    target = ActionRef(
        action_id="a",
        code_method_fqn="com.x.SdEdgingTest.dg103_test",
        repo_id="r",
        location=CodeLocation(file_path="x.java", line_start=1, line_end=10),
    )
    payload = await build_gate_hypothesis(
        target=target,
        conditions=[{"var": "x", "op": "<", "value": "1.0", "unit": ""}],
        repo_id="r",
        ontology_client=client,
    )
    detail_str = " ".join(p.detail for p in payload.sources)
    assert "test" in detail_str.lower() and "target" in detail_str.lower(), (
        f"target_is_test warning surface 기대. sources={[p.detail for p in payload.sources]}"
    )

    db_mod.reset_engine_for_tests()
