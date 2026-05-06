# Step C4 — Mapping Layer 신설 (Action 1급 + 다형성 + AnchorBinding + VerificationLevel)

**완료**: 2026-05-02
**기반 결정**: Q1' (Action 1급) + Q4' (fragment-level anchor) + Q7' (workflow=Action.kind) + Q8 (Strict gate) + Q9 (정형 effect) + D3 (Realization 다형성 + dispatch_source) + C2 (path syntax)

## 산출물 요약

| 항목 | 수치 |
|---|---|
| 새 모듈 (backend/modeling/mapping_layer/) | 6 파일 |
| Tests (tests/mapping_layer/) | 4 파일, **47/47 PASSED** |
| 총 LOC (mapping_layer + tests) | 1,632 |
| 누적 (C2+C3+C4) tests | **92/92 PASSED** (0.60s) |

## 디렉토리

```
backend/modeling/mapping_layer/
├── __init__.py         # public exports
├── schema.py           # Action / ActionParam / ActionEffect / Realization / AnchorBinding / TypeRealization
├── orm.py              # SQLAlchemy ORM (4 테이블)
├── store.py            # CRUD store (Action ↔ Realization 분리 저장 + 합쳐 반환)
├── path.py             # Path syntax parser (params[0]<RushOrder>.spec.diameter.range[1]) + validator
└── verification.py     # VerificationLevel 자동 계산 + can_simulate gate

tests/mapping_layer/
├── __init__.py
├── test_schema.py                   # 11 invariant tests
├── test_path.py                     # 19 parser + validator tests
├── test_store_and_verification.py   # 13 store CRUD + verification tests
└── test_e2e_action.py               # 4 단계 통합 (Code+Domain+Mapping)
```

## 모델

