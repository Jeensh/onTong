# 02 — Ontology API Additions

> **목적**: `/api/ontology/*` 보강. 기존 18 endpoint 에 추가로 시뮬 에이전트가 필요로 하는 BR / reverse lookup / graph traversal / DesignGap / Scenario endpoint 약 12개 신설.
>
> **위치**: `backend/modeling/api/ontology_router.py`.
>
> **의존**: `01-schema-extensions.md` 의 스키마 보강이 선행되어야 함.

---

## 0. 카탈로그

| 분류 | 신규 endpoint | 수 |
|---|---|---|
| BusinessRule | list / get / by-action / by-method | 4 |
| Action graph traversal | delegates-to-tree / realizing-methods | 2 |
| Reverse lookup | atoms→TR/Anchor / methods→callers / literal→anchor | 3 |
| DesignGap | list / get / by-action | 3 |
| SimulationScenario | list / get / by-action | 3 |
| **합계** | | **약 15** (병합 시 약 12) |

---

## 1. BusinessRule endpoints

### 1.1 GET `/api/ontology/business-rules`

```
GET /api/ontology/business-rules
  ?repo_id={str}                # optional
  &severity={error|warning|info} # optional
  &declared_on_term={str}        # optional
  &enforced_by={method_fqn}      # optional — 특정 메서드가 enforce 하는 BR 만
```

**Response**: `list[BusinessRuleDTO]` (`01-schema-extensions.md` 의 보강 후 스키마)

**용도**:
- 시뮬 에이전트가 SIM_VERIFIED 판정 시 적용할 BR 목록 조회
- explanation panel 에 BR description + operational_history 노출

### 1.2 GET `/api/ontology/business-rules/{br_fqn}`

```
GET /api/ontology/business-rules/{br_fqn}
```

**Response**: `BusinessRuleDTO | None`

**용도**: 특정 BR 의 enforced_by + violated_at_call + operational_history 상세 조회.

### 1.3 GET `/api/ontology/actions/{action_fqn}/business-rules`

```
GET /api/ontology/actions/{action_fqn}/business-rules
```

**Response**: `list[BusinessRuleDTO]` (이 Action 이 호출되는 흐름에서 enforce 되어야 할 BR)

**선정 알고리즘**:
1. Action 의 declared_on_term + 그 term 에 정의된 BR
2. Action 이 enforced_by 에 등록된 BR (이 Action 이 guard 역할인 경우)
3. transitive — delegates_to 안의 모든 sub-action 의 BR 합집합

**용도**: 시뮬 흐름의 ④ BR 검증 단계에서 "이 Action 실행 시 검증해야 할 BR 전체 집합" 조회.

### 1.4 GET `/api/ontology/code-methods/{method_fqn}/business-rules`

```
GET /api/ontology/code-methods/{method_fqn}/business-rules
  ?role={enforcer|violator|both}  # default = both
```

**Response**: `list[BusinessRuleDTO]`

**용도**:
- `role=enforcer` — 이 메서드가 enforce 하는 BR (가드 메서드)
- `role=violator` — 이 메서드가 violated_at_call 에 등장하는 BR (위반 가능 site)
- `role=both` — 양쪽 합집합

---

## 2. Action graph traversal endpoints

### 2.1 GET `/api/ontology/actions/{action_fqn}/delegates-to-tree`

```
GET /api/ontology/actions/{action_fqn}/delegates-to-tree
  ?max_depth=10                  # default 10, ge 1, le 30
  &include_optional={bool}       # default true (if 분기 안 호출도 포함)
  &include_in_loop={bool}        # default true
```

**Response**:
```python
class DelegationTreeNode(BaseModel):
    action_fqn: str
    is_in_loop: bool
    optional: bool
    invocation_count: int
    children: list["DelegationTreeNode"] = []  # depth-1 sub-action 트리
    cycle_detected: bool = False  # 순환 호출 마킹 (visited set)
```

**용도**:
- 시뮬 흐름 ① 단계에서 workflow 의 transitive 하위 Action 모두 펼침
- 21-step Algorithm 의 1 → 8 sub-step + A-a 루프 + Validator 호출 그래프를 한 번에 펼침

**예시** (workflow 의 트리):
```json
{
  "action_fqn": "scm.workflow.PerSlabIteration",
  "children": [
    {"action_fqn": "scm.action.SlabResultCompute", "is_in_loop": true, "children": [...]},
    {"action_fqn": "scm.action.ValidateSlabResult", "is_in_loop": true, "optional": false, "children": [
      {"action_fqn": "scm.guard.NoChemDeviation", "children": []}
    ]}
  ]
}
```

### 2.2 GET `/api/ontology/actions/{action_fqn}/realizing-methods`

```
GET /api/ontology/actions/{action_fqn}/realizing-methods
  ?repo_id={str}  # optional
```

