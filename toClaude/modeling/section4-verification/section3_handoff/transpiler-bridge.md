# Transpiler Bridge — Section 3 ↔ sim_v2

> Java → Python transpiler 가 **두 곳에 분리되어 존재**한다. 어디가 더 깊은지, 어디가 누락이며, Section 3 가 어디를 가져다 쓰면 좋은지 정직하게 정리.

| | Section 3 | sim_v2 (Section 4) |
| --- | --- | --- |
| 경로 | `backend/section3/transpiler.py` | `backend/sim_v2/core/synthesizer/java_translator.py` |
| 라인 수 | ~수백 (보고서 추정) | **1,425 lines** |
| 핸들러 함수 | (Section 3 보고서에 미공개) | **71 `_translate_*` dispatch** |
| 기본 파서 | `tree-sitter-java` | `tree-sitter-java` (동일) |
| 출력 | Python source 1 string | `TranslationResult(python_source, imports_needed, notes, signature_locked)` |
| 호출 측 | sandbox subprocess (1 case-at-a-time) | `BehaviorTwinRunner` (in-process safe exec, multi-fixture) |

## 1. 규칙 매핑 — 누가 무엇을 처리하는가

| 규칙 | Section 3 | sim_v2 |
| --- | --- | --- |
| **literal** | | |
| `null` → `None` | ✓ | ✓ `_translate_null_literal` |
| `true / false` | ✓ | ✓ `_translate_true`, `_translate_false` |
| 정수/실수/문자/문자열 리터럴 | ✓ | ✓ 각 handler |
| **연산자** | | |
| `&&` `\|\|` → `and` `or` | ✓ | ✓ `_translate_binary_expression` |
| `==` 객체 비교 | (확실치 않음) | ✓ |
| `++ / --` | (PoC 표 누락) | ✓ `_translate_update_expression` |
| **타입 박싱** | | |
| `BigDecimal` → `Decimal` | ✓ `new BigDecimal("0.95") → Decimal("0.95")` | ✓ `_JAVA_TYPE_TO_PYTHON` map (`String/Integer/Long/Float/Double/BigDecimal/...`) |
| `Class.forName()` | (없음 추정) | ✓ `_translate_class_literal` |
| **Java String idiom** ★ | | |
| `s.length()` → `len(s)` | ✓ | **✓ W75 추가** |
| `s.charAt(i)` → `s[i]` | ✓ | **✓ W75 추가** |
| `s.equals(o)` → `s == o` | (확실치 않음) | **✓ W75 (receiver_type=String 필요)** |
| `s.isEmpty()` → `not s` | (확실치 않음) | **✓ W75 (typed)** |
| `s.substring(a,b)` → `s[a:b]` | (확실치 않음) | **✓ W75 추가** |
| `s.startsWith/endsWith/trim/toLowerCase` | (확실치 않음) | **✓ W75 추가** |
| **Collection idiom** | | |
| `list.size()` → `len(list)` | (확실치 않음) | **✓ W75 (typed: List/Map/Set)** |
| `map.containsKey(k)` → `k in map` | (확실치 않음) | **✓ W75 추가** |
| `map.get(k)` → `map.get(k)` (OK) | OK | OK (변화 없음) |
| **Math / Static idiom** | | |
| `Math.abs(x)` → `abs(x)` | (확실치 않음) | **✓ W75 추가** |
| `Math.min/max/pow/round/sqrt` | (확실치 않음) | **✓ W75 추가** |
| `Integer.parseInt(s)` → `int(s)` | (확실치 않음) | **✓ W75 추가** |
| `Objects.isNull/nonNull/equals` | (확실치 않음) | **✓ W75 추가** |
| `Optional.isPresent/get/orElse` | (확실치 않음) | **✓ W75 (typed)** |
| **Control flow** | | |
| `for (int i = 0; i < N; ++i)` → `for i in range(0, N)` | ✓ | ✓ `_translate_for_statement` |
| `while`, `do-while` | (보고서 미언급) | ✓ |
| `for-each` | (보고서 미언급) | ✓ `_translate_enhanced_for_statement` |
| `continue / break` | ✓ 그대로 | ✓ |
| `if / else if / else` | (보고서 미언급) | ✓ |
| `switch` (Java 14+ arrow form 포함) | (보고서 미언급) | ✓ `_translate_switch_statement` (예상 — 71 핸들러 중) |
| **메서드** | | |
| 메서드 선언 → `def` | ✓ | ✓ `_translate_method_declaration` |
| `this` → `self` | ✓ (PoC) | ✓ `_translate_this` |
| Static 메서드 | (보고서 미언급) | ✓ |
| **클래스** | | |
| `new Foo(args)` → `Foo(args)` | (보고서 미언급, BigDecimal 만 명시) | ✓ `_translate_object_creation_expression` |
| 캐스팅 `(T) x` | (없음 추정) | ✓ `_translate_cast_expression` |
| `instanceof` | (없음 추정) | ✓ `_INSTANCEOF_TYPE_MAP` |
| `Foo.class` (class literal) | (없음 추정) | ✓ `_translate_class_literal` |
| Field access (`this.f`, `Foo.STATIC`) | (보고서 미언급) | ✓ `_translate_field_access` |
| Inner / nested class | (없음 추정) | (W23/W41 — `_translate_class_declaration`) |
| **예외** | | |
| `throw new X("msg")` | (보고서 미언급) | ✓ `_translate_throw_statement` |
| `try / catch / finally` | (보고서 미언급) | ✓ `_translate_try_statement` |
| `try-with-resources` | (없음 추정) | ✓ (W23 — context manager 변환) |
| **Lambda / functional** | | |
| `(x) -> body` | (없음 추정) | ✓ `_translate_lambda_expression` (multi-stmt body 는 nested def hoist) |
| `Class::method` (method ref) | (없음 추정) | ✓ `_translate_method_reference` |
| **annotation / trace** | | |
| W16 trace anchor (`_trace.step('anchor_N', {...})` 삽입) | ✗ | ✓ `with_trace=True` 옵션 |
| W21 `this.field` 의 enclosing class resolution | ✗ | ✓ (`this_type` 인자) |

