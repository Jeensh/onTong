"""Phase 7-E — Auto-PR 자바 방어 코드 자동 생성 테스트.

검증:
1. fallback suggest: LLM 미가용 시 stub 패치 생성
2. unified_diff 생성: 자바 코드 변경에 대한 diff 텍스트
3. 빈 failures 거부
4. extract_method + suggest 흐름 e2e
"""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.simulation.auto_pr.suggester import (
    AutoPRRequest,
    FailedCase,
    PatchSuggestion,
    make_unified_diff,
    suggest_patch,
)
from backend.simulation.transpile.parser import extract_method


PROJECT_ROOT = Path(__file__).resolve().parents[2]
THICKNESS_JAVA = (
    PROJECT_ROOT
    / "sample-repos"
    / "slab-design"
    / "slab-design-feature"
    / "src/main/java/com/example/slabdesign/feature/sd/process/working/action"
    / "SdThicknessAction.java"
)


# ─── unified diff ──────────────────────────────────────────────────


def test_unified_diff_changes_detected():
    original = "void execute() {\n    int x = 1;\n}\n"
    patched = "void execute() {\n    if (x < 0) return;\n    int x = 1;\n}\n"
    diff = make_unified_diff(original, patched)
    assert "if (x < 0) return;" in diff
    assert diff.startswith("---")  # unified diff 헤더


def test_unified_diff_identical_no_changes():
    src = "void execute() {\n    int x = 1;\n}\n"
    diff = make_unified_diff(src, src)
    # 동일하면 diff 텍스트가 비어있거나 헤더만 있음
    assert "+if" not in diff


# ─── fallback path ─────────────────────────────────────────────────


@pytest.mark.skipif(not THICKNESS_JAVA.exists(), reason="slab-design 자바 파일 없음")
@pytest.mark.asyncio
async def test_fallback_suggestion_produces_stub(monkeypatch):
    """LLM 비활성화 시 fallback stub 가 생성되는지."""
    monkeypatch.setenv("SIMULATION_DISABLE_LLM_AUTO_PR", "1")
    info = extract_method(THICKNESS_JAVA, "execute")
    assert info is not None

    failures = [
        FailedCase(
            case_id="boundary-001",
            description="확정공장 첫 글자가 공백 — DG104 expected",
            case_type="boundary",
            expected={"stage": "validate", "error_code": "DG104"},
            actual_output={"error": {"code": "DG101", "message": "PlantMapping 미정의"}},
        ),
    ]
    req = AutoPRRequest(info=info, failures=failures, prefer_llm=False)
    suggestion, diff = await suggest_patch(req)
    assert suggestion.method == "fallback"
    assert "Auto-PR fallback" in suggestion.patched_method
    assert "boundary-001" in suggestion.patched_method  # case_id 가 주석으로 보존
    assert suggestion.confidence < 0.5
    # diff 는 자바 텍스트 차이 (fallback 은 주석만 추가하지만 차이 발생)
    assert isinstance(diff, str)


@pytest.mark.skipif(not THICKNESS_JAVA.exists(), reason="slab-design 자바 파일 없음")
@pytest.mark.asyncio
async def test_fallback_multiple_failures_truncated(monkeypatch):
    """5건 초과 실패 케이스는 prompt limit 으로 잘리고 (+N건 더 있음) 표시."""
    monkeypatch.setenv("SIMULATION_DISABLE_LLM_AUTO_PR", "1")
    info = extract_method(THICKNESS_JAVA, "execute")
    assert info is not None

    failures = [
        FailedCase(
            case_id=f"f-{i:03d}",
            description=f"failure {i}",
            case_type="error",
            expected={"x": i},
            actual_output={"x": i + 1},
        )
        for i in range(8)
    ]
    req = AutoPRRequest(info=info, failures=failures, prefer_llm=False, max_failures_in_prompt=5)
    suggestion, _ = await suggest_patch(req)
    assert "+3건 더 있음" in suggestion.patched_method
    # 처음 5건은 주석에 포함
    for i in range(5):
        assert f"f-{i:03d}" in suggestion.patched_method


@pytest.mark.skipif(not THICKNESS_JAVA.exists(), reason="slab-design 자바 파일 없음")
@pytest.mark.asyncio
async def test_suggestion_includes_risk_notes(monkeypatch):
    monkeypatch.setenv("SIMULATION_DISABLE_LLM_AUTO_PR", "1")
    info = extract_method(THICKNESS_JAVA, "execute")
    assert info is not None
    failures = [
        FailedCase(
            case_id="x",
            description="d",
            case_type="error",
            expected={},
            actual_output={},
        )
    ]
    suggestion, _ = await suggest_patch(AutoPRRequest(info=info, failures=failures, prefer_llm=False))
    assert isinstance(suggestion.risk_notes, list)
    assert len(suggestion.risk_notes) >= 1


@pytest.mark.skipif(not THICKNESS_JAVA.exists(), reason="slab-design 자바 파일 없음")
@pytest.mark.asyncio
async def test_e2e_extract_then_suggest(monkeypatch):
    """parser 로 자바 메서드 추출 → suggest_patch → diff 생성 e2e."""
    monkeypatch.setenv("SIMULATION_DISABLE_LLM_AUTO_PR", "1")
    info = extract_method(THICKNESS_JAVA, "execute")
    assert info is not None
    failures = [
        FailedCase(
            case_id="e2e",
            description="end-to-end smoke",
            case_type="normal",
            expected={"stage": "ok"},
            actual_output={"error": {"code": "DG101"}},
        )
    ]
    suggestion, diff = await suggest_patch(AutoPRRequest(info=info, failures=failures, prefer_llm=False))
    assert isinstance(suggestion, PatchSuggestion)
    # patched_method 안에 메서드 시그니처가 있어야 함
    assert "execute" in suggestion.patched_method
    # diff 헤더에 클래스/메서드명
    assert "SdThicknessAction" in diff
