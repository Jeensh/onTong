# Step C2 — Code Layer 신설

**완료**: 2026-05-02
**기반 결정**: D1=C (Two-Layer 분리) + D2=A (Class.role 자동 분류) + D3=A+ (CallSiteAnalyzer)

## 산출물 요약

| 항목 | 수치 |
|---|---|
| 새 모듈 (backend/modeling/code_layer/) | 6 파일 |
| Tests (tests/code_layer/) | 4 파일, **15/15 PASSED** |
| 총 LOC (code_layer + tests) | 1,833 |
| 보존 모듈 활용 | java_parser + Spring 10 analyzer (output 만 어댑터) |

## 디렉토리

```
backend/modeling/code_layer/
├── __init__.py            # public exports
├── schema.py              # Pydantic DTO (CodeType / CodeField / CodeMethod / CallSite)
├── orm.py                 # SQLAlchemy ORM (4 테이블 — code_types/fields/methods/call_sites)
├── store.py               # CRUD store (DTO ↔ ORM 변환, repo 격리)
├── adapter.py             # 기존 ParseResult → 새 schema 매핑
├── role_classifier.py     # Class.role / Method.role 자동 분류
└── callsite_analyzer.py   # 정적 dispatch 추론 (Case 1/2/3 자동, 모호 → 사용자 큐)

tests/code_layer/
├── __init__.py
├── test_schema.py         # 9 invariant tests
├── test_store.py          # 6 CRUD tests
└── test_e2e.py            # 1 통합 (Java 4파일 → adapter → role → store → CallSite)
```

## 모델 (Pydantic + SQLAlchemy)

### CodeType
- fqn (PK) / simple_name / package
- kind: class / abstract_class / interface / enum / record
- **role**: domain / framework / infra / unknown (D2=A)
- is_abstract (interface 자동 True)
- extends (단일, interface 면 None) + implements[] + extends_interfaces[]
- fields[] / methods[] (cascade)
- modifiers / annotations
- repo_id

### CodeMethod
- fqn (PK) + name + parent_type_fqn (FK)
- params (typed) + return_type
- **role**: business / helper / adapter / unknown (Q2'=C 정합)
- is_abstract / is_override / is_constructor
- body_text (raw Java)
- **anchors[]** (param/local/return/branch/literal/field/field_access — P14 호환)
- extra (mutations / value_flow / extracted_rules)

### CallSite (D3 7-case)
- caller_method_fqn / callee_simple_name / callee_receiver_static_type / line
- possible_runtime_types[] (CallCandidate: code_type_fqn + score + reason)
- confidence (1.0 = 단일 확정, < 1.0 = 모호)
- **analysis_source**: single_impl / instanceof_guard / annotation / factory_branch (자동) / generic_bound / strategy_map / reflection / static_unresolved / user_confirmed
- needs_user_confirm + user_confirmed_type/at

## CallSiteAnalyzer 1차 구현 (Case 1~3 자동)

| Case | 트리거 | 처리 |
|---|---|---|
| **SINGLE_IMPL** | 인터페이스에 method 가진 impl 1개 | confidence=1.0, 그 impl 확정 |
| **ANNOTATION** | @Service/@Component 단일 등록 | confidence=1.0, 그 클래스 확정 |
| **자체 정의** (override 없음) | 일반 class, subtype 에 override 없음 | confidence=1.0, 자기 자신 확정 |
| **STATIC_UNRESOLVED** | 다중 impl / 다중 override / receiver 모름 | needs_user_confirm=True, 후보 list + reason 컨텍스트 |

**Case 4 (FACTORY_BRANCH) / Case 2 (INSTANCEOF_GUARD)**: body AST 분석 필요 — Phase 2 (별도 step).

## 검증

| 검사 | 결과 |
|---|---|
| `pytest tests/code_layer/` | **15/15 PASSED** (0.21s) |
| `python -c "import backend.main"` | ✓ OK |
| Java parser + Spring analyzer import | ✓ OK |
| frontend tsc | ✓ 에러 없음 |

## E2E 검증 — Java 샘플 (Order/StandardOrder/RushOrder/Trackable)

```
파싱: 4 .java → 4 ParseResult
어댑팅: 4 CodeType
역할 분류:
  Order(abstract_class) → DOMAIN
  StandardOrder(class)  → DOMAIN
  RushOrder(class)      → DOMAIN
  Trackable(interface)  → DOMAIN
  Order.validate()      → BUSINESS (abstract)
  RushOrder.validate()  → BUSINESS (override=True)
  Order.getOrderNo()    → ADAPTER (getter)

CallSiteAnalyzer:
  validate@Order        → STATIC_UNRESOLVED (StandardOrder/RushOrder 후보 → 사용자 큐)
  getTrackingNo@Trackable → SINGLE_IMPL (Order 의 단일 구현, conf=1.0)
  getOrderNo@Order      → SINGLE_IMPL (override 없음, 자체 conf=1.0)

Store:
  upsert 4 → list 4 → idempotent re-upsert → 4 (변경 없음)
  CallSite 3 upsert → ambiguous 1
```

## 다음 step

**C3 — Domain Layer**: BusinessTerm 신모델 (kind=atomic|composite + facets is_abstract/is_interface/is_root_entity/struct_like_hint) + Inheritance (extends/implements) + Composition + effective_parts resolver. SQLite 신 schema. 기존 BusinessTerm 데이터는 이미 archive (Q10=D).

승인 시 시작.