## 2. 한 줄 결론

| Section 3 가 강한 곳 | sim_v2 가 강한 곳 |
| --- | --- |
| **Java String idiom** 명시 변환 (length/charAt) | **AST 핸들러 깊이** (71 handler, lambda/try-with-resources/instanceof/class literal/cast/inner class) |
| 단발 production 실행 검증 (`cumulativeProductivity → 0.95`) | **trace instrumentation** (W60 — anchor 별 변수 캡처) |
| `anchor_locator` → module-level prelude prepend (W74 prototype) | **enclosing class 의 this.field FQN resolution** (W21) |

## 3. 추천 통합 path (시뮬레이션 담당자 / 클로드용)

세 가지 옵션. **B 가 가성비 가장 좋다.**

### A. Section 3 transpiler 유지, sim_v2 무시
- **장점:** 즉시. 변화 없음.
- **단점:** sim_v2 의 71 handler (lambda/try-with-resources/inner class/instanceof) 못 받음. Section 3 demo 가 ProductivityService 같은 *단순* 메서드만 처리 가능.
- **언제:** Section 3 가 항상 PoC 의 단순 메서드만 다룬다는 약속이 가능할 때.

### B. sim_v2 를 base 로 가져가고, Java String idiom 만 patch ★ 추천
- **방법:** `from backend.sim_v2.core.synthesizer.java_translator import JavaToPythonTranslator` 후 subclass 하여 `_translate_method_invocation` 만 override:
  ```python
  class Section3Translator(JavaToPythonTranslator):
      _IDIOM_REWRITES = {
          ("String", "length"): lambda obj, args: f"len({obj})",
          ("String", "charAt"): lambda obj, args: f"{obj}[{args[0]}]",
          ("String", "isEmpty"): lambda obj, args: f"(not {obj})",
          ("String", "equals"): lambda obj, args: f"({obj} == {args[0]})",
          ("String", "substring"): lambda obj, args: f"{obj}[{args[0]}:{args[1] if len(args)>1 else ''}]",
          ("List", "size"): lambda obj, args: f"len({obj})",
          ("Map", "containsKey"): lambda obj, args: f"({args[0]} in {obj})",
      }
      def _translate_method_invocation(self, node, *, indent):
          # 1) detect (receiver_type, method_name)
          # 2) if in self._IDIOM_REWRITES → use rewrite
          # 3) else fall back to super().
          ...
  ```
