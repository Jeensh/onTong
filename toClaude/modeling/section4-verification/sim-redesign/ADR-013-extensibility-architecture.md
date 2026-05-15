# ADR-013: Extensibility Architecture for Meta-Programming

작성일: 2026-05-13
상태: 확정 (사용자 결정, 2026-05-13)
선행: ADR-002 (Two-Engine + plugin), ADR-006 ~ ADR-009 (4 meta-programming 영역)
관련 결정: M-D4 (확장가능 설계)

## 컨텍스트

ADR-006 ~ ADR-009 가 4 meta-programming 영역 (polymorphic dispatch / annotation / AOP / bytecode) 의 mechanism 명시. 그러나:
- 4 ADR 이 cover 하지 못하는 case 존재 (e.g., Spring AOP `@Aspect` 의 specific edge case, Lombok 외 custom annotation processor, JaCoCo / ASM instrumented bytecode)
- 새 meta-programming pattern 이 향후 발견될 수 있음 (e.g., GraalVM native image, Quarkus build-time DI, Loom virtual thread instrumentation)

DECISIONS-CONFIRMED.md 의 M-D4 결정:
- 추천 (`SYNTHESIS-ROUND2.html`): "Honest limits — SIGNATURE_LOCKED for unsupported"
- M-D4 결정: **수용하되 확장가능 설계** (Other 선택, non-default)

근거:
> Default: SIGNATURE_LOCKED for unsupported cases
> Extension first-class: plugins/<sys>/<extension-type>/ pattern 으로 새 case 추가
> Framework 변경 X, plugin 만 추가 → 새 meta-programming case 흡수

## 결정

**Framework core 의 4 meta-programming ADR 은 stable contract. Plugin level 의 extension point 로 새 case 흡수.**

### 1. Extension hierarchy

```
Tier 1 — Framework core (변경 빈도 낮음, semver)
  core/synthesizer/dispatchers/      # ADR-006 의 8 dispatch_kind
  core/synthesizer/annotations/      # ADR-007 의 annotation handler
  core/synthesizer/aop/              # ADR-008 의 aspect weaver
  core/synthesizer/bytecode/         # ADR-009 의 bytecode handler

Tier 2 — Plugin extensions (system 별 자유)
  plugins/<sys>/dispatchers/         # 새 dispatch_kind 추가
  plugins/<sys>/annotations/         # 새 annotation processor
  plugins/<sys>/aop/                 # 새 aspect type
  plugins/<sys>/bytecode/            # 새 bytecode pattern
  plugins/<sys>/extensions/          # tier 1-2 외 새로운 영역 (escape hatch)
```

### 2. Extension point contract

각 tier 1 디렉토리는 plugin 의 extension 을 registry pattern 으로 흡수:

```python
# core/synthesizer/dispatchers/__init__.py

DISPATCHER_REGISTRY: dict[str, Dispatcher] = {
    "single_impl": SingleImplDispatcher(),
    "instanceof_guard": InstanceofGuardDispatcher(),
    # ... 8 dispatch_kind (ADR-006)
}

def register_dispatcher(name: str, dispatcher: Dispatcher) -> None:
    """Plugin extension entry point."""
    if name in DISPATCHER_REGISTRY:
        raise ConflictError(f"Dispatcher {name!r} already registered")
    DISPATCHER_REGISTRY[name] = dispatcher

def get_dispatcher(dispatch_kind: str) -> Dispatcher:
    return DISPATCHER_REGISTRY.get(dispatch_kind, SignatureLockedDispatcher())
```

Plugin 의 extension 등록:
```python
# plugins/banking/dispatchers/__init__.py

from core.synthesizer.dispatchers import register_dispatcher
from .drools_dispatch import DroolsDispatcher

register_dispatcher("banking.drools_kbase_lookup", DroolsDispatcher())
```

Plugin manifest 에서 명시:
```toml
[plugin]
name = "banking"

[extensions]
dispatchers = ["banking.drools_kbase_lookup"]
annotations = ["@Compensable"]
aop = ["@TenantContext"]
bytecode = []
```

### 3. SIGNATURE_LOCKED 의 default behavior

Plugin extension 가 없는 unknown case 는 default 로 SIGNATURE_LOCKED:

```python
# core/synthesizer/dispatchers/default.py
class SignatureLockedDispatcher:
    def synthesize(self, call_site):
        return PythonStatement(
            f"# UNCLEAR: dispatch_kind = {call_site.kind!r} not handled by any registered dispatcher.\n"
            f"# SIGNATURE_LOCKED. Add plugins/<sys>/dispatchers/ extension or curate manually.\n"
            f"def {call_site.method}(...):\n"
            f"    raise NotImplementedError('SIGNATURE_LOCKED: {call_site.kind}')"
        )
```

