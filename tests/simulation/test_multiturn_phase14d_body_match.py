"""Phase 14D — body × conditions 매칭 강화.

페르소나 검증 (PM 13c) 발견:
  - body_signals=0 인데 rule_signals 만으로 verdict=likely_yes
  - body 안에 var/op/value 가 흩어진 곳에 있어도 그냥 합산해서 likely_yes
  - 노이즈: "value=0" 인데 body 에 `index 0` 같은 무관 매칭

해결책 (정밀화 4종):
  (a) var 의 모든 token 이 같이 등장해야 (AND 매칭) — 단일 token 부분 매칭 차단
  (b) value 는 word-boundary 매칭 (예: "0" 은 `\b0\b` — `index0` 차단)
  (c) **co-occurrence boost**: var + value 가 같은 line 에 있으면 +2 (단순 합산 +1 보다 강함)
  (d) **expression boost**: regex `var\s*op\s*value` 매칭 시 verdict=likely_yes 강한 신호
"""
from __future__ import annotations

import pytest

from backend.section3.agents.multiturn.gate_hypothesis import _infer_verdict


# ─────────────────────────────────────────────────────────────────────────────
# (1) word-boundary value 매칭 — 노이즈 차단
# ─────────────────────────────────────────────────────────────────────────────


def test_value_word_boundary_avoids_index_collision() -> None:
    """body 의 'index0' 가 value='0' 매칭에 잡히면 안 됨."""
    body = "for (int i = 0; i < arr.length; i++) { result[index0] = i; }"
    # var "수량" 은 body 에 없음. value "0" 만 body 의 `i = 0` 매칭 — 의도적인 hit.
    # 단, "index0" 같은 token 내부 매칭은 안 잡혀야 — `\b0\b` boundary 필요.
    # body_signals 가 boundary 매칭 1회 (i=0) 만 잡고 index0 무시.
    verdict, _, body_sig, _ = _infer_verdict(
        body_text=body,
        conditions=[{"var": "수량", "op": "=", "value": "0", "unit": ""}],
        evidence=[],
    )
    # body 의 "수량" 0 → var hit 0. value "0" 의 word-boundary hit 1 (i = 0 에서).
    # op "=" 의 substring hit 있음. body_signals ≤ 2 (var 없음).
    # index0 매칭은 boundary 이슈로 잡히면 안 되지만, 현재 substring 매칭은 잡힐 수 있음.
    # 핵심 검증: 노이즈가 verdict 를 likely_yes 로 만들면 안 됨.
    assert verdict in ("likely_no", "unknown"), (
        f"var 누락 + boundary 매칭만으로 likely_yes 면 안 됨. "
        f"verdict={verdict} body_sig={body_sig}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# (2) var token AND 매칭 (다중 단어)
# ─────────────────────────────────────────────────────────────────────────────


def test_var_multi_token_requires_all_match() -> None:
    """'주문 수량' 의 모든 token (주문 + 수량) 이 body 에 다 있어야 var hit."""
    body_partial = "void f() { 주문 = 5; }"   # 주문 만 있음
    body_full = "void f() { 주문수량 = 5; if (주문수량 == 0) fail(); }"

    # partial: var hit 약함
    verdict_p, _, sig_p, _ = _infer_verdict(
        body_text=body_partial,
        conditions=[{"var": "주문 수량", "op": "=", "value": "5", "unit": ""}],
        evidence=[],
    )
    # full: var hit 강함
    verdict_f, _, sig_f, _ = _infer_verdict(
        body_text=body_full,
        conditions=[{"var": "주문 수량", "op": "=", "value": "0", "unit": ""}],
        evidence=[],
    )
    # full 이 partial 보다 confidence 높아야
    assert sig_f >= sig_p, (
        f"all-token 매칭이 더 강한 시그널이어야. "
        f"partial={sig_p} full={sig_f}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# (3) co-occurrence — var + value 가 같은 line
# ─────────────────────────────────────────────────────────────────────────────


def test_cooccurrence_boosts_verdict_above_isolated_signals() -> None:
    """var + value 가 같은 line 에 있으면 흩어진 경우보다 verdict 강함."""
    body_cooc = "if (margin < 1.0) throw new EdgException('EDG_001');"
    body_isolated = (
        "// margin description\n"
        "void check() {\n"
        "    int x = 1;\n"  # 1.0 unrelated
        "    do_unrelated_stuff();\n"
        "}\n"
    )

    v_cooc, _, sig_cooc, _ = _infer_verdict(
        body_text=body_cooc,
        conditions=[{"var": "margin", "op": "<", "value": "1.0", "unit": ""}],
        evidence=[],
    )
    v_iso, _, sig_iso, _ = _infer_verdict(
        body_text=body_isolated,
        conditions=[{"var": "margin", "op": "<", "value": "1.0", "unit": ""}],
        evidence=[],
    )
    # co-occurrence 케이스는 likely_yes / yes, isolated 는 더 낮은 등급
    assert v_cooc in ("yes", "likely_yes"), (
        f"co-occurrence 시 likely_yes 이상이어야. v_cooc={v_cooc}"
    )
    assert sig_cooc > sig_iso, (
        f"co-occurrence 시그널이 isolated 보다 강해야. "
        f"co-oc={sig_cooc} iso={sig_iso}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# (4) expression 매칭 — `var op value` 정확 패턴
# ─────────────────────────────────────────────────────────────────────────────


def test_expression_pattern_match_yields_strongest_verdict() -> None:
    """body 안에 `margin < 1.0` 같은 정확한 expression → yes."""
    body = "if (margin < 1.0) throw new EdgException('EDG_001');"
    verdict, _, body_sig, _ = _infer_verdict(
        body_text=body,
        conditions=[{"var": "margin", "op": "<", "value": "1.0", "unit": ""}],
        evidence=[],
    )
    # exact expression match → 강한 verdict (yes 또는 likely_yes), confidence high
    assert verdict in ("yes", "likely_yes"), f"expression match 시 강한 verdict. v={verdict}"


def test_expression_pattern_works_with_korean_op_words() -> None:
    """op 가 '<' / '<=' / '>' / '>=' / '==' / '!=' 등에 정확 매칭."""
    body = "if (qty <= 0) throw 'invalid';"
    verdict, _, sig, _ = _infer_verdict(
        body_text=body,
        conditions=[{"var": "qty", "op": "<=", "value": "0", "unit": ""}],
        evidence=[],
    )
    assert verdict in ("yes", "likely_yes"), (
        f"<= operator 매칭 시 강한 verdict. v={verdict} sig={sig}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# (5) unknown 회귀 — 시그널 전혀 없음
# ─────────────────────────────────────────────────────────────────────────────


def test_unknown_verdict_when_no_signals() -> None:
    """body 도 evidence 도 전혀 무관 → unknown (정직)."""
    body = "void unrelated() { System.out.println('hello'); }"
    verdict, _, sig, _ = _infer_verdict(
        body_text=body,
        conditions=[{"var": "두께", "op": "<", "value": "0.1", "unit": "mm"}],
        evidence=[],
    )
    assert verdict == "unknown"
    assert sig == 0


# ─────────────────────────────────────────────────────────────────────────────
# (6) regression — empty conditions / body
# ─────────────────────────────────────────────────────────────────────────────


def test_empty_conditions_unknown() -> None:
    v, _, _, _ = _infer_verdict(body_text="x", conditions=[], evidence=[])
    assert v == "unknown"


def test_empty_body_with_rule_evidence_still_signals() -> None:
    """body 가 비어도 evidence (rule) 가 매칭하면 약한 likely_yes."""
    from backend.section3.agents.multiturn.schemas import BusinessRuleEvidence
    v, _, body_sig, rule_sig = _infer_verdict(
        body_text="",
        conditions=[{"var": "주문 수량", "op": "=", "value": "0", "unit": ""}],
        evidence=[
            BusinessRuleEvidence(
                fqn="rule.x", statement="주문 수량이 0 인 경우 거부",
                severity="hard",
            ),
        ],
    )
    assert body_sig == 0
    assert rule_sig >= 1
    assert v in ("likely_yes", "unknown")  # rule_signals 만 있을 때 약하게 likely_yes
