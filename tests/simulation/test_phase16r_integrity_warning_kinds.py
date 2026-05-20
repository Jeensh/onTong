"""Phase 16R — integrity_warning kind canonical 검증.

backend `INTEGRITY_WARNING_KINDS` set + `emit_warning` 헬퍼 도입.
이 테스트는:
  - emit_warning 포맷 ("integrity_warning=KIND (DETAIL)") 검증
  - gate_hypothesis.py 가 emit_warning 만 쓰는지 (raw f-string 사용 X) 검증
  - INTEGRITY_WARNING_KINDS set 와 frontend WARNING_META.ts 의 kind 동기화 검증
"""
from __future__ import annotations

import re
from pathlib import Path

from backend.section3.agents.multiturn.integrity_warning_kinds import (
    INTEGRITY_WARNING_KINDS, emit_warning,
)


# ─────────────────────────────────────────────────────────────────────────────
# emit_warning 포맷
# ─────────────────────────────────────────────────────────────────────────────


def test_emit_warning_format() -> None:
    s = emit_warning("target_is_test", "target=X.Foo")
    assert s == "integrity_warning=target_is_test (target=X.Foo)"


def test_emit_warning_all_kinds_parseable() -> None:
    """모든 kind 의 결과가 frontend 의 regex (`integrity_warning=([a-z_]+)`) 로 추출 가능."""
    pat = re.compile(r"integrity_warning=([a-z_]+)")
    for k in INTEGRITY_WARNING_KINDS:
        s = emit_warning(k, "detail")  # type: ignore[arg-type]
        m = pat.search(s)
        assert m is not None, f"{k}: parse fail. s={s!r}"
        assert m.group(1) == k


# ─────────────────────────────────────────────────────────────────────────────
# gate_hypothesis.py 의 emit 사이트 모두 canonical kinds 안인지 검증
# ─────────────────────────────────────────────────────────────────────────────


def test_gate_hypothesis_only_emits_canonical_kinds() -> None:
    """gate_hypothesis.py 의 모든 `integrity_warning=X` 가 set 에 등록됐어야."""
    src = Path("backend/section3/agents/multiturn/gate_hypothesis.py").read_text()
    pat = re.compile(r'"?integrity_warning=([a-z_]+)')
    emitted = set(pat.findall(src))
    # 일부 substring match (e.g., 'integrity_warning=body_unsupported_no_rule')
    # 는 이미 set 에 있어야 (drift 차단)
    unknown = emitted - INTEGRITY_WARNING_KINDS
    assert not unknown, f"gate_hypothesis.py 에 등록되지 않은 kind: {unknown}"


def test_gate_hypothesis_uses_emit_warning_only() -> None:
    """gate_hypothesis.py 가 raw `"integrity_warning=...` 직접 f-string 으로 emit 하지 않도록.

    (찾으면 emit_warning helper 로 마이그레이션 필요 — 16R refactor 회귀 방지.)
    """
    src = Path("backend/section3/agents/multiturn/gate_hypothesis.py").read_text()
    # `"integrity_warning=...` 패턴 검색. 단 emit_warning 함수 자체의 f-string 은 OK
    # 이 모듈은 helper 만 사용하니 raw 사용은 0 이어야.
    raw_pattern = re.compile(r'"integrity_warning=')
    matches = raw_pattern.findall(src)
    assert not matches, (
        f"gate_hypothesis.py 가 raw integrity_warning 문자열 {len(matches)} 회 사용 — "
        "emit_warning(kind, detail) 헬퍼로 마이그레이션 필요"
    )


# ─────────────────────────────────────────────────────────────────────────────
# frontend WARNING_META.ts 의 키 set 과 일치 (cross-language contract)
# ─────────────────────────────────────────────────────────────────────────────


def test_frontend_warning_meta_kinds_match_backend() -> None:
    """frontend `WARNING_META` 의 key set 이 backend INTEGRITY_WARNING_KINDS 와 일치.

    drift 시 새 kind 가 frontend 에서 unknown-gray 칩으로 fallback 되거나, frontend 만
    선반영된 kind 가 backend 미발화로 dead 가 됨. 양쪽 sync 강제.
    """
    ts_src = Path(
        "frontend/src/lib/section3/warning_meta.ts",
    ).read_text()
    # WARNING_META 블록의 키들 추출. 형식:
    #   target_is_test: { ... },
    # 사이에 라인 첫 글자가 알파벳/언더스코어로 시작.
    # 블록은 `export const WARNING_META: ... = { ... };` 안
    m = re.search(
        r"export const WARNING_META: [^=]+=\s*\{(.*?)\};",
        ts_src,
        re.DOTALL,
    )
    assert m is not None, "WARNING_META 블록 파싱 실패"
    block = m.group(1)
    key_pat = re.compile(r"^\s*([a-z_]+):\s*\{", re.MULTILINE)
    frontend_kinds = set(key_pat.findall(block))

    assert frontend_kinds == INTEGRITY_WARNING_KINDS, (
        f"frontend ↔ backend kind set drift\n"
        f"  frontend only: {frontend_kinds - INTEGRITY_WARNING_KINDS}\n"
        f"  backend only:  {INTEGRITY_WARNING_KINDS - frontend_kinds}"
    )
