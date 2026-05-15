# W71 · Fixture Synthesizer — LLM test case 합성 대안

> **What:** Action 의 `params_json` 만 보고 deterministic boundary value 조합으로 fixture 생성.
>
> **Why for Section 3:** sandbox 의 normal/boundary/error 3 case 는 LLM 합성. 비결정적, repro 불가, 빈 문자열/MAX_INT 같은 진짜 boundary 누락 빈번. W71 은 결정적 + 6 boundary per string param + cap 12 combinations.

## 1. Import

```python
from backend.sim_v2.core.verification.fixture_synthesizer import (
    PRIMITIVE_TYPES,                 # frozenset({"string","int","long","float","double","decimal","boolean"})
    FixtureSynthesisReport,          # 결과 모델
    synthesize_fixtures_for_action,  # 메인 entry
)
```

## 2. Boundary value seed table

```python
_VALUE_SEEDS = {
    "string":  ("", "x", "y", "0", "-1", "테스트"),
    "int":     (0, 1, -1, sys.maxsize, -sys.maxsize - 1),
    "long":    (0, 1, -1, 2**62, -(2**62)),
    "float":   (0.0, 1.0, -1.0, 0.5, 1e30),
    "double":  (0.0, 1.0, -1.0, 1e100),
    "decimal": (Decimal("0"), Decimal("1"), Decimal("-1"), Decimal("0.5")),
    "boolean": (True, False),
}
```

Section 3 sandbox 의 LLM 합성 vs W71:

| 케이스 종류 | LLM (Section 3 현재) | W71 (결정적) |
| --- | --- | --- |
| normal | `cmpCd="ABC"` 같은 적당히 평범한 값 | `"x"`, `"y"`, `0`, `1` |
| boundary | LLM 이 "boundary" 라고 *부르는* 값 | `""`, `sys.maxsize`, `Decimal("-1")` — 진짜 경계 |
| error | LLM 이 None / 빈 문자열 | None (object_ref) + 같은 boundary 적용 |
| repro | 다시 부르면 다른 값 | 같은 입력 → 같은 출력 보장 |

## 3. 메인 API

```python
from backend.sim_v2.core.verification.fixture_synthesizer import (
    synthesize_fixtures_for_action,
)
from backend.sim_v2.core.ontology.domain_layer.production_domain_loader import (
    load_actions,
)

actions = load_actions(session, "slab-design-real-v2")
target = next(a for a in actions if a.fqn == "action.scm.fail")

report = synthesize_fixtures_for_action(
    session, target,
    function_name="fail_",                          # Python 측 def 이름
    python_source=transpiled_python,                # JavaToPythonTranslator 출력
    self_value=None,                                # 인스턴스 메서드면 mock self
    max_combinations=12,                            # cap (6×6 → 12)
)
# report.fixtures: tuple[BehaviorFixture, ...]
# report.synthesizable_params: int    (primitive — 우리가 변동 가능)
# report.skipped_params:       int    (object_ref / unknown — None placeholder)
# report.reason: str                  (왜 0 fixture / partial 인지)
```

## 4. Section 3 sandbox 와의 통합 예시

기존 Section 3 sandbox 의 `step` kind 합성 흐름을:

```
agent → composer.simulate(step, target_id=7)
    → LLM 으로 3 case 합성 (normal/boundary/error)
    → transpile → subprocess → 3 case 실행
```

W71 으로 교체:

```python
# Section 3 method/action kind 합성 분기에서
from backend.sim_v2.core.verification.fixture_synthesizer import (
    synthesize_fixtures_for_action,
)
from backend.sim_v2.core.verification.behavior_twin_runner import (
    BehaviorFixtureStore, BehaviorTwinRunner,
)
from backend.sim_v2.core.verification.engine import VerificationEngine
from backend.sim_v2.core.verification.oracle import OracleRequest

# 1) 합성 (LLM 대신)
report = synthesize_fixtures_for_action(
    session, action,
    function_name=composer_result.function_name,
    python_source=transpiled,
)

# 2) 일괄 실행
store  = BehaviorFixtureStore(list(report.fixtures))
runner = BehaviorTwinRunner(store)
engine = VerificationEngine(fixture_runner=runner, plugin="section3.w71")
req    = OracleRequest(
    proposal_id=f"section3.{action.fqn}",
    fixture_subset=[f.fixture_id for f in report.fixtures],
)
oracle = engine.run_oracle(req)

# 3) UI 노출 (Section 3 의 RichResultCard 와 동일 shape)
for fid, fxr in oracle.by_fixture.items():
    yield {
        "case_id":  fid,
        "input":    store.get(fid).input_args,
        "output":   fxr.python_proposal_output,
        "status":   fxr.status,                  # PASS / FAIL_OUTPUT / ERROR
    }
```

## 5. object_ref params 처리

Java 인자가 `SDOrderEntity`/`SDSlabEntity` 같은 entity 라면 W71 은 자동으로 `None` placeholder 를 emit. 보통 method body 가 `entity.getX()` 호출하므로 NameError 또는 NoneType 에러가 난다. 이때:

- **단기 대응:** [W72 invariants](./W72-twin-invariants.md) 의 `allowed_exceptions` 으로 NoneType 통과
- **장기 대응:** W74 stub injection (sandbox 에 mock entity 주입)
- **section3 anchor 기법 적용:** `code-types.{class_fqn}/fields` 의 fixture seed 를 stub 으로 부착

## 6. 한계 / 함정

- **primitive only** — String/int/long/float/double/decimal/boolean 만 변동. Java enum 은 `_VALUE_SEEDS` 에 없음 (수동 추가 필요).
- **max_combinations cap** — 3 string params 면 6×6×6=216 조합 → cap 12 = 첫 12 개만. 더 풍부한 coverage 가 필요하면 cap 키우거나 pairwise testing 라이브러리 도입.
- **인자 간 의존성 무시** — `validateRange(low, high)` 에서 `low > high` 같은 invalid 조합도 그대로 생성. 의미적 invariant 는 W72 `allowed_exceptions` 로 흡수.

## 7. 관련 파일

| 파일 | 역할 |
| --- | --- |
| `backend/sim_v2/core/verification/fixture_synthesizer.py` | 메인 구현 (200 lines) |
| `backend/sim_v2/tests/core/verification/test_w71_fixture_synthesizer.py` | 17 unit + production smoke |
| `backend/sim_v2/demos/uc37_production_fixture_coverage/run.py` | v2 38 action 전수 시연 — 11/38 driveable |
| `backend/sim_v2/tests/demos/test_uc37_production_fixture_coverage.py` | 7 demo test |

## 8. v2 production 결과

UC37 demo 실측 (38 action, slab-design-real-v2):

| Status | 건수 | 의미 |
| --- | --- | --- |
| FULL_PRIMITIVE | 9 | 모든 인자 primitive — 12 fixture 생성 가능 |
| PARTIAL | 2 | 일부 primitive — 변동, 나머지 None |
| ALL_NULL | 25 | 모든 인자 object_ref — null placeholder 만 |
| NO_LINK | 2 | code_method_fqn 없음 |
| **Total** | 38 | **151 fixtures 생성** |

Section 3 가 가져다 쓰면: 11/38 action 은 LLM 없이 deterministic case 생성 가능. ALL_NULL 25 건은 W74 stub injection 후 해제될 후보.
