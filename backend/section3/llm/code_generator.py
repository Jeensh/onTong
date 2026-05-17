"""ontology API 응답 → 실행 가능한 Python 코드 동적 합성.

원칙:
- modeling 의 simulate 응답 (test_cases / data_dependencies / ontology_trace / code_skeleton(JUnit))
  만 input. slab-design 의 hardcoded Python 일체 참조 0건.
- LLM 이 "변수 schema + Step 의미 + test_case input/expected_output" 만 보고 Python 합성.
- 출력 코드는 stdin 으로 JSON input 을 받고 stdout 으로 JSON output 을 내야 함
  (sandbox runner 와의 계약).
"""

from __future__ import annotations

from typing import Any

from backend.section3.llm.openai_client import LLMClient

SYSTEM_PROMPT = """당신은 제조 IT 시스템의 Python 코드 자동 합성기입니다.
주어지는 입력 (modeling 의 ontology trace + test_case 정의) 만으로 실행 가능한 Python
함수를 생성합니다.

# 절대 규칙
1. 외부 라이브러리 import 금지 (json, math 만 허용). pandas/numpy 금지 — sandbox 환경 가벼움.
2. modeling API 응답에 명시되지 않은 hardcoded 비즈니스 로직 추가 금지. 모르면 None 반환.
3. 출력 코드는 다음 시그니처를 가짐:
   ```
   import json, sys
   def run(inputs: dict) -> dict:
       ...
       return {"feasible": bool, "outputs": dict, "trace": list}
   if __name__ == "__main__":
       data = json.loads(sys.stdin.read())
       print(json.dumps(run(data), ensure_ascii=False))
   ```
4. test_case 의 expected_output 을 그대로 반환하지 말 것. 입력 변수를 사용해 실 계산을
   시도하고, ontology 가 명시한 valid_range / constraints 를 체크. 명시 안 됐으면 inputs 만
   echo + feasible=true.
5. 코드 외 텍스트 / 주석 외 문장 없이 순수 Python 코드만 출력.

응답은 ```python 또는 ``` 블록으로 감싸지 말고 raw Python 만 출력.
"""


def generate_python_from_modeling(
    modeling_result: dict[str, Any],
    *,
    intent_context: str = "",
    llm: LLMClient | None = None,
) -> str:
    """modeling.simulate / impact_analysis 응답 → Python 코드 string.

    Args:
        modeling_result: modeling 의 OntologyResponse.result dict
        intent_context: agent 가 추가 컨텍스트 제공 (예: "Step 1 의 두께 계산")
        llm: optional override

    Returns:
        실행 가능한 Python source string
    """
    if llm is None:
        from backend.section3.llm.openai_client import get_llm_client
        llm = get_llm_client()

    user_content = (
        f"context: {intent_context}\n\n"
        f"modeling_result (JSON):\n{_json_pretty(modeling_result)}\n\n"
        "위 정보만으로 위 시그니처를 따르는 Python 코드를 합성하세요.\n"
        "test_cases 의 input 변수명들을 함수가 받아들이고, expected_output 과 일관된\n"
        "결과를 시도. 모르는 부분은 None 또는 echo."
    )

    code = llm.chat(
        [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        temperature=0.1,
        max_tokens=1500,
    )

    # ```python ... ``` fence 가 포함된 경우 벗기기 (안전망)
    code = _strip_fence(code)
    return code


def _json_pretty(obj: Any, limit: int = 4000) -> str:
    import json
    s = json.dumps(obj, indent=2, ensure_ascii=False)
    if len(s) > limit:
        s = s[:limit] + "\n... (truncated)"
    return s


def _strip_fence(code: str) -> str:
    """```python ... ``` 또는 ``` ... ``` fence 제거."""
    lines = code.strip().splitlines()
    if not lines:
        return code
    if lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].startswith("```"):
        lines = lines[:-1]
    return "\n".join(lines)


__all__ = ["generate_python_from_modeling", "SYSTEM_PROMPT"]
