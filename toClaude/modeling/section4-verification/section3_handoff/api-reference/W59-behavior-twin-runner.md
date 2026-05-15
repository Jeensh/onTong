# W59 · BehaviorTwinRunner — Sandbox subprocess 대안

> **What:** Translated Python source 를 *in-process* safe exec 으로 실행, Java baseline 과 결과 비교.
>
> **Why for Section 3:** 현재 Section 3 의 sandbox 가 subprocess + JSON stdin/stdout. 이건 격리는 강하지만 (a) 1 case 마다 fork 비용, (b) baseline 비교가 LLM 응답에 의존, (c) trace 캡처 불가. W59 가 셋 다 해결.

## 1. Import

```python
from backend.sim_v2.core.verification.behavior_twin_runner import (
    BehaviorFixture,         # 입력 + expected output 모델
    BehaviorFixtureStore,    # fixture_id → fixture 저장소
    BehaviorTwinRunner,      # FixtureRunner 구현
    compare_outputs,         # 수동 비교 helper (tolerance 지원)
    _safe_globals,           # 안전한 sandbox globals
)
```

## 2. 핵심 데이터 모델

```python
@dataclass(frozen=True)
class BehaviorFixture:
    fixture_id:      str                   # 고유 ID (e.g. "addPos.both_pos")
    python_source:   str                   # Java→Python translated source
    function_name:   str                   # 호출할 def 이름
    input_args:      tuple[Any, ...]       # (self_or_None, *args)
    input_kwargs:    Mapping[str, Any]
    expected_output: Any                   # Java baseline output (없으면 None)
    tolerance:       float = 0.0           # 0 = exact, >0 = numeric tol
    expected_trace_events: tuple[...] | None = None    # W60 trace 비교
```

`expected_output=None` 일 때는 [W73 JavaBaselineMap](./../usage-recipes/recipe-2-record-java-baseline.py) 를 통해 부착하거나, [W72 invariants](./W72-twin-invariants.md) 로 baseline-free 검증.

## 3. 메인 API

```python
runner = BehaviorTwinRunner(store)
result = runner.run_fixture(
    fixture_id="my.test.1",
    plugin="section3.sandbox",
    apply_diffs={},        # proposal hook (Section 3 에서는 그냥 {})
)
# result.status: "PASS" / "FAIL_OUTPUT" / "FAIL_TRACE" / "ERROR"
# result.python_proposal_output: actual return value
# result.output_diff.summary: "match" or "diverge: ..."
```

## 4. Status 분류

| Status | 의미 |
| --- | --- |
| `PASS` | output ≡ baseline (tolerance 내) |
| `FAIL_OUTPUT` | output ≠ baseline — *진짜* 시맨틱 드리프트 |
| `FAIL_TRACE` | output 은 같지만 trace 가 달라짐 (process drift) |
| `ERROR` | twin 이 compile/runtime exception → 번역 실패 또는 sandbox dep 누락 |

> `FAIL_OUTPUT` 이 `FAIL_TRACE` 를 dominate. contract violation > process drift.

## 5. 비교 helper — tolerance

```python
from decimal import Decimal
from backend.sim_v2.core.verification.behavior_twin_runner import compare_outputs

# Decimal vs float 자동 coerce, list/tuple/dict 재귀
diff = compare_outputs(Decimal("0.95"), 0.95, tolerance=1e-9)
assert diff.is_equivalent       # True

diff = compare_outputs([1, 2, 3], [1, 2, 4])
diff.summary    # "diverge: [2]: 3 != 4"
```

## 6. Sandbox globals — Section 3 의 anchor prelude 와 통합

현재 sim_v2 의 `_safe_globals()` (line 181-203):

```python
{
    "__builtins__": { abs, min, max, sum, len, range, round, sorted, ...,
                      ValueError, TypeError, ...,
                      "print": lambda *a, **kw: None },  # silent print
    "Decimal":   Decimal,
    "getcontext": getcontext,
    "math":      math,
}
```

