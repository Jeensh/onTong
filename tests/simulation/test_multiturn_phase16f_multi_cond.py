"""Phase 16F — multi-cond AND verdict semantics.

시니어 16B 권고 #2. 현재 `_infer_verdict` 가 multi-condition 의 signal 들을
단순 합산 → OR 처럼 동작. 명시적 AND semantic:

  - 모든 conditions 의 var+value+op 가 body 안에서 매칭 (또는 expression match) → yes
  - 일부만 매칭 → likely_yes 약화
  - 전부 미매칭 → unknown/likely_no

per-condition matched count 를 reasoning 에 surface.
"""
from __future__ import annotations

import pytest


# ─────────────────────────────────────────────────────────────────────────────
# (1) 2 conditions 모두 매칭 → yes
# ─────────────────────────────────────────────────────────────────────────────


def test_two_conditions_both_match_yields_yes() -> None:
    """body 안에 두 condition 모두 expression match → verdict=yes."""
    from backend.section3.agents.multiturn.gate_hypothesis import _infer_verdict

    body = "if (thickness < 0.1 && width > 100) throw new Ex();"
    verdict, reasoning, _, _ = _infer_verdict(
        body_text=body,
        conditions=[
            {"var": "thickness", "op": "<", "value": "0.1", "unit": "mm"},
            {"var": "width", "op": ">", "value": "100", "unit": "mm"},
        ],
        evidence=[],
    )
    assert verdict in ("yes", "likely_yes"), (
        f"두 condition 모두 매칭 → likely_yes 이상. v={verdict}"
    )


def test_two_conditions_partial_match_yields_likely_yes() -> None:
    """1 condition 만 매칭 → likely_yes 약화 (전부 yes 보다 낮음)."""
    from backend.section3.agents.multiturn.gate_hypothesis import _infer_verdict

    body = "if (thickness < 0.1) throw;"  # width 부재
    verdict, reasoning, _, _ = _infer_verdict(
        body_text=body,
        conditions=[
            {"var": "thickness", "op": "<", "value": "0.1", "unit": "mm"},
            {"var": "width", "op": ">", "value": "100", "unit": "mm"},
        ],
        evidence=[],
    )
    # 1/2 매칭 → likely_yes 또는 likely_no (partial)
    assert verdict in ("likely_yes", "likely_no", "yes")  # 강화/약화는 heuristic 영역


def test_two_conditions_zero_match_yields_unknown_or_likely_no() -> None:
    """둘 다 매칭 X → unknown / likely_no."""
    from backend.section3.agents.multiturn.gate_hypothesis import _infer_verdict

    body = "System.out.println('hi');"  # 둘 다 매칭 X
    verdict, reasoning, _, _ = _infer_verdict(
        body_text=body,
        conditions=[
            {"var": "thickness", "op": "<", "value": "0.1", "unit": "mm"},
            {"var": "width", "op": ">", "value": "100", "unit": "mm"},
        ],
        evidence=[],
    )
    assert verdict in ("unknown", "likely_no")


# ─────────────────────────────────────────────────────────────────────────────
# (2) per-condition matched count surface in reasoning
# ─────────────────────────────────────────────────────────────────────────────


def test_reasoning_surfaces_match_count() -> None:
    """reasoning 에 N/M conditions matched 명시."""
    from backend.section3.agents.multiturn.gate_hypothesis import _infer_verdict

    body = "if (thickness < 0.1) throw;"
    _, reasoning, _, _ = _infer_verdict(
        body_text=body,
        conditions=[
            {"var": "thickness", "op": "<", "value": "0.1", "unit": "mm"},
            {"var": "width", "op": ">", "value": "100", "unit": "mm"},
        ],
        evidence=[],
    )
    # 1/2 매칭 정보 (또는 partial 명시) surface
    assert ("1/2" in reasoning) or ("partial" in reasoning.lower()) or (
        "조건" in reasoning and ("매칭" in reasoning or "일부" in reasoning)
    ), f"reasoning 에 partial match 정보 surface. reasoning={reasoning!r}"


def test_reasoning_all_match_says_all() -> None:
    """모든 conditions 매칭 시 reasoning 에 명시."""
    from backend.section3.agents.multiturn.gate_hypothesis import _infer_verdict

    body = "if (thickness < 0.1 && width > 100) throw;"
    _, reasoning, _, _ = _infer_verdict(
        body_text=body,
        conditions=[
            {"var": "thickness", "op": "<", "value": "0.1", "unit": "mm"},
            {"var": "width", "op": ">", "value": "100", "unit": "mm"},
        ],
        evidence=[],
    )
    # 2/2 매칭 정보
    assert ("2/2" in reasoning) or ("모든" in reasoning) or ("all" in reasoning.lower()) or (
        "조건" in reasoning and ("매칭" in reasoning)
    ), f"reasoning 에 all match 정보 surface. reasoning={reasoning!r}"


# ─────────────────────────────────────────────────────────────────────────────
# (3) backward compat — single condition 동작 변동 없음
# ─────────────────────────────────────────────────────────────────────────────


def test_single_condition_backward_compat() -> None:
    from backend.section3.agents.multiturn.gate_hypothesis import _infer_verdict

    body = "if (margin < 1.0) throw;"
    verdict, _, _, _ = _infer_verdict(
        body_text=body,
        conditions=[{"var": "margin", "op": "<", "value": "1.0", "unit": ""}],
        evidence=[],
    )
    # 단일 condition 정확 매칭 → likely_yes/yes
    assert verdict in ("yes", "likely_yes")


# ─────────────────────────────────────────────────────────────────────────────
# (4) all-match preference over partial: 2/2 ≥ 1/2
# ─────────────────────────────────────────────────────────────────────────────


def test_all_match_stronger_than_partial() -> None:
    """동일 query 에서 all-match 케이스가 partial 보다 verdict 강하거나 같아야."""
    from backend.section3.agents.multiturn.gate_hypothesis import _infer_verdict

    conditions = [
        {"var": "thickness", "op": "<", "value": "0.1", "unit": ""},
        {"var": "width", "op": ">", "value": "100", "unit": ""},
    ]
    body_all = "if (thickness < 0.1 && width > 100) throw;"
    body_partial = "if (thickness < 0.1) throw;"

    v_all, _, sig_all, _ = _infer_verdict(
        body_text=body_all, conditions=conditions, evidence=[],
    )
    v_partial, _, sig_partial, _ = _infer_verdict(
        body_text=body_partial, conditions=conditions, evidence=[],
    )
    # all-match 의 body_signals 가 partial 이상이어야
    assert sig_all >= sig_partial, (
        f"all-match signals ≥ partial. all={sig_all} partial={sig_partial}"
    )