### 4. Extension discovery + loading

```python
# core/plugin_loader.py
def load_plugin(plugin_path: pathlib.Path) -> None:
    """
    1. Read manifest.toml
    2. For each extension declared in [extensions]:
       - Import plugins/<sys>/dispatchers/ → triggers register_dispatcher() calls
       - Same for annotations, aop, bytecode, extensions
    3. Validate: declared extensions == actually registered
    4. Validate: namespace prefix (e.g., 'banking.*') matches plugin name
    """
    ...
```

### 5. Anti-pattern guard

- Plugin 이 framework core 의 dispatcher 를 override 금지 (DISPATCHER_REGISTRY 의 기존 key 에 register 시 `ConflictError`)
- Plugin 의 extension 은 unique name + **namespace prefix 권장**: `banking.drools_kbase_lookup` (not `drools_kbase_lookup`) — collision 방지
- Framework core 변경 시 backward compatibility 보장 — plugin extension API 의 semver
- `extensions/` tier 는 tier 1 의 4 영역 외 새로운 의미를 위한 **escape hatch** — 신중 사용. 정당화 문서 (`plugins/<sys>/extensions/RATIONALE.md`) 의무

### 6. Extension lifecycle (governance)

```
Phase 1 — Discovery
  Onboarding 중 unknown case 발견 → SIGNATURE_LOCKED 자동 발동
  User 가 plugins/<sys>/extensions/proposal-<case>.md 작성

Phase 2 — Implementation
  Plugin 의 dispatcher/annotation/aop/bytecode 등 작성
  Cross-plugin test suite 통과 확인

Phase 3 — Promotion (선택적)
  여러 plugin 에서 동일 extension 반복 등장 시
  → core/synthesizer/<tier-1>/ 으로 promote
  → 새 dispatch_kind / annotation_kind 추가
  → ADR-006~009 의 본 contract 갱신
```

Promotion 은 framework version bump (semver minor) — backward compatible.

## v2 / Broadleaf / Banking 의 예상 extension

| System | 예상 extensions |
|---|---|
| **v2** | (minimal) — Case 1-2 만 사용, framework core 로 충분. `plugins/v2-slab-design/extensions/` 비어있을 가능성 |
| **Broadleaf** | `broadleaf.configurable_handler` (Spring AOP @Configurable for entity injection), `broadleaf.data_driven` annotation, `broadleaf.dynamic_field` aspect |
| **Banking** | `banking.drools_kbase_lookup` dispatcher, `@Compensable` annotation, `@TenantContext` aspect, `banking.bpmn_dynamic_class` bytecode handler |

이 3 system 의 onboarding 이 extension architecture 의 실제 stress test (ADR-011 의 G4 gate, Month 4+).

## 결과 / 영향

- Framework core 의 4 ADR (006-009) 이 stable contract — 변경 빈도 낮춤
- 새 meta-programming case 가 발견될 때 plugin only — core 변경 X
- 3 system 각자의 specifics 가 plugin 안에 isolated
- SIGNATURE_LOCKED 가 "give up" 이 아닌 "default until extended" — 점진 처리 가능
- Extension API 의 backward compatibility 의무 발생 → semver discipline 필요
- Promotion 경로 명시 → "여러 plugin 의 공통 case" 가 framework core 로 흡수 가능

## Honest limits

- Plugin 이 tier 1 의 dispatcher 자체 의미를 fundamental 하게 바꾸는 case (e.g., dispatch_kind 자체를 polymorphic 으로 만드는 meta-meta) 는 framework core 변경 필요. 본 ADR 은 tier 1 외연 (새 dispatcher 추가) 만 cover
- Extension 의 quality 가 plugin author 책임 — framework 가 validate 못 함 (자동 test contract 만 enforce)
- 두 plugin 이 같은 namespace prefix 사용 시 collision — naming convention 으로만 방지, framework 자체는 enforce X

## 참조

- DECISIONS-CONFIRMED.md (M-D4)
- ADR-002 (plugin contract)
- ADR-006 ~ ADR-009 (4 meta-programming 영역)
- ADR-011 (3 systems — G4 gate 에서 extension architecture 검증)
- ADR-010 (Phase α discard — 새 framework 의 처음부터)
- `META-PROGRAMMING.html` (worked example)
