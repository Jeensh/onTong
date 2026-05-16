"""Recipe 2 — Synth + baseline 부착 + BehaviorTwinRunner end-to-end.

Section 3 sandbox 가 *Java 정답* 을 비교하려면 baseline 이 필요하다.
이 recipe 는 W73 의 JavaBaselineMap 을 수동 작성 → W71 synth → W73 attach
→ W59 BehaviorTwinRunner 까지의 full loop 를 4 case 합성 예제로 시연.

여기 쓰는 메서드는 self-contained Python (실제 production 코드 아님 —
Section 3 sandbox 에서는 composer + transpiler 출력이 들어감).

실행:
    .venv/bin/python toClaude/modeling/section4-verification/section3_handoff/usage-recipes/recipe-2-record-java-baseline.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[5]))

from backend.sim_v2.core.verification.behavior_twin_runner import (
    BehaviorFixture,
    BehaviorFixtureStore,
    BehaviorTwinRunner,
)
from backend.sim_v2.core.verification.engine import VerificationEngine
from backend.sim_v2.core.verification.java_oracle_adapter import (
    JavaBaselineEntry,
    JavaBaselineMap,
    attach_baselines,
)
from backend.sim_v2.core.verification.oracle import OracleRequest


# ─────────────────────────────────────────────────────────────────
# 0) Java 의 production 메서드라고 가정:
#       int addPositives(int a, int b) {
#           int x = a; if (x < 0) x = 0;
#           int y = b; if (y < 0) y = 0;
#           return x + y;
#       }
#    Section 3 transpiler 가 이걸 아래 Python 으로 번역한다고 보자.
# ─────────────────────────────────────────────────────────────────


PYTHON_SOURCE = (
    "def addPositives(self, a, b):\n"
    "    x = a\n"
    "    if x < 0:\n"
    "        x = 0\n"
    "    y = b\n"
    "    if y < 0:\n"
    "        y = 0\n"
    "    return x + y\n"
)


def main() -> int:
    # 1) W71-style synth fixture (여기서는 직접 작성하지만, 실 사용 시
    #    synthesize_fixtures_for_action 가 자동 생성)
    fixtures = []
    for i, (a, b) in enumerate([(1, 2), (-3, 5), (0, 0), (4, 4)]):
        fixtures.append(BehaviorFixture(
            fixture_id=f"addPositives#{i}",
            python_source=PYTHON_SOURCE,
            function_name="addPositives",
            input_args=(None, a, b),
            input_kwargs={},
            expected_output=None,           # ← baseline 부착 전, 비어 있음
        ))

    # 2) W73 — JavaBaselineMap (수동 annotation, recorded run, 또는 anchor-derived)
    baseline = JavaBaselineMap([
        JavaBaselineEntry("addPositives", (None, 1, 2),  3,
                          note="manual.2026-05-16"),
        JavaBaselineEntry("addPositives", (None, -3, 5), 5,
                          note="manual: a<0 → 0, b=5 → 5"),
        JavaBaselineEntry("addPositives", (None, 0, 0),  0),
        JavaBaselineEntry("addPositives", (None, 4, 4),  8),
    ])

    # 3) attach_baselines: synth fixture 의 expected_output 을 baseline 으로 채움
    attach = attach_baselines("addPositives", tuple(fixtures), baseline)
    print(f"매칭된 fixture : {len(attach.matched_fixtures)} / {attach.total_fixtures}")
    print(f"매칭 안 됨     : {attach.unmatched_count}")
    print()

    # 4) W59 BehaviorTwinRunner 으로 실행
    store  = BehaviorFixtureStore(list(attach.matched_fixtures))
    runner = BehaviorTwinRunner(store)
    engine = VerificationEngine(fixture_runner=runner, plugin="recipe2")
    req = OracleRequest(
        proposal_id="recipe2",
        fixture_subset=[f.fixture_id for f in attach.matched_fixtures],
    )
    result = engine.run_oracle(req)

    print(f"=== Behavioral verification results ===")
    print(f"aggregate    : {result.aggregate_status}")
    print()
    print(f"per-fixture:")
    print(f"  {'fixture':24s}  {'input':14s}  {'expected':10s}  {'actual':10s}  status")
    for fid in sorted(result.by_fixture.keys()):
        r  = result.by_fixture[fid]
        fx = store.get(fid)
        args_pretty = ", ".join(str(a) for a in fx.input_args[1:])
        print(f"  {fid:24s}  ({args_pretty:10s})  "
              f"{r.java_baseline_output!r:10}  "
              f"{r.python_proposal_output!r:10}  "
              f"{r.status}")
    print()
    print(f"이 흐름이 Section 3 sandbox 의 표 (expected_output 컬럼 포함) 에 그대로 들어감.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
