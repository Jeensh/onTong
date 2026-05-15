"""Recipe 3 — W72 baseline-free invariant survey on a method.

Section 3 의 chat 분기에서 자연어 → fqn 변환 실패 → [LOW] fallback 으로
끝나는 경우가 많다. 이때 *왜 [LOW] 인지* 의 구체 진단이 필요한데, W72 의
invariant 결과가 정확히 그 진단을 제공:

    FAIL_RETURN_TYPE        → declared return 과 다른 type
    FAIL_UNEXPECTED_THROW   → 메서드가 throw (sandbox dependency 누락 / null deref)
    FAIL_NONDETERMINISTIC   → 외부 상태 의존 (time/random/global mutation)
    ERROR                   → compile 자체 실패 → translator gap

이 recipe 는 4 가지 메서드 (clean / throws / type-mismatch / compile-fail) 에
대해 W72 를 돌려 각 진단이 어떻게 surface 되는지 보여준다.

실행:
    .venv/bin/python toClaude/modeling/section4-verification/section3_handoff/usage-recipes/recipe-3-run-invariant-survey.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[5]))

from backend.sim_v2.core.verification.behavior_twin_runner import BehaviorFixture
from backend.sim_v2.core.verification.twin_invariants import (
    TwinInvariantRunner,
    run_invariants_for_fixtures,
)


CLEAN_SRC = (
    "def addPositives(self, a, b):\n"
    "    x = a if a >= 0 else 0\n"
    "    y = b if b >= 0 else 0\n"
    "    return x + y\n"
)

THROWS_SRC = (
    "def boom(self, x):\n"
    "    raise ValueError('null deref')\n"
)

TYPE_MISMATCH_SRC = (
    "def greet(self, name):\n"
    "    return 'hi ' + name\n"
)

SYNTAX_FAIL_SRC = (
    "def whoops(self, x):\n"
    "    return ! not valid !\n"
)


def _fx(fid: str, src: str, fn: str, args: tuple) -> BehaviorFixture:
    return BehaviorFixture(
        fixture_id=fid,
        python_source=src,
        function_name=fn,
        input_args=args,
        input_kwargs={},
        expected_output=None,
    )


def main() -> int:
    cases = [
        ("clean.add",      CLEAN_SRC,         "addPositives", (None, 1, 2),
         "int", (), "PASS expected"),
        ("throws.boom",    THROWS_SRC,        "boom",         (None, 99),
         "int", (), "FAIL_UNEXPECTED_THROW expected — sandbox dep / null deref"),
        ("throws.allowed", THROWS_SRC,        "boom",         (None, 99),
         "int", ("ValueError",),
         "PASS expected — allowed_exceptions tuple 에 포함"),
        ("type.mismatch",  TYPE_MISMATCH_SRC, "greet",        (None, "world"),
         "int", (), "FAIL_RETURN_TYPE expected — string 반환 vs declared int"),
        ("compile.fail",   SYNTAX_FAIL_SRC,   "whoops",       (None, 1),
         "int", (), "ERROR expected — syntax broken"),
    ]

    print(f"{'fixture':22s}  {'declared':10s}  {'status':24s}  comment")
    for fid, src, fn, args, declared, allowed, comment in cases:
        runner = TwinInvariantRunner(
            declared_return=declared,
            allowed_exceptions=allowed,
        )
        r = runner.check(_fx(fid, src, fn, args))
        print(f"{fid:22s}  {declared:10s}  {r.status:24s}  {comment}")
        if r.error:
            print(f"  └ error : {r.error.splitlines()[0][:100]}")

    print()
    print("Section 3 의 chat impact 분기에서 [LOW] fallback 표시할 때,")
    print("위 4 가지 status 중 하나를 surface 하면 사용자가 *왜 [LOW]* 인지 알 수 있음.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