Section 3 의 `DEFAULT_PRODUCTIVITY = 0.95` 같은 anchor prelude 를 부착하려면:

```python
import backend.sim_v2.core.verification.behavior_twin_runner as runner_mod

def safe_globals_with_anchors(anchor_dict: dict) -> dict:
    g = runner_mod._safe_globals()
    g.update(anchor_dict)
    return g

# 사용 전에 monkeypatch
runner_mod._safe_globals = lambda: safe_globals_with_anchors({
    "DEFAULT_PRODUCTIVITY": 0.95,    # from anchor_locator regex
    "INVERSE_UNIT":         Decimal("0.001"),
})
```

→ Section 3 가 anchor 1건만 우회한 기법 → 임의의 module-level const 도 주입 가능.

## 7. Section 3 의 expected_output 검증 빈자리 채우기

Section 3 sandbox 의 현재 output:

```json
{"ok": true, "result": 0.95, "elapsed_sec": 0.012}
```

`result` 가 *Java 와 같은지* 검증 안 됨. W59 로 교체하면:

```python
from backend.sim_v2.core.verification.behavior_twin_runner import (
    BehaviorFixture, BehaviorFixtureStore, BehaviorTwinRunner,
)

fixture = BehaviorFixture(
    fixture_id="cumulativeProductivity.smoke",
    python_source=transpiled_source,                # composer 출력
    function_name="cumulativeProductivity",
    input_args=(None, "ABC", "01", None, None, None, None),
    input_kwargs={},
    expected_output=0.95,                           # Java 측 ground-truth
)

store = BehaviorFixtureStore([fixture])
runner = BehaviorTwinRunner(store)
result = runner.run_fixture("cumulativeProductivity.smoke",
                            plugin="section3", apply_diffs={})

if result.status == "PASS":
    return {"ok": True, "result": 0.95, "verified_against_baseline": True}
else:
    return {"ok": False, "diff": result.output_diff.summary}
```

## 8. Trace instrumentation (W60)

번역 시 `with_trace=True` 옵션이면 anchor 별로 `_trace.step('anchor_3', {'x': x, 'y': y})` 가 자동 삽입. fixture 에 `expected_trace_events=...` 를 함께 주면 W59 가 trace diff 까지 비교 → Section 3 의 SSE `layer_scan` 이벤트와 결합 시 step-by-step 검증 UI 가능.

## 9. 한계 / 함정

- **`exec()` 기반 sandbox** — RestrictedPython 수준의 강한 격리는 아님. `_safe_globals` 가 builtins subset 만 노출하지만, attribute lookup 으로 `().__class__.__bases__[0].__subclasses__()` 같은 escape 가 가능. **신뢰할 수 없는 코드 입력에는 부적합**, Java 측 검증된 transpile 결과 한정 사용.
- **모듈-level 가변 상태는 격리됨** — 두 번 호출하면 두 번 모두 fresh namespace 라 counter/cache 공유 안 됨. 자세히는 [test_w72_twin_invariants.py](../../../../../backend/sim_v2/tests/core/verification/test_w72_twin_invariants.py) 의 `test_module_level_mutable_state_is_blocked_by_sandbox` 참조.
- **외부 lib import 차단** — sandbox globals 에 없는 모듈 (`from datetime import ...` 등) 은 NameError. Section 3 의 anchor prelude + W74 stub injection 으로 케이스별 부착 필요.

## 10. 관련 파일

| 파일 | 역할 |
| --- | --- |
| `backend/sim_v2/core/verification/behavior_twin_runner.py` | 메인 구현 |
| `backend/sim_v2/core/verification/oracle.py` | `FixtureOracleResult` / `OracleRequest` |
| `backend/sim_v2/core/verification/trace.py` | W60 trace collector |
| `backend/sim_v2/demos/uc25_behavior_twin/run.py` | 시연 데모 (addPositives / cumulativeSum / buggyAverage) |
| `backend/sim_v2/tests/core/verification/test_behavior_twin_runner.py` | unit test |