**Response**:
```python
class RealizingMethodDTO(BaseModel):
    method_fqn: str
    realization: Realization  # 기존 ActionDTO.realizations 의 row
    is_primary: bool          # ActionDTO.realizes 가 비어있으면 본인이 PRIMARY
    parent_action_fqn: str | None  # realizes 의 첫 fqn
```

**용도**:
- 시뮬 흐름 ③ Java dispatch sandbox 단계에서 input runtime type 에 맞는 코드 위치 결정
- get_realizations_for_input_type 와 다른 점: 본 endpoint 는 input type 무관하게 **모든 realization 위치** 를 반환 (시뮬 explainer 에서 펼쳐 보기용)

---

## 3. Reverse lookup endpoints

> **3 가지 모두 "거꾸로" 탐색이 필요**: 시뮬 에이전트가 원인 추적 / 영향도 평가 / explanation 생성 시 핵심.

### 3.1 GET `/api/ontology/atoms/{atom_fqn}/used-by`

```
GET /api/ontology/atoms/{atom_fqn}/used-by
  ?repo_id={str}              # optional
  &usage={tr|anchor|composite|all}  # default all
```

**Response**:
```python
class AtomUsageDTO(BaseModel):
    usage_kind: Literal["type_realization", "anchor_binding", "composite_part"]
    target_fqn: str         # TR / AnchorBinding / Composite term fqn
    role: str               # "input", "output", "literal_match", "subterm" 등
    confidence: float | None
```

**용도**:
- 한 atomic (예: `scm.shared.atomic.thickness`) 이 어디에 쓰이는지 한눈에
- 영향도 평가 — 이 atomic 이 변하면 어떤 Action / Anchor / Composite 가 영향 받는가
- design-gap #28~#29 (atomic share 정책) 의 검증 데이터

### 3.2 GET `/api/ontology/code-methods/{method_fqn}/callers`

```
GET /api/ontology/code-methods/{method_fqn}/callers
  ?repo_id={str}        # optional
  &transitive={bool}    # default false
  &max_depth=5          # default 5, transitive=true 일 때만 의미
```

**Response**: `list[CallSiteDTO]` (기존 DTO 재사용 — `caller_method_fqn` / `callee_method_fqn` / `line` / `arg_resolutions` 등)

**용도**:
- BR 위반 추적 — violated_at_call 의 caller 를 한 단계 더 위로 추적
- 시뮬 epxlanation panel — "이 메서드는 X / Y / Z 에서 호출됨"

### 3.3 GET `/api/ontology/anchor-bindings/by-literal`

```
GET /api/ontology/anchor-bindings/by-literal
  ?literal={str}           # 예: "HR" / "230" / "OPEN"
  &literal_kind={string|number|enum}  # default string
  &repo_id={str}           # optional
```

**Response**: `list[AnchorBindingDTO]` (기존 DTO 재사용)

**용도**:
- 시뮬 에이전트가 "코드의 어떤 literal 이 어떤 anchor 에 binding 되어있는가" 역방향으로 조회
- design-gap #16 (anchor 마커 발견 정확도) 검증
- magic number / magic string refactoring 시 영향도 평가

---

## 4. DesignGap endpoints

### 4.1 GET `/api/ontology/design-gaps`

```
GET /api/ontology/design-gaps
  ?status={open|scheduled|resolved|wontfix}  # optional
  &severity={critical|major|minor}            # optional
  &area={str}                                 # optional
  &source_phase={A|B|C|D|E}                   # optional
  &related_action_fqn={str}                   # optional — 특정 Action 영향
```

**Response**: `list[DesignGap]` (`01-schema-extensions.md` 의 신규 엔티티)

**용도**:
- 시뮬 에이전트의 explanation panel — "이 결과는 design-gap #X 영향" 표기
- Phase E 진입 시 일괄 결정 대시보드 source

### 4.2 GET `/api/ontology/design-gaps/{gap_id}`

```
GET /api/ontology/design-gaps/{gap_id}
```

**Response**: `DesignGap | None`

### 4.3 GET `/api/ontology/actions/{action_fqn}/design-gaps`

```
GET /api/ontology/actions/{action_fqn}/design-gaps
  ?include_transitive={bool}  # default true — delegates_to 트리의 모든 gap 포함
```

**Response**: `list[DesignGap]` (이 Action 실행 시 영향 받을 가능성이 있는 gap)

**선정 알고리즘**:
1. `related_action_fqns` 에 본 action 이 있는 gap
2. transitive 모드 — `delegates-to-tree` 펼친 후 그 안의 모든 sub-action 의 gap 합집합

**용도**: 시뮬 결과 panel — "현재 결과는 #X / #Y 갭의 잠정 가정 위에 만들어졌다" 명시.

---

## 5. SimulationScenario endpoints

> 시나리오 카탈로그 조회. 실제 실행은 `03-simulation-api-spec.md` 의 `/api/simulation/*` router.

