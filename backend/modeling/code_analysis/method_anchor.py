"""P14 (2026-04-26) — MethodAnchor : 메서드 본문 안의 매핑 anchor.

Anchor 7 종 (round1-code-schema §6 + v3.1 §1) :
    field          — class instance field 선언
    field_access   — method 안에서 instance field read/write/invoke
    param          — method parameter
    local          — method 안의 지역 변수 선언
    return         — return statement 의 expression
    branch         — if / switch / while / for / try 의 condition
    literal        — 매직 넘버 / 상수 문자열 / 정규식 등

`field` 는 class scope 라 별도 추출 (java_parser 의 _extract_field). 나머지 6 종은
method body 의 tree-sitter AST visitor 로 추출.

`MethodAnchor` 는 dataclass — Pydantic 안 쓰는 이유 : code_analysis 영역은
deterministic / no-network 이고 SQLite 직렬화 시 `dataclasses.asdict()` 로 충분.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class AnchorKind(StrEnum):
    FIELD = "field"
    FIELD_ACCESS = "field_access"
    PARAM = "param"
    LOCAL = "local"
    RETURN = "return"
    BRANCH = "branch"
    LITERAL = "literal"


@dataclass(frozen=True)
class MethodAnchor:
    """Method body 안의 single anchor.

    `locator` 는 사람-readable 위치 식별자 (UI 카드 헤더에 표시) :
        - param[hrTgtWidth]
        - local[slabLengthLow]
        - branch[if@line:50]
        - literal["DG107"@line:60]
        - field_access[this.castSpec.smCd@read@line:48]
        - return[@line:52]

    `extra` 는 anchor kind 별 부가 정보 :
        - branch    : {"statement_text": "x ≤ y && y ≤ z", "branch_kind": "if|switch|for|while|try"}
        - literal   : {"raw": "\"DG107\"", "literal_kind": "string|integer|float|boolean", "is_magic": True}
        - field_access : {"target_field_fqn": "EdgingService.castSpec", "access_kind": "read|write|invoke"}
        - local     : {"declared_type": "BigDecimal", "rhs_text": "max(...)"}
        - param     : {"declared_type": "BigDecimal", "position": 0}
        - return    : {"return_text": "s.getGroup()"}
    """
    method_fqn: str
    kind: AnchorKind
    locator: str
    line: int
    snippet: str          # AST 위치의 source text (≤120자, 잘라서)
    extra: dict[str, Any] = field(default_factory=dict)


__all__ = ("AnchorKind", "MethodAnchor")
