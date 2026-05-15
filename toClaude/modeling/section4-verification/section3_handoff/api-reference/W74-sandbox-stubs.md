# W74 · Sandbox Stub Injection — Production NameError 0

> **What:** Production method 의 sandbox exec 에 필요한 stub (anchor 상수, entity 클래스, Spring bean, JPA repo) 을 3 source 에서 자동 derive 하여 `_safe_globals` 에 주입.
>
> **Why for Section 3:** Section 3 의 anchor prelude 기법은 `DEFAULT_PRODUCTIVITY = 0.95` 1건만 우회. W74 는 같은 idea 를 generic 화하여 UC38 의 0/11 PASS → UC40 의 **6/11 PASS** 까지 도달.

## 1. Import

```python
from backend.sim_v2.core.verification.sandbox_stubs import (
    build_stub_namespace,                    # 통합 entry — 권장
    derive_anchor_constants,                 # anchor_locator regex 추출
    derive_class_stub,                       # MagicMock(spec_set=fields)
    derive_entity_stub_from_code_types,      # + code_types lookup
    derive_repository_stub,                  # Spring bean MagicMock
    find_unbound_names,                      # AST-based unbound discovery
    classify_unbound,                        # "class" / "bean" / "unknown"
    is_bean_name,                            # *Repository / *Service / ...
)
```

## 2. 3 source 분류

| Source | 무엇 | 어떻게 derive |
| --- | --- | --- |
| **(a) anchor constants** | `DEFAULT_PRODUCTIVITY = 0.95` 같은 static final | `anchor_bindings.anchor_locator` 의 regex `^([A-Z_][A-Z0-9_]*)\s*=\s*(.+?)$` |
| **(b) class stubs** | `ValidationResult`, `SDOrderEntity` 같은 entity ctor | AST 로 unbound Name 찾고 Capitalized → `MagicMock(spec_set=fields)` (code_types.fields_json 있으면 spec, 없으면 permissive) |
| **(c) repository / bean stubs** | `orderRepository`, `userService`, `xmlMapper` | camelCase + suffix (`Repository/Service/Mapper/Client/Manager/Dao/Handler/Resolver/Helper/Translator/Validator/Builder/Factory/Provider/Loader/Driver`) → `MagicMock` |

## 3. 통합 API (권장 entry)

```python
from sqlalchemy.orm import Session
from backend.sim_v2.core.verification.sandbox_stubs import build_stub_namespace

stub_ns = build_stub_namespace(
    session,
    method_fqn="com.x.ProductivityService.cumulativeProductivity(...)",
    repo_id="slab-design-real-v2",
    python_source=transpiled,
    code_types_lookup_fqns={                  # (optional) short → FQN
        "SDOrderEntity": "com.example.slabdesign.feature.sd.SDOrderEntity",
        ...
    },
)
# stub_ns ::= {
#   "DEFAULT_PRODUCTIVITY": 0.95,
#   "ValidationResult":     <MagicMock spec_set=['ok', 'errorCode', 'message']>,
#   "groupRepository":      <MagicMock>,
#   "lookup":               <MagicMock>,   # lowercase non-bean — permissive
# }
```

## 4. BehaviorTwinRunner / TwinInvariantRunner 통합

```python
from backend.sim_v2.core.verification.behavior_twin_runner import BehaviorTwinRunner
from backend.sim_v2.core.verification.twin_invariants import TwinInvariantRunner

# W59 와 함께
runner = BehaviorTwinRunner(store, stub_namespace=stub_ns)

# W72 와 함께
inv = TwinInvariantRunner(
    declared_return="float",
    allowed_exceptions=("ValueError", "ArithmeticException"),
    stub_namespace=stub_ns,
)
```

`_safe_globals(extra=stub_ns)` 가 내부적으로 합쳐서 exec 시 사용된다. 사용자는 hook 자체를 직접 호출할 필요 없음.

## 5. Section 3 sandbox 통합 시나리오

```python
# Section 3 의 sandbox_agent.py — 현재 흐름
def simulate_method(composer_result):
    py_src = transpile(composer_result.java_body)
    # ★ NEW — 우리 자산 사용
    from backend.sim_v2.core.verification.sandbox_stubs import build_stub_namespace
    stub_ns = build_stub_namespace(
        session, composer_result.method_fqn, repo_id, py_src,
    )
    # 기존 subprocess 대신 W59 in-process
    from backend.sim_v2.core.verification.behavior_twin_runner import (
        BehaviorTwinRunner, BehaviorFixtureStore,
    )
    runner = BehaviorTwinRunner(store, stub_namespace=stub_ns)
    return runner.run_fixture(fixture_id, plugin="section3", apply_diffs={})
```

## 6. 자동 derive 의 한계 (정직하게)

| 케이스 | 동작 | 우회 |
| --- | --- | --- |
| `DEFAULT_PRODUCTIVITY = 0.95` | ✓ 정확히 0.95 추출 | — |
| `MAX = 999L` (Java long literal) | ✓ 999 (L suffix 제거) | — |
| `PRICE = new BigDecimal("99.5")` | ✓ Decimal("99.5") 추출 | — |
| `ITEMS = List.of(1, 2, 3)` | ✗ regex 가 List literal 미파싱 | 수동 stub 추가 |
| `repo.findById(x).orElse(y)` | ✓ MagicMock cascade → MagicMock | OK, 단 declared return type 과 mismatch 가능 |
| `if (entity.getX() > 5)` | ✓ MagicMock comparison → MagicMock truthy | 결과 무의미 — typed return stub 필요 |

## 7. UC40 실측 (v2, 2026-05-16)

```
──────────────────────────────────────────────────────────────────────────────
✓ W74 stub-injection production reach: 6/11 actions invariant-clean
──────────────────────────────────────────────────────────────────────────────
  ✓ [PASS              ] 12/12  stubs=1  return=object_ref  action.scm.fail
  ✓ [PASS              ] 12/12  stubs=5  return=void        action.scm.record_step
  ✓ [PASS              ] 12/12  stubs=5  return=void        action.scm.record_algorithm_failure
  ✓ [PASS              ] 12/12  stubs=2  return=object_ref  action.scm.find_group
  ✓ [PASS              ] 12/12  stubs=3  return=object_ref  action.scm.find_spec
  ✓ [PASS              ] 12/12  stubs=3  return=float       action.scm.product.cumulative_productivity
  ✗ [FAIL_RETURN_TYPE  ] 0/12   stubs=1  return=string      action.scm.batch_design
  ✗ [FAIL_RETURN_TYPE  ] 0/12   stubs=2  return=float       action.scm.product.lookup_or_default
  ✗ [FAIL_RETURN_TYPE  ] 2/6    stubs=1  return=string      action.scm.product.classify_by_product_code
  ✗ [ERROR             ] 0/12   stubs=0  return=string      action.scm.batch_design__driver
  ✗ [ERROR             ] 0/12   stubs=0  return=object_ref  action.scm.order.extract_designable_orders
```

## 8. 관련 파일

| 파일 | 역할 |
| --- | --- |
| `backend/sim_v2/core/verification/sandbox_stubs.py` | 메인 구현 (~260 lines) |
| `backend/sim_v2/tests/core/verification/test_w74_sandbox_stubs.py` | 42 unit test |
| `backend/sim_v2/demos/uc40_stub_injected_behavioral/run.py` | production survey |
| `backend/sim_v2/tests/demos/test_uc40_stub_injected_behavioral.py` | 6 demo test |
