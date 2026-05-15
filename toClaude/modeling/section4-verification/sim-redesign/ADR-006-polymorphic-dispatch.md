# ADR-006: Polymorphic Dispatch & Reflection Handling

작성일: 2026-05-13
상태: 확정 (사용자 D 선택 응답)
선행: ADR-001 (Python twin), ADR-002 (Two-Engine + plugin)
관련: v4 D3 (CallSiteAnalyzer 7-case)

## 컨텍스트

메모리 `project_decisions_v4_action.md` 의 D3 (CallSiteAnalyzer 7-case) 가 Java polymorphic dispatch 를 분류:
- 자동: single_impl / instanceof_guard / annotation / factory_branch (Case 1~4)
- 사용자 큐: generic / strategy_map / reflection (Case 5~7)

Round 2 종합 설계의 Anchored Twin Synthesizer 가 Layer 1 (slot registry) + Layer 2 (AST walker) 구조이나, dispatch_kind 가 Layer 1 emitter 분기 spec 에 누락. 사용자 reflection 질문이 이 빈틈 노출 → 이 ADR 이 명시.

## 결정

Layer 1 의 slot template entry 에 **dispatch_kind** 추가, 각 kind 별 Python emitter pattern 결정:

```python
SlotTemplate = NamedTuple(
    slot: str,
    java_pattern: ASTPatternMatcher,
    dispatch_kind: Literal[
        "single_impl",       # Case 1
        "instanceof_guard",  # Case 2
        "annotation",        # Case 3
        "factory_branch",    # Case 4
        "generic",           # Case 5
        "strategy_map",      # Case 6
        "reflection_bounded", # Case 7a
        "reflection_unbounded", # Case 7b
    ],
    py_emitter: Callable,
    runtime_imports: list[str],
)
```

Section 2 의 ontology table `anchor_bindings` 에 `dispatch_kind` 컬럼 추가 (현 schema 에 없음). 신규 마이그레이션 (additive).

## 각 dispatch_kind 의 Python emitter pattern

### Case 1 — single_impl (자동)
Interface 의 유일한 구현체. Synthesizer 가 직접 method call emit.

```java
service.process(order);  // service 의 구체 타입이 ProductService 하나
```
→
```python
self.product_service.process(order)
```

### Case 2 — instanceof_guard (자동)
Java pattern matching 또는 instanceof + cast.

```java
if (x instanceof Foo f) { f.bar(); }
else if (x instanceof Baz b) { b.qux(); }
```
→
```python
if isinstance(x, Foo):
    x.bar()
elif isinstance(x, Baz):
    x.qux()
```

### Case 3 — annotation (자동)
@Qualifier / @Primary / 등 명시. Synthesizer 가 dispatch table 생성.

```java
@Autowired @Qualifier("primary") private Service service;
```
→
```python
# Synthesizer 가 plugins/<sys>/contracts/ 의 qualifier registry 조회
self.service = qualifier_registry["primary"]  # = PrimaryServiceImpl()
```

### Case 4 — factory_branch (자동)
Factory 의 if-chain / switch.

```java
public Service create(String kind) {
    switch (kind) {
        case "A": return new ServiceA();
        case "B": return new ServiceB();
        default:  return new DefaultService();
    }
}
```
→
```python
def create(self, kind: str) -> Service:
    if kind == "A":
        return ServiceA()
    elif kind == "B":
        return ServiceB()
    else:
        return DefaultService()
```

### Case 5 — generic (사용자 큐)
Java generic 의 type erasure → ontology 의 candidate set + LLM 추천.

```java
public <T extends Entity> T find(Class<T> type, String id) {
    return entityManager.find(type, id);
}
```

Ontology 가 candidate (`Order`, `Slab`, `CastSpec`, ...) 식별 → user 가 confirm. 합성기:

```python
def find(self, type_: type[T], id: str) -> T:
    # ontology 가 candidate 식별: [Order, Slab, CastSpec]
    return lookup_data_source.find_by_type(type_, id)
```

### Case 6 — strategy_map (사용자 큐)
`Map<String, Strategy>` 의 정적 population 분석.

```java
private static final Map<String, AlgorithmStep> STEPS = Map.of(
    "thickness", new SdThicknessAction(),
    "width", new SdWidthRangeAction(),
    "length", new SdLengthRangeAction()
);
STEPS.get(stepName).run(order, slab);
```

Section 2 가 map population 정적 분석 → ontology 의 key→target 쌍. 합성기:

```python
STEPS: dict[str, AlgorithmStep] = {
    "thickness": SdThicknessAction(),
    "width": SdWidthRangeAction(),
    "length": SdLengthRangeAction(),
}
STEPS[step_name].run(order, slab)
```

Bounded — runtime key set 이 static 으로 알려진 경우.

