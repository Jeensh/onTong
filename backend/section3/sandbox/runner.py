"""격리된 Python subprocess 실행기.

원칙:
- LLM 이 생성한 코드를 직접 main process 에서 exec 하지 않는다.
- subprocess 로 venv 의 Python 실행 + stdin 으로 JSON input 전달 + stdout 으로 JSON 결과.
- timeout / stderr 캡처. 무한 루프 방지.

계약 (code_generator 와 일치):
- 코드는 stdin 에서 JSON 을 읽어 `run(inputs)` 호출 후 결과를 stdout 에 JSON 으로 출력.
- 성공 시 결과 dict, 실패 시 ok=False + error 메시지.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


def run_python(
    source: str,
    inputs: Optional[dict[str, Any]] = None,
    *,
    timeout: float = 10.0,
    python_executable: Optional[str] = None,
) -> dict[str, Any]:
    """격리 subprocess 에서 Python 코드 실행.

    Args:
        source: Python 소스 (`run(inputs) -> dict` 정의 + `if __name__ == "__main__"` 블록)
        inputs: stdin JSON 으로 전달될 dict (없으면 {})
        timeout: 초 단위
        python_executable: 명시 안 하면 sys.executable (현재 venv) 사용

    Returns:
        {
            "ok": bool,
            "result": dict | None,           # stdout 의 JSON parse
            "stdout": str,
            "stderr": str,
            "elapsed_sec": float,
            "error": str | None,
            "returncode": int,
        }
    """
    python = python_executable or sys.executable
    inputs_json = json.dumps(inputs or {})

    # 코드를 tempfile 로 저장 — error trace 가 line 번호 추적 가능하게
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", delete=False, encoding="utf-8"
    ) as tf:
        tf.write(source)
        script_path = tf.name

    start = time.monotonic()
    try:
        proc = subprocess.run(
            [python, script_path],
            input=inputs_json,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=_safe_env(),
        )
        elapsed = time.monotonic() - start
        ok = proc.returncode == 0

        result: dict[str, Any] | None = None
        parse_error: str | None = None
        if ok and proc.stdout.strip():
            try:
                result = json.loads(proc.stdout.strip().splitlines()[-1])
                # 마지막 line 만 JSON 으로 가정 — print 디버그 라인이 앞에 있어도 OK
            except json.JSONDecodeError as e:
                parse_error = f"stdout JSON 파싱 실패: {e}"
                ok = False

        return {
            "ok": ok,
            "result": result,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
            "elapsed_sec": round(elapsed, 4),
            "error": parse_error or (proc.stderr if not ok else None),
            "returncode": proc.returncode,
        }

    except subprocess.TimeoutExpired as e:
        return {
            "ok": False,
            "result": None,
            "stdout": e.stdout or "",
            "stderr": e.stderr or "",
            "elapsed_sec": timeout,
            "error": f"timeout after {timeout}s",
            "returncode": -1,
        }
    except Exception as e:
        return {
            "ok": False,
            "result": None,
            "stdout": "",
            "stderr": "",
            "elapsed_sec": time.monotonic() - start,
            "error": f"subprocess 실행 실패: {e}",
            "returncode": -2,
        }
    finally:
        try:
            os.unlink(script_path)
        except OSError:
            pass


def run_python_multi(
    source: str,
    test_cases: list[dict[str, Any]],
    *,
    timeout_per_case: float = 5.0,
) -> list[dict[str, Any]]:
    """여러 test_case 에 대해 순차 실행. 각 case 의 결과 반환.

    각 test_case 는 다음 shape 권장:
        { "case_id": str, "case_type": str, "input": dict, "expected_output": dict | None }
    """
    results: list[dict[str, Any]] = []
    for tc in test_cases:
        run_result = run_python(source, tc.get("input") or {}, timeout=timeout_per_case)
        results.append({
            "case_id": tc.get("case_id"),
            "case_type": tc.get("case_type"),
            "input": tc.get("input"),
            "expected_output": tc.get("expected_output"),
            "execution": run_result,
            "matched_expected": _matches_expected(
                run_result.get("result"), tc.get("expected_output")
            ),
        })
    return results


def _matches_expected(actual: Any, expected: Any) -> Optional[bool]:
    """expected_output 과 actual 의 핵심 필드 매칭 (None 이면 비교 안 함)."""
    if expected is None or actual is None:
        return None
    if not isinstance(expected, dict) or not isinstance(actual, dict):
        return None
    for k, v in expected.items():
        if k == "feasible" and "feasible" in actual:
            if bool(actual["feasible"]) != bool(v):
                return False
        # 그 외 필드는 syntactic 매칭 — 부동소수점 tolerance 는 추후 보강
        elif k in actual and actual[k] != v:
            return False
    return True


def _safe_env() -> dict[str, str]:
    """sandbox 환경변수 — 최소화 (PATH 만 유지)."""
    keep = {"PATH", "HOME", "LANG", "LC_ALL"}
    return {k: v for k, v in os.environ.items() if k in keep}


__all__ = ["run_python", "run_python_multi"]