### Action (1급, Q1'=A)
- fqn / label / kind (pure_function | effectful | workflow) / is_abstract / declared_on_term
- params (typed, ActionParam: name + type + object_ref_term + unit + range + nullable + anchor_locator + confirmed)
- output (ActionOutput)
- preconditions / postconditions (BusinessRule fqn 참조)
- **effects** (정형 — op + target_term + target_attr, Q9=C)
- **realizations** (다중, 다형성)
- sub_actions (workflow 일 때, Q7'=A)
- verification_level / signature_locked_at / confirmed_by

**Schema invariants**:
- `kind=pure_function` → effects 비어있어야
- `kind=workflow` → realizations 비어있고 sub_actions 채워야
- `ActionParam.type=object_ref` → object_ref_term 필수, 그 외 type 에선 금지
- `range` 형식 + min ≤ max

### Realization (다형성, D3)
- `code_method_fqn` + `applies_to_code_type_fqn` (subtype filter, None=base)
- `is_override` / `dispatch_source` (D3 9-enum: SINGLE_IMPL/INSTANCEOF_GUARD/ANNOTATION/FACTORY_BRANCH/GENERIC_BOUND/STRATEGY_MAP/REFLECTION/USER_CONFIRMED/STATIC_UNRESOLVED)
- scope (PRIMARY | PARTIAL) / confidence / confirmed

같은 (Action, code_method, subtype) 중복 차단 — UniqueConstraint.

### AnchorBinding (fragment-level, Q4'=A)
- id (sha1) / anchor_locator / code_method_fqn
- target_action_fqn / target_slot (path with subtype cast)
- confidence / source / confirmed

**메서드 매핑 없이도 anchor 가 Action 슬롯에 binding 가능** (사각지대 흡수).

### TypeRealization (CodeType ↔ BusinessTerm)
- code_type_fqn ↔ term_fqn / scope (primary | partial)
- 같은 (code, term, scope) 중복 차단

## Path syntax (C2=A 풍부)

| 문법 | 예시 | 의미 |
|---|---|---|
| `params[i]` | `params[0]` | param 참조 (object_ref 면 추가 traversal) |
| `params[i]<Subtype>` | `params[0]<RushOrder>` | subtype cast (Java instanceof) |
| `.role_name` | `.spec` | composition role 따라 자손 term |
| `[i]` / `[-1]` / `[*]` | `.chemical[-1]` | collection index / 마지막 / 전체 |
| `[?(filter)]` | `[?(active)]` | 필터 (인식만, Phase 2) |
| `output.field` | `output.value` | output 참조 |
| `preconditions[i]` / `effects[i].field` | `effects[1].target_term` | Action slot 직접 |

**subtype cast 매칭**: exact fqn / label / fqn endswith / **CamelCase→snake 변환** (RushOrder → rush_order). Java class name 자동 호환.

**validator**: BusinessTerm 그래프 traversal 가능 여부 검사 — atomic.range 인덱싱 OK, subtype cast 가 descendants 안에 있어야, role_name 이 effective_parts 에 있어야.

## VerificationLevel state machine (자동 계산)

| Level | 조건 |
|---|---|
| **UNMAPPED** | Realization 0 (workflow 면 sub_actions 도 0) |
| **DRAFT** | Realization 있음, but params 미확정 또는 primary realization 미확정 |
| **SIGNATURE_LOCKED** | params 모두 confirmed + primary realization 1개+ confirmed |
| **BODY_ANCHORED** | + anchor binding 모두 confirmed |
| **SIM_VERIFIED** | + 외부 신호 sim_passed=True (A2 Simulation Agent 가 갱신) |
| **PR_PROVEN** | + 외부 신호 pr_proven=True (A3 PR Agent 가 갱신) |

`can_simulate(level)` — Q8=A Strict gate: SIGNATURE_LOCKED 이상이어야 시뮬 가능.

## E2E — Order 도메인 위에 주문_검증 Action

```
Code Layer:
  abstract com.scm.Order { abstract validate() }
  com.scm.RushOrder extends Order { @Override validate() }
  com.scm.StandardOrder extends Order { @Override validate() }

Domain Layer:
  주문 (composite, abstract, root_entity)
  ├── 긴급주문 (extends 주문) HAS priority (atomic int [1,5])
  ├── 표준주문 (extends 주문)
  └── HAS spec → 주문스펙 HAS diameter (atomic float, mm, [0,300])

Mapping Layer:
  TypeRealization: com.scm.{Order, RushOrder, StandardOrder} ↔ t.{order, rush_order, standard_order}
  Action(action.scm.order_validate, abstract, declared_on_term=t.order):
    params=[(주문, t.order, confirmed=True)]
    realizations=[
      com.scm.RushOrder.validate     applies_to=RushOrder    primary confirmed
      com.scm.StandardOrder.validate applies_to=StandardOrder primary confirmed
    ]
  AnchorBinding: literal:1 in RushOrder.validate → params[0]<RushOrder>.priority.range[0]

Path validation:
  params[0]                                       ✓
  params[0].spec.diameter                         ✓ (HAS-A traversal)
  params[0].spec.diameter.range[1]                ✓ (atomic.range 인덱스)
  params[0]<RushOrder>.priority                   ✓ (subtype cast → priority)
  params[0]<RushOrder>.priority.range[0]          ✓
  preconditions[0]                                ✓ (root slot)

VerificationLevel: BODY_ANCHORED (params confirmed + anchor confirmed) → can_simulate ✓
```

## 검증

| 검사 | 결과 |
|---|---|
| `pytest tests/mapping_layer/` | **47/47 PASSED** (0.25s) |
| 누적 `pytest tests/{code,domain,mapping}_layer/` | **92/92 PASSED** (0.60s) |
| `python -c "import backend.main"` | ✓ OK |
| `frontend tsc --noEmit` | ✓ 에러 없음 |

## 다음 step

**C5 — Query API**: Agent 가 호출할 깨끗한 boundary. Term/Code/Action/Anchor/Search 5 종 API + DTO + REST endpoint + OpenAPI spec + 정적 검사 도구 (Agent 가 Core internal import 시 build 실패).

승인 시 시작.
