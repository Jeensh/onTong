"""Recipe 1 — Replace LLM test synthesis with W71 deterministic boundaries.

Section 3 의 sandbox 가 LLM 으로 normal/boundary/error 3 case 를 합성하는데:
    - 비결정적 (재현 불가)
    - LLM 이 "boundary" 라고 부르는 값이 실제 boundary 가 아닌 경우 많음
    - 빈 문자열, MAX_INT, 음수 0 같은 진짜 경계 누락
    - 같은 입력에 다른 결과

W71 은:
    - 결정적 (같은 action.params_json → 같은 fixture)
    - per-primitive boundary value seed (string: 6 / int: 5 / boolean: 2)
    - max_combinations=12 cap

이 recipe 는 production action 하나를 골라 fixture 가 어떻게 생성되는지 보여준다.
실행:
    .venv/bin/python toClaude/modeling/section4-verification/section3_handoff/usage-recipes/recipe-1-replace-llm-test-synthesis.py
"""
from __future__ import annotations

import sys
from pathlib import Path

# 프로젝트 루트를 path 에 추가
sys.path.insert(0, str(Path(__file__).resolve().parents[5]))

from backend.sim_v2.core.ontology.domain_layer.production_domain_loader import (
    load_actions,
)
from backend.sim_v2.core.verification.fixture_synthesizer import (
    synthesize_fixtures_for_action,
)
from backend.sim_v2.demos.uc10_production_inspector.run import (
    PRODUCTION_DB_PATH,
    open_readonly_session,
)


# Section 3 사이드 — 보통은 composer + transpiler 출력
DUMMY_PYTHON_SOURCE = (
    "def fail_(self, errorCode, message):\n"
    "    return {'ok': False, 'code': errorCode, 'msg': message}\n"
)
DUMMY_FUNCTION_NAME = "fail_"


def main() -> int:
    if not PRODUCTION_DB_PATH.exists():
        print(f"production DB not found at {PRODUCTION_DB_PATH}")
        return 1
    session = open_readonly_session()
    if session is None:
        return 1
    try:
        actions = load_actions(session, "slab-design-real-v2")
        target = next(a for a in actions if a.fqn == "action.scm.fail")

        report = synthesize_fixtures_for_action(
            session, target,
            function_name=DUMMY_FUNCTION_NAME,
            python_source=DUMMY_PYTHON_SOURCE,
            max_combinations=12,
        )

        print(f"=== action: {target.fqn}")
        print(f"params_json declares  : "
              f"{report.synthesizable_params} primitive + "
              f"{report.skipped_params} object_ref")
        print(f"fixtures generated    : {len(report.fixtures)}")
        print()
        print(f"각 fixture (총 {len(report.fixtures)}):")
        for fx in report.fixtures:
            args_pretty = ", ".join(repr(a) for a in fx.input_args[1:])
            print(f"  {fx.fixture_id:30s}  args=({args_pretty})")
        print()
        print(f"이 fixture 들을 Section 3 의 sandbox_agent 에서 LLM 합성 대신")
        print(f"그대로 BehaviorTwinRunner 에 넘기면 12 case 가 결정적으로 실행됨.")
        print(f"(다음 recipe-2 참조 — 부착할 Java baseline 까지 포함한 full loop.)")
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    sys.exit(main())
