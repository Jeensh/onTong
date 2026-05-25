"""Phase 16T — ranking boost weights canonical 모듈.

이전: `gate_i.py` 의 module-level 상수로 흩어짐 (`_ROLE_BOOST` / `_PARENT_BOOST` /
`_CLASS_PATTERN_BOOST` / `_FQN_EXACT_BOOST` / `_NAME_TOKEN_BOOST` /
`_DECLARED_ON_TERM_BOOST` / `_DOMAIN_ANNOTATIONS`).

별도 모듈 분리 이유:
  - 미래 튜닝/실험: A/B 테스트, repo-specific override, 환경변수 주입 등
  - 가시성: ranking 정책을 한 곳에서 확인
  - 테스트 격리: weight 변경 시 gate_i 본체 변동 없이 검증

함수 동작은 변경되지 않음 (Phase 16T = 재구조화 only). 16T 이후 후속에서:
  - env var override (ONTONG_RANKING_BOOST_*) 적용 가능
  - profile (default / aggressive / safe) 선택 가능
"""
from __future__ import annotations


# ─────────────────────────────────────────────────────────────────────────────
# Role / parent_role boost (Phase 12 activation)
# ─────────────────────────────────────────────────────────────────────────────


ROLE_BOOST: dict[str, float] = {
    "business": 5.0,
    "adapter":  -1.0,
    "helper":   -3.0,
    "unknown":  0.0,
}

PARENT_ROLE_BOOST: dict[str, float] = {
    "domain":    3.0,
    "framework": -1.0,
    "infra":     -2.0,
    "unknown":   0.0,
}


# ─────────────────────────────────────────────────────────────────────────────
# 도메인 annotation 인지 — @Service/@Component/@Transactional/@Repository
# ─────────────────────────────────────────────────────────────────────────────


DOMAIN_ANNOTATIONS: tuple[str, ...] = (
    "@Service", "@Component", "@Transactional", "@Repository",
)
DOMAIN_ANNOTATION_BOOST: float = 2.0


# ─────────────────────────────────────────────────────────────────────────────
# 클래스 FQN substring 패턴 — domain action 가산, helper 감산
# ─────────────────────────────────────────────────────────────────────────────


CLASS_PATTERN_BOOST: list[tuple[str, float]] = [
    (".action.",     6.0),    # *.action.Sd*Action — 도메인 액션 패키지
    (".validator.",  4.0),
    (".service.",    3.0),
    (".wrapper.",   -3.0),    # *.wrapper.ValidationResult — 헬퍼 패키지
    (".util.",      -3.0),
    (".dto.",       -4.0),
    ("result",      -2.0),    # *Result 클래스
]


# ─────────────────────────────────────────────────────────────────────────────
# 사용자 query 와의 일치 boost
# ─────────────────────────────────────────────────────────────────────────────


FQN_EXACT_BOOST: float = 15.0   # 사용자가 FQN 직접 명시 (`Class.method`)
NAME_TOKEN_BOOST: float = 4.0   # 의미 있는 단어 (4 자+) 가 fqn 에 substring
DECLARED_ON_TERM_BOOST: float = 10.0  # Phase 14E — declared_on_term × query alias 매칭


__all__ = [
    "CLASS_PATTERN_BOOST",
    "DECLARED_ON_TERM_BOOST",
    "DOMAIN_ANNOTATIONS",
    "DOMAIN_ANNOTATION_BOOST",
    "FQN_EXACT_BOOST",
    "NAME_TOKEN_BOOST",
    "PARENT_ROLE_BOOST",
    "ROLE_BOOST",
]
