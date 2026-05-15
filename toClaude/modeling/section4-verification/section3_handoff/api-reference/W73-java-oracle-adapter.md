# W73 · Java Oracle Adapter — Baseline 부착 layer

> **What:** `(action_fqn, input_args) → expected_output` 매핑을 따로 관리, W71 합성 fixture 에 부착.
>
> **Why for Section 3:** Section 3 sandbox 는 `{"ok": true, "result": 0.95}` 만 반환 — *0.95 가 진짜 Java 와 같은지* 검증 못함. W73 으로 baseline 을 명시적으로 부착하면 W59 BehaviorTwinRunner 가 PASS/FAIL_OUTPUT 까지 surface.

## 1. Import

```python
from backend.sim_v2.core.verification.java_oracle_adapter import (
    JavaBaselineEntry,               # 단일 annotation
    JavaBaselineMap,                 # 카탈로그
    attach_baselines,                # synth fixture + baseline → matched fixture
    BaselineAttachmentReport,        # 부착 결과
)
```

## 2. 데이터 모델

```python
@dataclass(frozen=True)
class JavaBaselineEntry:
    action_fqn:      str               # e.g. "action.scm.product.cumulative_productivity"
    input_args:      tuple[Any, ...]   # synth fixture 와 동일 형태 (self, *args)
    expected_output: Any               # Java 측 정답
    note:            str = ""          # 제공처 (e.g. "manual.2026-05-16" / "recorded.run.42")
```

## 3. Map 사용

```python
m = JavaBaselineMap([
    # ProductivityService.cumulativeProductivity 의 정답들
    JavaBaselineEntry(
        action_fqn="action.scm.product.cumulative_productivity",
        input_args=(None, "ABC", "01", None, None, None, None),
        expected_output=0.95,
        note="anchor DEFAULT_PRODUCTIVITY=0.95, length<8 fallback",
    ),
    JavaBaselineEntry(
        action_fqn="action.scm.product.cumulative_productivity",
        input_args=(None, "ABCDEFGH", "01", "P01", "GR1", "PR1", "C001"),
        expected_output=0.87,
        note="length=8 정상 lookup 경로",
    ),
])

# fixture 의 input_args 와 매칭하면 (자동 list/dict normalize)
entry = m.lookup(
    "action.scm.product.cumulative_productivity",
    (None, "ABC", "01", None, None, None, None),
)
# → JavaBaselineEntry(...)
```

## 4. attach_baselines — 메인 API

```python
from backend.sim_v2.core.verification.fixture_synthesizer import (
    synthesize_fixtures_for_action,
)
from backend.sim_v2.core.verification.java_oracle_adapter import (
    JavaBaselineMap, attach_baselines,
)

# 1) 합성
report = synthesize_fixtures_for_action(
    session, action, function_name=fn, python_source=src,
)
# 2) baseline 매칭 + 부착
attach = attach_baselines(
    action.fqn,
    report.fixtures,
    baseline_map,
)
# attach.matched_fixtures: tuple[BehaviorFixture, ...]  ← expected_output 채워짐
# attach.total_fixtures:   12
# attach.unmatched_count:  10   ← baseline 없는 fixture 는 *drop*
# attach.match_rate:       0.16
```

> 매칭 안 된 fixture 는 drop. W59 에 null-baseline 을 그대로 넘기면 모두 FAIL_OUTPUT 으로 표시되어 노이즈 → drop 으로 깔끔히 처리.

## 5. Section 3 의 anchor_locator 와 통합

Section 3 보고서에서 anchor 가 *코드 상 default 상수* 추출에 쓰임. baseline 도 같은 anchor 데이터 소스로 합성 가능:

```python
# (a) anchor_locator 가 "DEFAULT_PRODUCTIVITY = 0.95" 면
#     → 그 메서드의 fallback 출력은 0.95 라고 가정
# (b) call-sites 데이터에서 호출자 측 expected output 추출 (가능 시)
# (c) business-rules.statement 에서 invariant 추출 ("정상 범위: 0.5 ≤ p ≤ 1.0")
#     → fixture 의 output 이 이 범위 안에 있는지 *간이* invariant
```

3 가지 source 모두 W73 의 `JavaBaselineEntry` 로 변환 가능.

## 6. Baseline source 3 종