- **장점:** 71 handler 모두 상속. Java String / Collection idiom 만 patch. UC39 의 ATTRERROR 2건 (str.length) 동시 해결.
- **단점:** sim_v2 dependency 가 backend/section3/ 에 들어옴. 단방향이라 부담 적음.

### C. sim_v2 java_translator 자체에 idiom rewrite 추가
- **방법:** `_translate_method_invocation` 안에 `_IDIOM_REWRITES` 분기 추가 (sim_v2 W75 sprint).
- **장점:** 두 곳 모두 자동 혜택. Section 3 는 그대로 sim_v2 호출하면 됨.
- **단점:** sim_v2 변경 — 우리 1,727 tests 회귀 확인 필요. (단 W75 작업이 어차피 plan 에 있음.)

## 4. Section 3 의 anchor prelude 기법 (W74 ✓ 구현 완료)

Section 3 보고서 8.7 의 결정적 한 줄을 generic 화하여 **W74 Sandbox stub injection** 으로 완성:

```python
from backend.sim_v2.core.verification.sandbox_stubs import build_stub_namespace
from backend.sim_v2.core.verification.behavior_twin_runner import BehaviorTwinRunner

# 자동 stub namespace 생성
stub_ns = build_stub_namespace(
    session, method_fqn="com.x.ProductivityService.cumulativeProductivity(...)",
    repo_id="slab-design-real-v2",
    python_source=transpiled,
)
# stub_ns 안에:
#   "DEFAULT_PRODUCTIVITY": 0.95         ← anchor_locator regex 추출
#   "ValidationResult":     MagicMock(...) ← AST unbound + class stub
#   "groupRepository":      MagicMock(...) ← AST unbound + bean suffix → repo stub

runner = BehaviorTwinRunner(store, stub_namespace=stub_ns)
```

**UC40 실측 결과 (2026-05-16):**

| | UC38 baseline | UC40 stub-injected |
| --- | --- | --- |
| Action PASS | **0 / 11** | **6 / 11 (54.5%)** |
| Fixture PASS | 0 / 126 | 74 / 126 (58.7%) |
| 자동 derive 된 stubs | 0 | 23 |
| NameError 발생 | 11 | **0** |

남은 5 건은 SYNTAX 2 (translator 추가 case 필요) + FAIL_RETURN_TYPE 3 (MagicMock cascade 가 declared return type 과 mismatch — typed-return stub 으로 close 가능, 다음 sprint).

## 5. 즉시 가져다 쓸 수 있는 sim_v2 API

```python
# Section 3 의 sandbox 가 LLM 으로 합성하던 부분을 deterministic 로 교체
from backend.sim_v2.core.verification.fixture_synthesizer import (
    synthesize_fixtures_for_action,    # W71 — primitive boundary value seeds
)

# Section 3 의 sandbox subprocess 대신 in-process safe exec
from backend.sim_v2.core.verification.behavior_twin_runner import (
    BehaviorTwinRunner,                # W59 — diff against Java baseline
    BehaviorFixture,                   # 입력/예상값 모델
    compare_outputs,                   # 결과 비교 with tolerance
    _safe_globals,                     # Section 3 의 sandbox _safe_globals 대안
)

# Java baseline 부착 (Section 3 가 expected_output 검증 못하는 한계 해결)
from backend.sim_v2.core.verification.java_oracle_adapter import (
    JavaBaselineMap,                   # (action, args) → expected 라이브러리
    JavaBaselineEntry,
    attach_baselines,                  # synth fixture 에 baseline 부착
)

# Behavioral baseline 없이도 검증
from backend.sim_v2.core.verification.twin_invariants import (
    TwinInvariantRunner,               # W72 — determinism + return-type + no-throw
    run_invariants_for_fixtures,
)

# Translation
from backend.sim_v2.core.synthesizer.java_translator import (
    JavaToPythonTranslator,            # 71 handler
    TranslationResult,
)
```
