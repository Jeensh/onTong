"""Phase 16R — integrity_warning kind canonical 정의 (backend single source).

이전: `gate_hypothesis._compute_integrity_warnings` 가 6 개의 hardcoded
`"integrity_warning=KIND ..."` 문자열을 emit. frontend `WARNING_META` 가 manual
sync. 새 kind 추가 시 두 곳 + 문자열 format 매번 수동.

16R — canonical 정의:
  - `IntegrityWarningKind` Literal 타입 (mypy / static check)
  - `INTEGRITY_WARNING_KINDS` set (런타임 dispatch / dedupe)
  - `emit_warning(kind, detail)` helper — 통일된 "integrity_warning=KIND (DETAIL)" 포맷

신규 kind 추가 절차:
  1. 이 파일의 `IntegrityWarningKind` literal + `INTEGRITY_WARNING_KINDS` set 에 추가
  2. `gate_hypothesis._compute_integrity_warnings` 에 발화 분기 추가 (emit_warning 사용)
  3. `frontend/src/lib/section3/warning_meta.ts` `WARNING_META` 에 label/Icon/cls 추가
  4. `RED_KINDS` / `YELLOW_KINDS` 분류 결정

테스트 (`test_phase16r_integrity_warning_kinds.py`) 가:
  - emit_warning 포맷 검증
  - gate_hypothesis 코드 안의 모든 `integrity_warning=X` 가 set 에 등록됐는지 grep
"""
from __future__ import annotations

from typing import Final, Literal


IntegrityWarningKind = Literal[
    "body_unsupported_no_rule",
    "body_unsupported_rule_only",
    "no_strong_evidence",
    "cross_evidence_mismatch",
    "body_unsupported_alias_gap",
    "target_is_test",
]

# 런타임 dispatch / dedupe 용 set (frozenset 으로 immutable)
INTEGRITY_WARNING_KINDS: Final[frozenset[str]] = frozenset({
    "body_unsupported_no_rule",
    "body_unsupported_rule_only",
    "no_strong_evidence",
    "cross_evidence_mismatch",
    "body_unsupported_alias_gap",
    "target_is_test",
})


def emit_warning(kind: IntegrityWarningKind, detail: str) -> str:
    """통일된 integrity_warning 문자열 포맷.

    형식: ``integrity_warning=KIND (DETAIL)``

    frontend `parseIntegrityWarnings` 가 `integrity_warning=([a-z_]+)` regex 로
    kind 추출 → DETAIL 은 hover tooltip 용 free-text.
    """
    return f"integrity_warning={kind} ({detail})"


__all__ = [
    "INTEGRITY_WARNING_KINDS",
    "IntegrityWarningKind",
    "emit_warning",
]
