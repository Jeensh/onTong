# W72 · Twin Invariants — Baseline-free 검증

> **What:** Java baseline output 없이도 twin 의 *구조적 invariant* 3 개를 검증.
>
> **Why for Section 3:** 모든 메서드의 Java 정답을 미리 알 수는 없다. 그래도 "두 번 실행하면 같은 결과", "void 라면 None 반환", "throw 안 함" 같은 *최소 sanity* 는 baseline 없이 검증 가능. Section 3 sandbox 의 단발 실행 결과 `ok=true` 만 보여주던 것을 *invariant 보장* 까지 확장.

## 1. Import

```python
from backend.sim_v2.core.verification.twin_invariants import (
    InvariantCheckResult,            # per-fixture report
    InvariantAggregate,              # 전체 묶음
    TwinInvariantRunner,             # 메인 runner
    run_invariants_for_fixtures,     # 편의 함수
)
```

## 2. 검증 invariant 3 종

| Invariant | 무엇 | Fail 조건 |
| --- | --- | --- |
| **DETERMINISM** | 같은 args 로 2 번 호출 → 같은 출력 | 두 호출의 결과가 다름 |
| **NO_UNEXPECTED_THROW** | 예외 던지지 않거나, `allowed_exceptions` 에 포함된 클래스만 던짐 | 다른 클래스 던짐 |
| **RETURN_TYPE_OK** | 출력의 Python type 이 `declared_return` 과 매핑 | declared `int` 인데 `str` 반환 등 |

`None` 은 모든 declared return 에 대해 허용 (Java null 의 합법성).

## 3. 메인 API — 단일 fixture

```python
from backend.sim_v2.core.verification.twin_invariants import TwinInvariantRunner
from backend.sim_v2.core.verification.behavior_twin_runner import BehaviorFixture

src = (
    "def add(self, a, b):\n"
    "    return a + b\n"
)
fixture = BehaviorFixture(
    fixture_id="add.1",
    python_source=src,
    function_name="add",
    input_args=(None, 2, 3),
    input_kwargs={},
    expected_output=None,                # 사용 안 함 (W72 는 baseline-free)
)

runner = TwinInvariantRunner(
    declared_return="int",
    allowed_exceptions=(),               # () = 모든 throw 가 fail
)
r = runner.check(fixture)
# r.status: PASS / FAIL_NONDETERMINISTIC / FAIL_UNEXPECTED_THROW /
#           FAIL_RETURN_TYPE / ERROR
```

## 4. Aggregate

```python
from backend.sim_v2.core.verification.twin_invariants import (
    run_invariants_for_fixtures,
)

agg = run_invariants_for_fixtures(
    fixtures,
    declared_return="string",
    allowed_exceptions=("ValueError", "ArithmeticException"),
)
# agg.aggregate_status: PASS / FAIL_NONDETERMINISTIC /
#                      FAIL_UNEXPECTED_THROW / FAIL_RETURN_TYPE / ERROR /
#                      INCONCLUSIVE
# agg.passing: int
# agg.total:   int
```

## 5. Declared return type 매핑

```python
_PY_TYPE_FOR_DECLARED = {
    "string":  (str,),
    "int":     (int,),                   # bool 은 명시적 제외
    "long":    (int,),
    "float":   (float, int),             # widening
    "double":  (float, int),
    "decimal": (Decimal, int, float),
    "boolean": (bool,),
    "void":    (type(None),),
    # object_ref / unknown → 타입 check skip
}
```

- `bool` 은 Python 에서 `int` 의 subclass 라 의도치 않게 통과. 명시적으로 차단.
- declared `object_ref` 또는 모르는 type 이면 type check 건너뜀. → Section 3 의 entity return 메서드도 통과.

## 6. Section 3 sandbox + W72 통합 예시

```python
# Section 3 sandbox 가 method/action 시뮬 후 invariants 자동 검증
from backend.sim_v2.core.verification.fixture_synthesizer import (
    synthesize_fixtures_for_action,
)
from backend.sim_v2.core.verification.twin_invariants import (
    run_invariants_for_fixtures,
)

report = synthesize_fixtures_for_action(
    session, action,
    function_name=fn, python_source=src,
)

# action.output_json 에서 declared return 추출
declared = action.output_json.get("type", "void") if action.output_json else "void"

inv = run_invariants_for_fixtures(
    report.fixtures,
    declared_return=declared,
    allowed_exceptions=tuple(action.effects_json.get("exceptions", [])),  # 액션이 명시한 throw 만 허용
)

# UI 표시 — Section 3 의 RichResultCard 확장
yield {
    "invariants": {
        "passing":    inv.passing,
        "total":      inv.total,
        "status":     inv.aggregate_status,
        "per_fixture": [
            {"fixture_id": fid, "status": r.status, "error": r.error}
            for fid, r in inv.fixture_id_to_result.items()
        ],
    }
}
```

## 7. Section 3 의 chat impact 분기 [LOW] fallback 보강

현재 Section 3 chat 에서 자연어 → fqn 변환 실패 시 [LOW] fallback. W72 의 sample error 가 *구체적 cause* 를 제공:

| W72 status | chat 측 UX |
| --- | --- |
| `FAIL_RETURN_TYPE` | "이 메서드는 `string` 반환을 선언했지만 `Decimal` 을 돌려줍니다 — 시그니처 mismatch 가능성" |
| `FAIL_UNEXPECTED_THROW` | "이 메서드는 input `(...)` 에서 `NullPointerException` 을 던집니다 — null check 누락 추정" |
| `FAIL_NONDETERMINISTIC` | "이 메서드는 같은 입력에 다른 결과 — 외부 상태 (DB/시간/random) 의존" |
| `ERROR` | "translation 자체 실패 — Java idiom (`.length()` 등) 또는 외부 클래스 (`SDOrderEntity`) 가 sandbox 에 없음" |

→ chat UX 에서 *왜 [LOW] 인지* 명확한 진단으로 변환.

## 8. UC38 production survey 결과 — 정직한 baseline

v2 38 action 중 11 driveable (UC37 driveable) 에 대해 W72 결과:

| Cause | 건수 |
| --- | --- |
| FAIL_UNEXPECTED_THROW | 9 |
| ERROR (compile fail) | 2 |
| **PASS** | **0** |

이게 *Section 3 sandbox 가 진짜로 가지고 있는 production gap*. 대부분 NameError (`SlabDesignHistEntity` 등 sandbox 에 없는 클래스). → W74 stub injection 으로 close.

## 9. 한계

- **Fresh namespace 격리** — 두 번째 호출은 새 namespace 라 module-level 가변 상태가 carry-over 안 됨. `_counter[0] += 1` 같은 nondeterminism 은 NameError 로 흡수 → 결과적으로 FAIL_UNEXPECTED_THROW.
- **Time/random 의존성 미검출** — `datetime.now()` 가 sandbox 에 노출되지 않아 NameError. 노출 후 호출하면 그제서야 FAIL_NONDETERMINISTIC.
- **Output 의 값 자체는 검증 안 함** — 진짜 값 정합성은 W59 + W73 baseline 필요.

## 10. 관련 파일

| 파일 | 역할 |
| --- | --- |
| `backend/sim_v2/core/verification/twin_invariants.py` | 메인 구현 |
| `backend/sim_v2/tests/core/verification/test_w72_twin_invariants.py` | 17 unit test |
| `backend/sim_v2/demos/uc38_production_invariants/run.py` | v2 production survey |
