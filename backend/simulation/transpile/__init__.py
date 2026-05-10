"""Phase 7-D — Java→Python 자동 transpile 모듈.

목적
----
Section 3 의 sandbox step 16개는 사람(Claude)이 자바 원본을 보고 손으로 미러링한 것이다.
새 도메인의 자바 코드를 시뮬레이션 단계로 자동 편입하기 위해 다음을 자동화한다:

    1. tree-sitter (Java)  — 메서드 시그니처/본문/import/필드 추출
    2. LLM (Pydantic AI)   — 자바 메서드 → 파이썬 step 함수 작성
    3. 동치성 검증          — 같은 inputs 로 (a) 기존 미러 step (있으면) 또는
                              (b) LLM 이 만든 expected outputs 와 결과 비교
    4. 저장                 — sandbox/steps/<name>.py 또는 미리보기만

운영자 흐름은 frontend/src/components/simulation/TranspilePanel.tsx 참고.
"""

from .parser import JavaMethodInfo, extract_method, list_methods
from .llm_transpile import PythonStepDraft, transpile_method
from .equivalence import EquivalenceReport, shadow_compare

__all__ = [
    "JavaMethodInfo",
    "extract_method",
    "list_methods",
    "PythonStepDraft",
    "transpile_method",
    "EquivalenceReport",
    "shadow_compare",
]
