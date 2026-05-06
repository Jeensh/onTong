# Step C3 — Domain Layer 신설

**완료**: 2026-05-02
**기반 결정**: D1=C (Two-Layer 분리, Domain layer) + C1=A→D1 (kind 단순화) + C2=A (path syntax)

## 산출물 요약

| 항목 | 수치 |
|---|---|
| 새 모듈 (backend/modeling/domain_layer/) | 6 파일 |
| Tests (tests/domain_layer/) | 4 파일, **30/30 PASSED** |
| 총 LOC (domain_layer + tests) | 1,518 |
| 누적 (C2+C3) tests | **45/45 PASSED** (0.40s) |

## 디렉토리

```
backend/modeling/domain_layer/
├── __init__.py         # public exports
├── schema.py           # Pydantic DTO (BusinessTerm + Inheritance + Composition + BusinessRule)
├── orm.py              # SQLAlchemy ORM (4 테이블)
├── store.py            # CRUD store (DTO ↔ ORM, repo 격리, idempotent)
├── validator.py        # 그래프 검증 (사이클 / atomic-parts / dangling)
└── resolver.py         # ancestors / descendants / effective_parts (transitive closure)

tests/domain_layer/
├── __init__.py
├── test_schema.py            # 12 invariant tests
├── test_store.py             # 7 CRUD tests
├── test_validator_resolver.py # 10 graph 검증 + traversal
└── test_e2e_order.py         # 1 통합 (주문 도메인 13 terms + Inheritance + Composition + Rule)
```

## 모델 (v5 결정 정합)

### BusinessTerm (2-kind + 4 facets)
- **kind**: atomic | composite (2종 — v4 의 4-kind 폐기)
- **facets** (조합): is_abstract / is_interface (→auto abstract) / is_root_entity / struct_like_hint
- atomic 일 때 value_type / unit / range / enum_values
- repo_id / source / confirmed
- Schema invariants: atomic+interface 금지 / atomic+struct_hint 금지 / range[min] ≤ range[max] / range len=2

### Inheritance (Java OO 정합)
- child_fqn → parent_fqn
- kind: extends (단일) | implements (다중)
- self-loop schema 단계 차단

### Composition (HAS_A)
- parent_fqn → child_fqn + role_name (+ cardinality 1:1/0:1/1:N/0:N + required)
- self-loop 차단
- 같은 (parent, role) 중복은 store 단계 replace

### BusinessRule
- statement / severity (hard|soft) / terms_ref[]
- Action.preconditions/postconditions 가 fqn 으로 참조

## Validator (그래프 수준)

| 검사 | code | severity |
|---|---|---|
| atomic 의 parts 금지 | `ATOMIC_HAS_PARTS` | error |
| inheritance 사이클 (DAG 위반) | `INHERITANCE_CYCLE` | error |
| composition 사이클 | `COMPOSITION_CYCLE` | error |
| dangling parent / child | `*_DANGLING_*` | error |
| 같은 (parent, role) 중복 | `COMPOSITION_DUPLICATE_ROLE` | warning |

three-color DFS 사이클 검출. ValidationError 리스트 반환 (raise X) — 사용자 큐로.

## Resolver (transitive closure)

- `ancestors(fqn, inh)` — 모든 조상 (extends + implements 모두 따라감)
- `descendants(fqn, inh)` — 모든 자손
- `effective_parts(fqn, inh, comp)` — own + inherited parts. **자손이 같은 role 가지면 자손 우선** (override 의미)

사이클 보호: visited set + max_depth=32 안전망.

## E2E — 주문 도메인 (13 terms + 3 inheritance + 9 composition + 2 rules)

```
주문 (composite, root_entity, abstract)
├── implements Trackable (interface, abstract)
│   └── trackingNo (atomic string)
├── HAS spec (1:1) → 주문스펙 (composite, struct_like)
│   └── HAS diameter → 직경 (atomic float, mm)
├── HAS progress (1:1) → 진행관리정보 (composite)
├── HAS quality (1:1) → 품질설계정보 (composite)
└── HAS chemical (1:N) → 화학성분 (composite, struct_like)
    ├── HAS C → C 함량 (atomic float, %, [0.10, 0.25])
    └── HAS Mn → Mn 함량 (atomic float, %, [1.20, 1.60])

표준주문 EXTENDS 주문
긴급주문 EXTENDS 주문
└── HAS priorityLevel → 우선도 (atomic int, [1, 5])

Rules:
- rule.c_range: 0.10 ≤ C ≤ 0.25 (HARD, refs t.c_pct)
- rule.priority_range: 1 ≤ priority ≤ 5 (HARD, refs t.priority_level)
```

**effective_parts(긴급주문)** = {spec, progress, quality, chemical, trackingNo, priorityLevel} ✓
- 자기 own: priorityLevel
- 부모 (주문) 에서: spec, progress, quality, chemical
- 부모의 implements (Trackable) 에서: trackingNo

## 검증

| 검사 | 결과 |
|---|---|
| `pytest tests/domain_layer/` | **30/30 PASSED** (0.22s) |
| 누적 `pytest tests/code_layer/ tests/domain_layer/` | **45/45 PASSED** (0.40s) |
| `python -c "import backend.main"` | ✓ OK |
| `frontend tsc --noEmit` | ✓ 에러 없음 |

## 다음 step

**C4 — Mapping Layer**: TypeRealization (CodeType ↔ BusinessTerm) + Action (params/output/preconditions/effects/realizations 다형성) + Realization (dispatch_source) + AnchorBinding (fragment-level + composite path with subtype cast) + VerificationLevel state machine.

승인 시 시작.