### 5.1 GET `/api/ontology/scenarios`

```
GET /api/ontology/scenarios
  ?kind={regression|boundary|drama|integration|br_violation}  # optional
  &target_action_fqn={str}                                     # optional
  &origin={incident|interview|synthetic}                       # optional
```

**Response**: `list[SimulationScenario]`

### 5.2 GET `/api/ontology/scenarios/{scenario_id}`

```
GET /api/ontology/scenarios/{scenario_id}
```

**Response**: `SimulationScenario | None`

### 5.3 GET `/api/ontology/actions/{action_fqn}/scenarios`

```
GET /api/ontology/actions/{action_fqn}/scenarios
  ?kind={...}  # optional
```

**Response**: `list[SimulationScenario]` (이 Action 을 target 으로 하는 시나리오)

**용도**:
- 시뮬 UI 의 scenario picker — "이 Action 에 대해 사용 가능한 시나리오 N개" 표기
- VerificationLevel 진급 — SIM_VERIFIED 진급에 사용된 scenario 추적

---

## 6. 호환성과 라우팅 순서

### 6.1 기존 18 endpoint 와 충돌 없음

신규 endpoint 의 path 는 모두 새로운 prefix:
- `/api/ontology/business-rules/...`
- `/api/ontology/atoms/...` (단, 기존 `/api/ontology/terms/...` 와 다름 — atoms 만 별도 prefix)
- `/api/ontology/anchor-bindings/by-literal` (기존 `/anchor-bindings` 가 method/action suffix 형태였음 — 본 endpoint 는 query 형)
- `/api/ontology/design-gaps/...`
- `/api/ontology/scenarios/...`

### 6.2 catchall 등록 순서

기존 router 의 주의사항이 그대로 적용:
- catchall `/terms/{fqn}` 보다 specific endpoint (`/terms/{term_fqn}/effective-parts` 등) 가 먼저 등록되어야 함
- 신규 endpoint 도 같은 원칙: `/business-rules` (list) 먼저, `/business-rules/{br_fqn}` 가 뒤

### 6.3 OpenAPI 자동 생성

기존과 동일하게 FastAPI 의 `/docs` 에 자동 노출. 신규 DTO (DelegationTreeNode / RealizingMethodDTO / AtomUsageDTO 등) 도 자동 schema 생성됨.

---

## 7. 구현 순서 권장

| # | 단계 | 의존 |
|---|---|---|
| 1 | 1.1~1.4 BR endpoints | `01-schema-extensions.md` Section 1 |
| 2 | 2.1 delegates-to-tree | `01-schema-extensions.md` Section 2 |
| 3 | 2.2 realizing-methods | `01-schema-extensions.md` Section 2 |
| 4 | 3.1~3.3 Reverse lookup | 기존 storage 에 인덱스만 추가 (스키마 변경 없음) |
| 5 | 4.1~4.3 DesignGap | `01-schema-extensions.md` Section 4 |
| 6 | 5.1~5.3 Scenario | `01-schema-extensions.md` Section 5 |

---

## 8. 검증 방법

각 endpoint 별 sanity test:

| endpoint | 입력 예 | 기대 |
|---|---|---|
| `business-rules` | `?declared_on_term=scm.slab.SlabResult` | DG001~005 + 원본=조정 BR 모두 반환 |
| `actions/.../delegates-to-tree` | `scm.workflow.SDSlabEntity_step_1_to_8` | 1~8 step Action 트리 + A-a 루프 안에 PerSlabIteration |
| `atoms/.../used-by` | `scm.shared.atomic.thickness` | TR / AnchorBinding / Composite 다수 반환 (Phase A+B+C 178 row 영향) |
| `code-methods/.../callers` | `SdWidthRangeAction.execute` | SdDesigner.runStep1 등 |
| `anchor-bindings/by-literal` | `?literal=HR` | proc[1] 자리 anchor 9개 중 일부 |
| `design-gaps?status=open` | (no params) | 36 항목 중 open 상태만 |
| `scenarios?kind=regression` | (no params) | P-2018-0098 / P-2019-0445 등 운영 사고 시나리오 |

---

## 9. design-gaps 와의 매핑

| design-gap # | 본 명세 endpoint 가 해소 |
|---|---|
| #18 BR enforcement 추적 | 1.1~1.4 |
| #19 Guard 누락 검출 | 1.4 (role=violator) |
| #28 workflow 호출 그래프 | 2.1 |
| #5 Java dispatch sandbox | 2.2 |
| #16 anchor 마커 발견 | 3.3 |
| #29 atomic share 영향도 | 3.1 |
| #34 SimulationScenario 카탈로그 | 5.1~5.3 |
| #36 design-gap 1급 객체 | 4.1~4.3 |

---

마지막 업데이트: 2026-05-10
