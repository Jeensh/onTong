"""Hypothesis strategies — slab-design 도메인 case 자동 생성.

CaseType별 strategy:
- normal: 알고리즘 통과 가능한 정상 분포
- boundary: 경계값 (NULL, 0, very small, very large, 정확히 hr boundary 등)
- error: 검증 실패가 의도된 입력 (DG001~005 trigger)
- performance: 큰 designPendQty 등으로 매수 많이 나오는 케이스

Hypothesis는 shrink로 minimal failing case를 찾아주므로, 실패가 발견되면
가장 작은 reproducible 입력을 보고할 수 있다.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Literal

from hypothesis import strategies as st


CaseType = Literal["normal", "boundary", "error", "performance"]


# ─── Decimal ────────────────────────────────────────────────────────


def positive_decimal(min_value: float = 0.001, max_value: float = 1000.0) -> st.SearchStrategy[Decimal]:
    """양수 Decimal."""
    return st.decimals(
        min_value=Decimal(str(min_value)),
        max_value=Decimal(str(max_value)),
        allow_nan=False,
        allow_infinity=False,
        places=4,
    )


def signed_decimal(min_value: float = -1000.0, max_value: float = 1000.0) -> st.SearchStrategy[Decimal]:
    return st.decimals(
        min_value=Decimal(str(min_value)),
        max_value=Decimal(str(max_value)),
        allow_nan=False,
        allow_infinity=False,
        places=4,
    )


# ─── 날짜 ────────────────────────────────────────────────────────────


def future_date(days_ahead_min: int = 1, days_ahead_max: int = 365) -> st.SearchStrategy[str]:
    today = date.today()
    return st.integers(min_value=days_ahead_min, max_value=days_ahead_max).map(
        lambda d: (today + timedelta(days=d)).isoformat()
    )


def past_or_today_date() -> st.SearchStrategy[str]:
    today = date.today()
    return st.integers(min_value=-365, max_value=0).map(
        lambda d: (today + timedelta(days=d)).isoformat()
    )


# ─── 코드 / 문자열 ──────────────────────────────────────────────────


CONFIRMED_PLANT_PATTERN = st.lists(
    st.sampled_from(["K", "A", "B", "C", "D", " "]),
    min_size=8, max_size=8,
).map(lambda chars: "".join(chars))
"""8자리 confirmedPlantCd. ' '=비활성. 데모 fixture에 mapping이 있는 K/A/B/C/D만 사용."""


def confirmed_plant_with_active_sm() -> st.SearchStrategy[str]:
    """제강 활성 (idx 0이 ' ' 아님)."""
    return st.lists(
        st.sampled_from(["K", "A", "B", "C", "D", " "]),
        min_size=8, max_size=8,
    ).filter(lambda chars: chars[0] != " ").map(lambda chars: "".join(chars))


# ─── Order 변형 dict (overrides for fixtures.make_default_order) ────


@st.composite
def normal_order_overrides(draw) -> dict:
    """알고리즘 통과 가능한 정상 분포 — 데모 fixture와 호환.

    제약:
    - DG003: pkgWgtLow ≤ pkgWgtHigh ← 강제
    - DG004: designPendQtyHigh ≥ pkgWgtLow ← 강제 (cross-table)
    - 양수 보장
    """
    pkg_low = draw(positive_decimal(1, 30))
    pkg_high = pkg_low + draw(positive_decimal(0.001, 50))
    # designPendQtyHigh ≥ pkgWgtLow 보장 (DG004 통과)
    pend_high = pkg_low + draw(positive_decimal(0.1, 200))
    pend_low = draw(positive_decimal(0.001, float(pend_high) - 0.001))

    order_wgt_low = draw(positive_decimal(5, 15))
    order_wgt_high = order_wgt_low + draw(positive_decimal(0.001, 30))
    return {
        "stockCode": 0,
        "orderWidth": str(draw(positive_decimal(800, 2000))),
        "orderLength": str(draw(positive_decimal(2000, 6000))),
        "pkgWgtLow": str(pkg_low),
        "pkgWgtHigh": str(pkg_high),
        "orderWgtLow": str(order_wgt_low),
        "orderWgtHigh": str(order_wgt_high),
        "designPendQty": str(draw(positive_decimal(50, 200))),
        "designPendQtyLow": str(pend_low),
        "designPendQtyHigh": str(pend_high),
        "confirmedPlantCd": draw(confirmed_plant_with_active_sm()),
        "workDue": draw(future_date(7, 90)),
    }


@st.composite
def boundary_order_overrides(draw) -> dict:
    """경계값 — 0, 매우 작은 값, 정확히 임계치, NULL 가까운 값."""
    pick = draw(st.sampled_from([
        "very_small_pend", "exact_match_pkg_low", "single_active_proc", "long_due_chain",
    ]))
    base = draw(normal_order_overrides())
    if pick == "very_small_pend":
        # designPendQtyHigh가 매우 작으면 step 9에서 매수 < 1 → DG108
        base["designPendQtyHigh"] = "0.5"
        base["designPendQtyLow"] = "0.1"
    elif pick == "exact_match_pkg_low":
        # designPendQtyHigh == pkgWgtLow
        base["pkgWgtLow"] = base["designPendQtyHigh"]
    elif pick == "single_active_proc":
        # 한 공정만 활성 (HR만)
        base["confirmedPlantCd"] = " K      "
    elif pick == "long_due_chain":
        # workDue가 정확히 내일
        base["workDue"] = (date.today() + timedelta(days=1)).isoformat()
    base["_boundary_kind"] = pick   # meta — case_builder description 에서 사용
    return base


@st.composite
def error_order_overrides(draw) -> dict:
    """DG001~005 중 하나가 실패하도록 강제."""
    fail_kind = draw(st.sampled_from(["DG001", "DG002", "DG003", "DG004", "DG005"]))
    base = draw(normal_order_overrides())
    if fail_kind == "DG001":
        base["stockCode"] = 1
    elif fail_kind == "DG002":
        base["orderWidth"] = "0"
    elif fail_kind == "DG003":
        # pkgWgtLow > pkgWgtHigh
        base["pkgWgtLow"] = "100"
        base["pkgWgtHigh"] = "10"
    elif fail_kind == "DG004":
        base["pkgWgtLow"] = "1000"
        base["pkgWgtHigh"] = "2000"
        base["designPendQtyHigh"] = "10"
    elif fail_kind == "DG005":
        # workDue 과거
        base["workDue"] = (date.today() - timedelta(days=1)).isoformat()
    base["_expected_dg"] = fail_kind  # meta — case_builder에서 expected에 사용
    return base


@st.composite
def performance_order_overrides(draw) -> dict:
    """대량 Slab이 나오는 케이스 — 큰 designPendQty + 작은 splitWgtHigh."""
    base = draw(normal_order_overrides())
    base["designPendQty"] = "10000"
    base["designPendQtyLow"] = "1000"
    base["designPendQtyHigh"] = "10000"
    base["pkgWgtLow"] = "1"
    base["pkgWgtHigh"] = "5"
    base["orderWgtLow"] = "1"
    base["orderWgtHigh"] = "5"
    return base


# ─── Strategy 디스패치 ──────────────────────────────────────────────


def strategy_for(case_type: CaseType):
    return {
        "normal": normal_order_overrides(),
        "boundary": boundary_order_overrides(),
        "error": error_order_overrides(),
        "performance": performance_order_overrides(),
    }[case_type]