| Source | 비용 | 신뢰도 | 적용 |
| --- | --- | --- | --- |
| **manual annotation** | 높음 (사람이 case 별 작성) | 매우 높음 | 핵심 메서드 ~10건 |
| **JVM record/replay** (AspectJ 등 future W76) | 중간 (1 회 setup) | 높음 | 전수 가능 |
| **derived from anchor / rule** | 낮음 (자동) | 중간 (case 가 anchor 와 일치할 때만) | 보강 |

Section 3 가 가장 빠르게 깔 수 있는 것은 **derived from anchor**. UC39 의 `cumulativeProductivity → 0.95` 가 정확히 이 경로.

## 7. Section 3 sandbox 확장 예시

```python
# Section 3 의 sandbox_agent.py 안에서
from backend.sim_v2.core.verification.fixture_synthesizer import (
    synthesize_fixtures_for_action,
)
from backend.sim_v2.core.verification.java_oracle_adapter import (
    JavaBaselineMap, JavaBaselineEntry, attach_baselines,
)
from backend.sim_v2.core.verification.behavior_twin_runner import (
    BehaviorFixtureStore, BehaviorTwinRunner,
)

# 0) anchor 에서 baseline derive
anchor_baseline = derive_baseline_from_anchors(action, anchors)  # section3 helper
baseline_map = JavaBaselineMap(anchor_baseline)

# 1) synth
report = synthesize_fixtures_for_action(session, action, ...)

# 2) attach
attach = attach_baselines(action.fqn, report.fixtures, baseline_map)

# 3) run
store = BehaviorFixtureStore(list(attach.matched_fixtures))
runner = BehaviorTwinRunner(store)

# 4) UI 결과
yield {
    "matched":   attach.matched_fixtures.__len__(),
    "unmatched": attach.unmatched_count,
    "results":   [runner.run_fixture(f.fixture_id, plugin="section3", apply_diffs={})
                  for f in attach.matched_fixtures],
}
```

## 8. Section 3 chat 의 *expected vs actual* 표시 강화

현재 Section 3 simulate 결과는 `result: 0.95` 만. W73 결합 시:

```
case            input                                  expected  actual  status
normal          ("ABC","01",None,None,None,None)        0.95      0.95    ✓ PASS
boundary        ("","01",None,None,None,None)           0.95      0.95    ✓ PASS
length=10       ("ABCDEFGHIJ","01","P01","GR1","PR1","C001")  0.87     0.95   ✗ FAIL_OUTPUT
```

마지막 case 는 *진짜* 시맨틱 드리프트 — Java 측 lookup 결과와 다름. Section 3 가 이런 행을 surface 하려면 baseline 부착이 prerequisite.

## 9. UC39 Part A — 합성 pipeline proof

`uc39_b_level_capstone` 의 Part A 는 W73 의 가장 작은 정상 동작 데모:

```
4 fixture (None,1,2)/(None,-3,5)/(None,0,0)/(None,4,4)
       ↓ JavaBaselineMap 부착 → expected 3/5/0/8
       ↓ BehaviorTwinRunner
       PASS / PASS / PASS / PASS    ← 4/4 behavioral PASS
```

전체 흐름은 [recipe-2-record-java-baseline.py](../usage-recipes/recipe-2-record-java-baseline.py) 참조.

## 10. 한계

- **input_args normalization** — list/dict 는 hashable key 로 변환되지만 *깊은 동등성*만 매칭. fixture 의 자료형이 baseline 작성 시점과 같아야 함 (e.g., `int 1` vs `Decimal("1")` 다른 key).
- **action_fqn 스코프** — 매핑이 (action, args) pair. 같은 args 가 다른 action 에 쓰이면 별도 entry 필요. (대부분 의도된 동작.)
- **인자 형식 변경에 취약** — synth fixture 의 self placeholder (`None`) 변경 시 baseline 도 갱신 필요. 매뉴얼 annotation 의 비용.

## 11. 관련 파일

| 파일 | 역할 |
| --- | --- |
| `backend/sim_v2/core/verification/java_oracle_adapter.py` | 메인 구현 |
| `backend/sim_v2/tests/core/verification/test_w73_java_oracle_adapter.py` | 10 unit test |
| `backend/sim_v2/demos/uc39_b_level_capstone/run.py` | Part A 합성 + Part B production gap |
