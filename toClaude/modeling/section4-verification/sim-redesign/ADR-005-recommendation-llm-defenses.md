# ADR-005: Recommendation Engine 의 LLM 방어 mechanism (4 layer defense)

작성일: 2026-05-13
상태: 확정 (사용자 결정, 2026-05-13)
선행: ADR-002 (Two-Engine + plugin), ADR-012 (LLM-agnostic API)
관련: ADR-003 (Integrator), ADR-004 (Schema Layer), ADR-010 (Phase α lessons)
관련 결정: D7 (ADR-005 작성), D5 (LLM-agnostic, sibling ADR-012)

## 컨텍스트

Recommendation Engine (ADR-002 의 D2) 가 LLM 의 reasoning 을 활용. LLM 의 본질적 risk:
- **Hallucination** — 없는 entity / column / annotation 을 만들어냄
- **Spec drift** — 요구와 다른 변경 제안
- **Validation gap** — 생성된 schema diff 가 syntactic 으로 valid 하지만 semantic 으로 broken
- **Silent inconsistency** — proposal 의 일부 component 만 변경, 다른 component 와 conflict

Round 2 종합 (`SYNTHESIS-ROUND2.html`) 의 "4 defense mechanism" 이 이 risk 의 mitigation. 본 ADR 이 정식 명세.

DECISIONS-CONFIRMED.md 의 D7 (ADR-005 작성) + D5 (LLM-agnostic, sibling ADR-012) 결합.

## 결정

**Recommendation Engine 의 LLM 호출 전후로 4 defense layer 적용**:

```
1. Pre-call defense  — Context grounding
2. Post-call defense — Output validation
3. Runtime defense   — Oracle verification
4. Lifecycle defense — Human review gate
```

각 layer 가 independent — 단일 layer 실패가 다음 layer 의 trigger 가 아닌 **hard barrier**.

### 1. Pre-call defense — Context grounding

LLM 호출 전, prompt 에 ontology 의 실제 entity / column / annotation 만 reference 하도록 grounding:

```python
def build_grounded_prompt(user_request: str, ontology: Ontology, plugin: str) -> LLMRequest:
    relevant_entities = ontology.query_entities(plugin, related_to=user_request)
    relevant_schemas = ontology.query_schemas(plugin, related_to=user_request)
    relevant_terms = ontology.query_business_terms(plugin, related_to=user_request)

    return LLMRequest(
        system_prompt=f"""
            You are a schema recommender for the {plugin} system.
            Your output MUST reference ONLY the following entities and schemas:

            ## Existing entities (Java code):
            {format_entities(relevant_entities)}

            ## Existing schema:
            {format_schemas(relevant_schemas)}

            ## Existing business terms:
            {format_terms(relevant_terms)}

            If you need to propose a NEW entity / column / term, mark it with [NEW] prefix.
            DO NOT reference entities or schemas not in the lists above.
        """,
        user_prompt=user_request,
        response_schema=PROPOSAL_SCHEMA,
        ...
    )
```

이는 hallucination 의 primary defense — LLM 의 reasoning 이 ontology 의 실제 artifact 에 anchored.

### 2. Post-call defense — Output validation

LLM 의 raw output 을 strict schema validation + cross-reference check:

```python
def validate_proposal(raw: dict, ontology: Ontology, plugin: str) -> ValidationResult:
    errors = []

    # 2.1 Schema validation (JSON schema)
    try:
        prop = Proposal.model_validate(raw)
    except ValidationError as e:
        errors.append(SchemaError(e))
        return ValidationResult(status="FAIL", errors=errors)

    # 2.2 Cross-reference check
    if prop.schema_diff:
        for table in prop.schema_diff.altered_tables:
            if not ontology.has_table(plugin, table.name) and not table.name.startswith("[NEW]"):
                errors.append(CrossRefError(f"Table {table.name} not in ontology and not marked [NEW]"))

        for col_ref in prop.schema_diff.column_references:
            if not ontology.has_column(plugin, col_ref.table, col_ref.column):
                errors.append(CrossRefError(f"Column {col_ref} not in ontology"))

    if prop.code_diff:
        for entity_ref in prop.code_diff.entity_references:
            if not ontology.has_entity(plugin, entity_ref) and not entity_ref.startswith("[NEW]"):
                errors.append(CrossRefError(f"Entity {entity_ref} not in ontology"))

    # 2.3 Consistency check
    if prop.schema_diff and prop.code_diff:
        consistency = check_schema_code_consistency(prop.schema_diff, prop.code_diff, ontology)
        errors.extend(consistency.errors)

    return ValidationResult(
        status="PASS" if not errors else "FAIL",
        errors=errors,
        proposal=prop if not errors else None,
    )
```

Validation 실패 시 LLM 재호출 (retry with error feedback) 또는 abort.

### 3. Runtime defense — Oracle verification

Validation 통과한 proposal 은 ADR-003 의 Integrator → Verification Engine 의 oracle 호출:

```python
def verify_proposal(prop: Proposal, fixtures: list[FixtureRef]) -> OracleResult:
    # Verification Engine 이 fixture 의 baseline + proposal 적용 후 twin 결과 비교
    return verification_engine.run_oracle(prop, fixtures)
```

Oracle 의 4-tier result:
- **PASS**: 모든 fixture 의 R3/R4/R5 통과 → proposal 진행
- **FAIL_BREAKING**: 기존 fixture 가 break → proposal 의 backward-incompatible 변경. User 결정 필요
- **FAIL_DRIFT**: 출력은 동일하나 trace 가 다름 → 의도된 변경인지 user 확인
- **INCONCLUSIVE**: 일부 fixture 가 stuck (timeout, error) → debugging 필요

Oracle 결과는 ADR-003 의 ORACLED state 로 전이.

### 4. Lifecycle defense — Human review gate

Oracle 통과한 proposal 도 user review 의무 (ADR-003 의 REVIEWED state):

```
User review UI 표시 항목:
1. Proposal 의 natural language summary
2. Schema diff (visual: 색깔 표시된 SQL)
3. Code diff (visual: side-by-side Java)
4. Ontology diff (visual: graph node 추가/제거)
5. Oracle result by fixture (PASS/FAIL 상태)
6. LLM 의 reasoning trace (prompt + response + retry history)
7. Risk markers (LLM 의 [NEW] 마킹 / cross-ref warning / consistency warning)

User decision options:
  - ACCEPT (모두 적용)
  - REJECT (폐기)
  - CHANGE_REQUEST (refinement instruction 작성 → Recommendation Engine 의 refinement loop)
  - PARTIAL_ACCEPT (일부만 적용, 나머지 reject)
```

User review 없는 auto-merge 는 금지 (사용자 메모리 `feedback_simulation_design.md` "no MVP" 일관).

## 4 layer 의 cross-validation flow

```
LLM raw output
     │
     ▼
[1] Context grounding   ← 사전 차단
     │
     ▼
[2] Output validation   ← 즉시 차단 + retry
     │
     ▼
[3] Oracle verification ← 의도 검증
     │
     ▼
[4] Human review        ← 최종 결정
     │
     ▼
   MERGED
```

## Anti-pattern detection (ADR-010 의 L1 lesson 활용)

ADR-010 의 L1 (KNOWN_DIVERGENCE root cause) 가 specific anti-pattern 의 catalog:

```python
ANTI_PATTERN_CATALOG = {
    "bigdecimal_python_drift": {
        "java_signal": ["BigDecimal", "MathContext", "RoundingMode"],
        "python_risk": "decimal.ROUND_HALF_UP != Java's RoundingMode.HALF_UP for negative numbers",
        "mitigation": "Use Java RoundingMode mapping table in plugin's contracts/",
    },
    "implicit_null_handling": {
        "java_signal": ["Optional.empty()", "null check"],
        "python_risk": "None vs MissingType vs Optional 의 silent conflation",
        "mitigation": "Plugin 의 null 처리 contract 명시",
    },
    "transaction_scope_drift": {
        "java_signal": ["@Transactional(propagation=...)"],
        "python_risk": "Twin 의 stub TX 가 Java TX boundary 와 시점 불일치",
        "mitigation": "TX boundary 명시적 modeling (ADR-002 의 stub pattern)",
    },
    "validation_silence": {
        "java_signal": ["ValidationResult", "@Valid", "ConstraintValidator"],
        "python_risk": "Validation error 가 Twin 에서 silent skip",
        "mitigation": "Validation error 를 일관된 exception 으로 raise",
    },
    "constants_drift": {
        "java_signal": ["public static final", "enum constant"],
        "python_risk": "Python 의 constant module 과 Java 의 final 의 value 시점 차이",
        "mitigation": "Plugin 의 constants extraction 자동화",
    },
    # ... Phase α 의 5 KNOWN_DIVERGENCE 를 catalog 화. 향후 incremental 추가.
}

def detect_anti_patterns(prop: Proposal) -> list[AntiPatternWarning]:
    warnings = []
    for ap in ANTI_PATTERN_CATALOG.values():
        if matches_signal(prop, ap.java_signal):
            warnings.append(AntiPatternWarning(
                pattern=ap,
                location=...,
                suggested_mitigation=ap.mitigation,
            ))
    return warnings
```

Anti-pattern warning 은 user review 단계에서 표시 (4번째 defense 의 input).

## Retry strategy

Defense layer 1-2 의 실패 시 LLM 재호출:

```python
def submit_with_retry(request: LLMRequest, max_retries: int = 3) -> Proposal:
    last_errors = None
    for attempt in range(max_retries):
        response = provider.invoke(request)
        validation = validate_proposal(response.content, ontology, plugin)
        if validation.status == "PASS":
            return validation.proposal

        last_errors = validation.errors
        # Retry with error feedback
        request = LLMRequest(
            system_prompt=request.system_prompt + f"\n\n## Previous attempt errors:\n{last_errors}",
            user_prompt=request.user_prompt + "\n\nPlease fix the errors above.",
            ...
        )

    raise MaxRetriesExceeded(last_errors)
```

Retry 횟수는 plugin manifest 의 `[recommendation].max_retries` 로 override 가능 (default 3).

## 결과 / 영향

- LLM 의 hallucination + drift + validation gap + silent inconsistency 의 4-layer defense
- ADR-010 의 L1 lesson (Phase α anti-patterns) 가 anti-pattern catalog 로 보존
- Validation 실패 의 retry strategy 명시 — silent failure 차단
- User review 의무화 — auto-merge 금지 ("no MVP" 일관)

## Honest limits

- LLM 의 reasoning 자체의 quality 는 framework 가 enforce 못 함 — 4 layer 는 detection + barrier, generation 자체 quality 는 provider 의 model 능력에 의존
- Anti-pattern catalog 의 coverage 는 incremental 증가 — phase 1 은 Phase α 5 lesson 만
- Context grounding 의 ontology query 정확도 의존 — query miss 시 LLM 이 referenceable artifact 부족으로 generation 실패 (false negative)
- Retry loop 의 무한 가능성 — `max_retries` 로 cap, but quality degradation 가능

## 참조

- DECISIONS-CONFIRMED.md (D7, D5)
- ADR-002 (Two-Engine + plugin)
- ADR-003 (Integrator + proposal lifecycle)
- ADR-004 (Schema Layer)
- ADR-010 (Phase α lessons L1 — anti-pattern catalog source)
- ADR-012 (LLM-agnostic, sibling)
- `SYNTHESIS-ROUND2.html` (4 defense mechanism motivation)