### Case 7a — reflection_bounded (사용자 큐)
Bounded reflection: target 이 compile-time 에 알려진 set 안.

```java
String name = "com.example.scm.action." + capitalize(stepName);
Class<?> clazz = Class.forName(name);
clazz.getDeclaredConstructor().newInstance();
```

Section 2 가 candidate set 식별 (e.g., `com.example.scm.action.*` package scan + `@Component` 표시 클래스) → user confirm. 합성기:

```python
from plugins.slab_design.actions import (
    SdThicknessAction, SdWidthRangeAction, SdLengthRangeAction,
    # ... ontology candidate set 의 모든 class
)

ACTION_REGISTRY = {
    "thickness": SdThicknessAction,
    "width": SdWidthRangeAction,
    "length": SdLengthRangeAction,
    # ...
}

target_cls = ACTION_REGISTRY[step_name.lower()]
target_cls()
```

또는 동적 import 가 의도이면:

```python
import importlib
module = importlib.import_module(f"plugins.slab_design.actions.{step_name}_action")
target_cls = getattr(module, f"{capitalize(step_name)}Action")
target_cls()
```

선택은 ontology 의 user confirm 결정.

### Case 7b — reflection_unbounded (사용자 큐)
Target name 이 runtime 사용자 입력 또는 외부 config 에서 옴 — bound 식별 불가.

```java
String className = config.getProperty("dynamic.handler.class");  // runtime
Class<?> clazz = Class.forName(className);
clazz.newInstance();
```

Section 2 가 candidate 부재 신호 → GapSurfacer 가:

```python
# UNCLEAR: unbounded reflection at L42.
# Target class depends on runtime config property "dynamic.handler.class".
# Twin scope EXCLUDES this method body. SIGNATURE_LOCKED.
def execute(self, ...):
    raise NotImplementedError(
        "SIGNATURE_LOCKED: unbounded reflection. "
        "Target class resolution requires runtime config."
    )
```

또는 사용자 명시 plugin 으로 elevated:

```python
# plugins/<sys>/dynamic_handlers.py 가 사용자 작성
HANDLER_REGISTRY = {
    "X": ...,  # 사용자가 직접 매핑
}
```

## v2 Reality Check

grep 결과 (사용자 D 선택 응답 시점):
- `Class.forName` / `method.invoke` / `getDeclared*` / `java.lang.reflect.*` : **0건**
- `Map<String, Strategy>` / functional dispatch: **0건**
- `instanceof`: **1건** (TraceCollector L45 — Case 2)
- Spring DI annotation 은 framework 영역 — ADR-002 의 plugins/<sys>/stubs/ 처리

v2 는 dispatch 측면에서 거의 trivial — Case 2 minimal + Case 1 (single impl) majority. 더 복잡한 system 에서 본 ADR 의 효용.

## Section 2 의 작업

CallSiteAnalyzer (메모리 v4 D3) 의 실제 구현이 필요:
1. Java AST walk 시 각 method call site 에서 dispatch_kind 추정
2. Case 1-4 자동 결정
3. Case 5-7 candidate 추출 → ontology 의 `anchor_bindings.dispatch_kind` + `dispatch_candidates_json` 컬럼
4. 사용자 confirm queue (modeling UI)

## Honest Limits

- **Case 7b unbounded reflection**: 어떤 합성기도 풀 수 없는 근본 한계 — target 이 runtime 까지 미정. SIGNATURE_LOCKED 외 대안 없음
- **Case 5 generic 의 candidate identification**: type erasure 때문에 사용 시점 의 type argument 가 unknown. Section 2 의 정적 분석이 모든 call site 의 generic argument 를 추적해야 — 비용 큼
- **Map population 의 dynamic 추가**: `STEPS.put(name, impl)` 가 condition 안에 있거나 외부 input 의존 시 정적 분석 불가
- **Mixed dispatch**: 한 method 안에서 여러 dispatch_kind 가 chain (예: instanceof_guard 후 strategy_map lookup) → 합성기 emitter 의 composition rule 필요

## 결과

- Layer 1 emitter 가 8 종 dispatch_kind 별 분기 — 결정론적 합성 보장 영역 확대
- Case 7a (bounded reflection) 까지 자동, Case 7b 만 SIGNATURE_LOCKED — Round 2 synthesis 의 "Reflection → SIGNATURE_LOCKED" 단순화 보정
- Section 2 의 CallSiteAnalyzer 실제 구현 의존 — 별도 작업 항목 (ADR-002 의 plugin onboarding 의 일부)
- v2 영향 zero — v2 는 Case 1-2 만 사용
- 일반화: 모든 system 의 dispatch 가 8 kind 안에 들어옴

## 참조

- 메모리 `project_decisions_v4_action.md` (D3 = A+)
- ADR-002 (system-agnostic + plugin)
- 사용자 reflection 질문 (이 ADR motivation)
