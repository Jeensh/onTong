"""Phase 7-E — Auto-PR 자바 방어 코드 자동 생성.

목적
----
샌드박스 시뮬에서 발견된 실패 케이스 (matches_expectation=False) 를 LLM 에 보내
"이 입력에서도 안 깨지도록 자바 방어 코드를 보강한 메서드" 를 생성받는다.

운영자는:
  1. 변경 영향 분석 / 샌드박스에서 실패 케이스 발견
  2. 「자바 방어 코드 자동 생성」 버튼 클릭
  3. LLM 이 unified diff + 패치된 메서드 + rationale 반환
  4. 사용자가 검토 후 GitHub PR 으로 활용 (현재는 텍스트 복사 단계)

Pipeline
--------
1. 실패 케이스 + 자바 메서드 (transpile.parser 의 extract_method 재사용) → LLM
2. Pydantic AI Agent + structured output (PatchSuggestion)
3. unified_diff 생성 (difflib)
4. LLM 미가용 시 deterministic fallback (실패 케이스를 주석으로 보존하는 stub 패치)

scenario_assistant.py / llm_transpile.py 의 LLM fallback 패턴 미러.
"""

from .suggester import (
    PatchSuggestion,
    AutoPRRequest,
    suggest_patch,
)

__all__ = [
    "PatchSuggestion",
    "AutoPRRequest",
    "suggest_patch",
]
