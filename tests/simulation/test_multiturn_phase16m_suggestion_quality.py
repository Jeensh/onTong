"""Phase 16M — suggestion chip quality 보강.

14C `_fetch_suggestions` 라이브 진단 이슈:
  1. 사용자가 이미 친 토큰이 그대로 suggestion 1순위 (e.g., '주문' → '주문, 통합 주문, ...')
     — 정보 없음. 이미 알고 친 단어.
  2. generic Korean 동사 ("검증", "실행") 가 무관 도메인 dominate
     — e.g., '주문 검증' → 모두 ValidationResult 관련 (주문 도메인 X)

fix:
  (a) tokens 와 정확히 같은 (lowercase) candidate 는 suggestion 에서 제외
  (b) generic Korean 동사 stopword 필터 (검증/실행/처리/확인/조회/검사/수행/갱신/시뮬/영향)
"""
from __future__ import annotations

import pytest

from backend.modeling.persistence import database as db_mod


@pytest.fixture
def fresh_db(tmp_path, monkeypatch):
    db_path = tmp_path / "phase16m.db"
    monkeypatch.setenv("ONTONG_DB_PATH", str(db_path))
    db_mod.reset_engine_for_tests()

    from backend.modeling.code_layer import orm as _code_orm  # noqa: F401
    from backend.modeling.domain_layer import orm as _domain_orm  # noqa: F401
    from backend.modeling.mapping_layer import orm as _mapping_orm  # noqa: F401
    from backend.modeling.view_layer import orm as _view_orm  # noqa: F401
    from backend.application.authoring import orm as _authoring_orm  # noqa: F401
    from backend.section3.agents.multiturn import orm as _multiturn_orm  # noqa: F401

    db_mod.bootstrap_database()
    yield db_path
    db_mod.reset_engine_for_tests()


def _seed_term(*, fqn: str, label: str, aliases_json: str, repo_id: str = "r"):
    from backend.modeling.persistence.database import session_scope
    from backend.modeling.domain_layer.orm import BusinessTermRow
    with session_scope() as s:
        s.add(BusinessTermRow(
            fqn=fqn,
            label=label,
            aliases_json=aliases_json,
            kind="atomic",
            domain="scm",
            description="",
            confirmed=True,
            repo_id=repo_id,
            source="user",
        ))


# ─────────────────────────────────────────────────────────────────────────────
# (a) 사용자가 친 토큰과 정확히 같은 candidate 는 surface 안 함
# ─────────────────────────────────────────────────────────────────────────────


def test_query_token_not_in_suggestions(fresh_db) -> None:
    """'주문' query → suggestions 에 '주문' 자체는 없어야. aliases 만."""
    from backend.section3.agents.multiturn.gate_i import _fetch_suggestions

    _seed_term(
        fqn="term.scm.order",
        label="주문",
        aliases_json='["통합 주문", "Order", "SDOrderEntity"]',
    )
    s = _fetch_suggestions(query="주문", search_terms=["주문"], repo_id="r")
    assert "주문" not in s, f"query 와 동일 토큰은 suggestions 에서 제외. got={s}"
    # aliases 는 surface
    assert any(a in s for a in ["통합 주문", "Order", "SDOrderEntity"])


def test_case_insensitive_query_token_excluded(fresh_db) -> None:
    """query token 'thickness' → suggestions 에 'Thickness' / 'THICKNESS' 도 제외."""
    from backend.section3.agents.multiturn.gate_i import _fetch_suggestions

    _seed_term(
        fqn="term.scm.thickness",
        label="두께",
        aliases_json='["thickness", "Thickness", "THICKNESS", "thk"]',
    )
    s = _fetch_suggestions(
        query="thickness", search_terms=["thickness"], repo_id="r",
    )
    # 케이스 다른 동의어도 제외 (이미 사용자가 친 단어)
    lowered = {x.lower() for x in s}
    assert "thickness" not in lowered, f"case-insensitive 제외. got={s}"


# ─────────────────────────────────────────────────────────────────────────────
# (b) generic Korean 동사 stopword 필터
# ─────────────────────────────────────────────────────────────────────────────


def test_korean_verb_stopword_filtered(fresh_db) -> None:
    """'주문 검증' → '검증' 이 noise 추천 막아야. 주문 관련만 surface."""
    from backend.section3.agents.multiturn.gate_i import _fetch_suggestions

    _seed_term(
        fqn="term.scm.order",
        label="주문",
        aliases_json='["통합 주문", "Order"]',
    )
    _seed_term(
        fqn="term.scm.validation_result",
        label="검증결과",
        aliases_json='["검증 결과", "ValidationResult"]',
    )
    s = _fetch_suggestions(
        query="주문 검증", search_terms=["주문", "검증"], repo_id="r",
    )
    # 검증 stopword 라서 검증결과 추천 안 와야. 주문 관련만.
    assert not any("검증" in x for x in s), (
        f"검증 stopword 가 noise 차단. got={s}"
    )
    assert any(x in s for x in ["통합 주문", "Order"])


def test_all_stopwords_returns_empty(fresh_db) -> None:
    """모든 토큰이 stopword → 빈 결과 (graceful)."""
    from backend.section3.agents.multiturn.gate_i import _fetch_suggestions

    _seed_term(
        fqn="term.scm.validation_result",
        label="검증결과",
        aliases_json='["ValidationResult"]',
    )
    s = _fetch_suggestions(
        query="검증 처리 실행", search_terms=["검증", "처리", "실행"], repo_id="r",
    )
    assert s == [], f"all stopwords → empty. got={s}"


def test_stopword_set_covers_common_verbs(fresh_db) -> None:
    """검증/실행/처리/확인/조회/검사/수행/갱신/시뮬/영향 모두 stopword."""
    from backend.section3.agents.multiturn import gate_i
    expected = {
        "검증", "실행", "처리", "확인", "조회", "검사", "수행", "갱신",
        "시뮬", "영향",
    }
    assert expected.issubset(gate_i._KOREAN_QUERY_STOPWORDS), (
        f"stopword set 누락. expected={expected} got={gate_i._KOREAN_QUERY_STOPWORDS}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# (c) backward compat — 일반 case 동작 유지
# ─────────────────────────────────────────────────────────────────────────────


def test_no_match_still_empty(fresh_db) -> None:
    from backend.section3.agents.multiturn.gate_i import _fetch_suggestions
    assert _fetch_suggestions(query="zzz", search_terms=["zzz"], repo_id="r") == []


def test_non_stopword_token_still_works(fresh_db) -> None:
    """generic 토큰 외엔 기존 동작."""
    from backend.section3.agents.multiturn.gate_i import _fetch_suggestions

    _seed_term(
        fqn="term.scm.edging_group",
        label="엣징그룹",
        aliases_json='["EDGING_GROUP", "EdgingGroupEntity"]',
    )
    s = _fetch_suggestions(query="엣징", search_terms=["엣징"], repo_id="r")
    assert len(s) >= 1
    # 엣징 자체는 query 와 정확 매칭이 아니므로 (label="엣징그룹") 포함 OK
    assert any("EDGING" in x or "엣징그룹" in x for x in s)
