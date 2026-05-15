# Perspective: Recommendation Specialist — LLM-based Reasoning Engine

## 1. Summary

Recommendation Engine 은 ADR-002 가 신설한 두 번째 1급 use case 묶음 (UC4 schema / UC5 code / UC6 ontology evolution) 의 단일 엔진이다. Verification Engine (ADR-001 Anchored Twin Synthesizer) 이 *현재 코드의 진실을 결정론적으로 재생산* 한다면, Recommendation Engine 은 *그 진실 위에서 변경의 후보를 LLM 으로 reasoning* 한다. 두 엔진은 ontology + Java AST + Schema layer 를 공유하지만, mechanism 이 결정성 vs reasoning 으로 갈리고, 통신은 한 방향 — **Recommendation 이 propose → Verification 이 simulate → diff 가 oracle**. LLM hallucination / context overflow / non-determinism 을 막기 위해 (a) ontology 행을 *typed* tool 로 노출, (b) reasoning 을 결정론적 단계 (parse/locate/gap/propose/validate) 로 jail, (c) 출력은 schema SQL + code diff + ontology JSON delta *structured artifact*, (d) Verification Engine 호출이 매 proposal 의 회귀 fence. "고객사 슬랩 두께 override" 를 end-to-end 7-step 으로 풀어 보이고, 실패모드와 비결정성 처리를 honest 하게 catalog 한다.

## 2. Architecture — Recommendation Engine components

```
                Verification Engine        Recommendation Engine
                ───────────────────        ─────────────────────
                Anchored Twin Synth ◄────── (oracle RPC)
                Twin Runner                    (1) Feature Spec Parser
                Oracle Differ                  (2) Ontology Locator (typed tools)
                Trace Diff Analyzer            (3) Gap Identifier (deterministic)
                                               (4) Proposal Composer (LLM, jailed)
                ┌── Shared substrate ──┐         ├── Schema Recommender   (UC4)
                │  Schema Layer (5th)  │◄────┤   ├── Code Recommender     (UC5)
                │  Mapping / Domain    │     │   └── Ontology Evolver     (UC6)
                │  Code AST            │     │  (5) Proposal Validator
                └──────────────────────┘     │      ├── static (SQL/Python parse,FQN)
                                              │      └── Verification RPC (regen+regression)
                                              │  (6) Iteration Coordinator
                                              └─ feedback loop
```

핵심 invariant: **LLM 은 step 4 안에서만 reasoning**. Step 1-3 은 결정론적 parsing + DB query, step 5 는 결정론적 validator + Verification call, step 6 는 사용자와의 dialog state-machine. LLM 이 보는 context 는 step 2 의 typed tool 출력 + step 3 의 gap row 이므로 사이즈가 bounded.  Output 도 step 4 끝에 Pydantic schema 검증 — 잘못된 shape 면 reject + retry.

## 3. LLM context assembly

문제: 100K+ doc 가정 시 전체 ontology dump 는 token budget (예: 200K) 을 초과. v2 작은 case 도 985 method × 38 action × 163 anchor 이미 수만 토큰.

전략 — **retrieval before reasoning**:

| Step | LLM 이 보는 것 | 토큰 |
|---|---|---|
| Spec parser | 자연어 query + optional form | 50-200 |
| Locator output | query 와 매칭된 typed JSON row (term/action/anchor 최대 N=20 + 2-hop graph) | 1.5-4K |
| Gap identifier | "missing 의 결정적 diff" 표 | 0.3-0.8K |
| Schema/Code 추론 | 위 + Schema Layer + 인접 Java AST snippet | 2-6K |
| Validation feedback | parse 에러 / verification diff | 0.2-2K |

총 5-15K. retrieval k=20 cap 으로 100K 문서에서도 동일. **Schema Layer + BusinessTerm.synonyms + Action.name_ko 를 SQLite FTS5 인덱스** (이미 ontology 가 FTS5 사용 가정, `feedback_scale_5k_classes.md` 정합).

LLM 은 raw row 가 아니라 *typed schema* 로 받아서 hallucination 시 schema 검증으로 reject:

```jsonc
{
  "found_terms":[
    {"fqn":"term.scm.customer","name_ko":"고객사",
     "code_realiz":[{"java_type":"customerCd","table":"CUSTOMER_STD"}]},
    {"fqn":"term.scm.slab.slab_thickness","name_ko":"슬랩 두께",
     "code_realiz":[{"java_field":"SDSlabEntity.slabThickness"}]}],
  "found_actions":[
    {"fqn":"action.scm.thickness_실행","verification_level":"body_anchored",
     "current_source":"CAST_SPEC.SLAB_THICKNESS lookup",
     "anchors":[{"line":57,"slot":"body.service_lookup"},
                {"line":70,"slot":"body.set_output"}]}],
  "schema_layer":{
    "table":"CUSTOMER_STD",
    "current_columns":["CMP_CD","ORG_CD","PRIORITY","PRODUCT_CD",
                       "CUSTOMER_CD","PKG_WGT_HIGH","PKG_WGT_LOW"]}
}
```

CustomerStdJpo 의 column 목록은 `sample-repos/slab-design-real_v2/slab-design-store/src/main/java/com/example/slabdesign/store/sd/std/jpo/CustomerStdJpo.java:21-57` 에서 확인 — 두께 override column 부재 자동 검출.

## 4. Three sub-engines

**Schema Recommender (UC4)** — 입력: spec + locator + schema_layer. 출력: 1+개 alternative `(name, ddl_sql, rationale, blast_radius)`. Mechanism: 변경 패턴 라이브러리 (10-15: optional column / override table / mapping table / temporal column / soft delete / audit ...) 의 *각 패턴별 separate generation* 후 best 1-2 surface. 한 LLM call 이 모든 후보 합성하면 silent hallucination 위험.

**Code Recommender (UC5)** — 입력: 확정된 schema diff + spec + 영향 action FQN + 인접 anchor snippet. 출력: *Java method 의 anchor-precise diff skeleton* + 새 anchor 후보 (slot + locator + expected line). ADR-001 truth 상 사람은 Java 만 편집하므로 **코드 추천도 Java 에 대한 것**. Python 은 ontology 재실행 시 자동 합성.

**Ontology Evolver (UC6)** — 입력: schema diff + code diff + spec. 출력: BusinessTerm / BusinessRule / AnchorBinding 의 추가/수정 JSON delta. 산출물은 modeling UI 가 import → Section 2 confirm 후 ontology DB 반영. *자동 commit 없음* — modeling UI 가 권한 경계.

세 sub-engine 은 직렬 — schema → code → ontology. 단 사용자가 부분 요청하면 sub-engine 단독 invoke 가능.

## 5. Concrete worked example — "고객사 슬랩 두께 override"

사용자 query: **"고객사가 슬랩 두께를 specific 값으로 override 가능하게 하려면?"**

### Step 1 — Feature spec parsing

LLM prompt (system): "한국어 query 를 semantic units 로 분해. JSON schema: {entities[], attributes[], verbs[], predicates[]}."

```json
{"entities":["고객사 (customer)","슬랩 (slab)"],
 "attributes":["슬랩 두께 (slab_thickness)"],
 "verbs":["override"],
 "predicates":["specific 값 (override 우선순위)"],
 "scope_hint":"feature_addition"}
```

사람이 보는 artifact: JSON + "이 해석으로 진행할까요?" confirm.

### Step 2 — Ontology query (결정론적 tool)

- `find_term("고객사")` → `term.scm.customer`
- `find_term("슬랩 두께")` → `term.scm.slab.slab_thickness`
- `find_action_by_term(slab_thickness, verb=set)` → `action.scm.thickness_실행`
- `find_anchors_of_action(action.scm.thickness_실행)` → 5 anchor (L43,47,52,57,70)
- `schema_columns_for("CUSTOMER_STD")` → 7개 (PKG_WGT_HIGH/LOW 만 numeric)

### Step 3 — Gap identification (결정론적)

| 요구 | 현재 | gap |
|---|---|---|
| customer 가 thickness override 보유 | CUSTOMER_STD 에 thickness column 없음 | **column 부재** |
| thickness 결정 시 override check | SdThicknessAction L52-65 가 CAST_SPEC 만 lookup | **action 분기 부재** |
| Ontology 에 override term | term.scm.customer 에 override facet 없음 | **term 부재** |

### Step 4 — Proposal Composer

**4a. Schema (option α — column 추가, lower blast radius):**
```sql
ALTER TABLE CUSTOMER_STD
  ADD COLUMN OVERRIDE_SLAB_THICKNESS NUMERIC(10,3) NULL;
-- CustomerStdJpo.java:38 앞에
-- @Column(name="OVERRIDE_SLAB_THICKNESS", precision=10, scale=3)
-- private BigDecimal overrideSlabThickness;
```
rationale: PKG_WGT_HIGH/LOW 와 동일 패턴, NULL 허용으로 backward compatible.

**Option β — 새 table** (요약, product 별/priority 별 override 필요시):
```sql
CREATE TABLE CUSTOMER_SLAB_OVERRIDE (
  CMP_CD VARCHAR(2), ORG_CD VARCHAR(1), CUSTOMER_CD VARCHAR(10),
  PRODUCT_CD VARCHAR(3), PRIORITY INTEGER,
  OVERRIDE_SLAB_THICKNESS NUMERIC(10,3) NOT NULL,
  PRIMARY KEY (CMP_CD,ORG_CD,CUSTOMER_CD,PRIORITY));
```

**4b. Code Recommender (α 채택):** SdThicknessAction.java L50 다음에 새 block 삽입:
```java
// 신규 anchor: atomic.customer_override_check  (line ≈ 51)
CustomerStdEntity customer = customerStdService.findByCustomer(
    order.getCmpCd(), order.getOrgCd(), order.getCustomerCd());
if (customer != null && customer.getOverrideSlabThickness() != null) {
    slab.setSlabThickness(customer.getOverrideSlabThickness());
    return;  // CAST_SPEC lookup skip
}
// 기존 L52 시작 (CAST_SPEC fallback) 그대로
```

신규 anchor: `atomic.customer_override_check` (locator: `customer != null && customer.getOverrideSlabThickness() != null`), 그리고 override 분기의 `body.set_output`.

**4c. Ontology delta:**
```json
{
  "new_business_terms":[{
    "fqn":"term.scm.customer.thickness_override","kind":"atomic",
    "parent":"term.scm.customer","name_ko":"고객사 슬랩 두께 override",
    "code_realiz":[{"java_field":"CustomerStdJpo.overrideSlabThickness",
                    "column":"CUSTOMER_STD.OVERRIDE_SLAB_THICKNESS"}]}],
  "new_business_rules":[{
    "fqn":"rule.scm.thickness.customer_override_priority",
    "expr":"customer.override_slab_thickness IS NOT NULL → use that, skip CAST_SPEC",
    "source_action":"action.scm.thickness_실행"}],
  "new_anchor_bindings":[{
    "target_action_fqn":"action.scm.thickness_실행",
    "code_method_fqn":"...SdThicknessAction.execute(...)",
    "line":51,"target_slot":"atomic.customer_override_check",
    "anchor_locator":"customer != null && customer.getOverrideSlabThickness() != null",
    "confidence":0.95,"source":"recommendation"}]
}
```

### Step 5-7 — Validation + User artifact (다음 섹션)

## 6. Validation via Verification Engine

Recommendation 이 propose 끝나면 자동으로 **Verification Engine RPC**:

```python
result = verification_engine.evaluate(
    proposal=proposal,
    fixtures=["S1","S2","S3","S4","S5","S6_new"],
    mode="regression+forward")
# {
#   "regression":{"S1":{"output":"identical","trace_diff":"none"}, ...S5},
#   "forward":{"S6_new":{
#       "input":{"override_slab_thickness":240},
#       "expected_output":{"slab_thickness":240},
#       "actual_output":{"slab_thickness":240}, "passed":true,
#       "trace_diff_vs_S1":[
#         {"new_anchor":"atomic.customer_override_check","fired":true},
#         {"skipped_anchor":"body.service_lookup@L57",
#          "reason":"override branch"}]}}
# }
```

내부: (1) ontology 임시 branch 에 delta 반영 → (2) Synthesizer schema-aware twin 재합성 → (3) Twin Runner S1-S6 실행 → (4) Trace Diff Analyzer 가 S1-S5 unchanged (regression ✓) + S6 forward ✓ 확인.

이 oracle 없으면 LLM 추천은 "코드 같은 글" 일 뿐. Verification call 가 *제안의 falsifiability* 를 보장 — 사용자가 보는 화면에 "regression 0, forward S6 PASS" 같은 verifiable claim 첨부.

## 7. User interaction loop

```
turn 1 (사용자): "고객사가 슬랩 두께를 specific 값으로 override 가능하게 하려면?"
turn 2 (engine): step 1 결과 + clarify "이 override 는 (a) customer 1개당 1값,
                  (b) product 별로 다른 값, (c) date range 의 임시 override?"
turn 3 (사용자): "(a). product 무관."
turn 4 (engine): step 2-7 full proposal (3-tab artifact + verification result
                  S1-S5 ✓ + S6 PASS)
turn 5 (사용자): "customerStdService.findByCustomer signature 가 (cmp,org,customer)
                  만이면 부족하지 않아?"
turn 6 (engine): refine — Spring Data derived name
                  `findByCmpCdAndOrgCdAndCustomerCd` 생성. proposal 재발행.
turn 7 (사용자): "OK. finalize."
turn 8 (engine): PR draft + ontology delta export + modeling UI deep-link.
```

평균 3-7 turn. Escalation: clarify ≥ 3 → structured form 강제. regression FAIL → "기존 행동 변화 발생, 의도?" surface. verification PASS 인데 사용자 reject → 대안 (β) 또는 expansion 모드 재시도.

## 8. Output structure

산출물은 항상 *structured artifact bundle* — Markdown 자연어만이 아닌 머신 처리 가능 형태:

```
proposal-{id}/
├── manifest.yaml          # timestamp, model_version, prompt_hash, seed, ontology_revision
├── schema-diff.sql        # DDL only
├── schema-diff-rationale.md
├── code-diff.patch        # unified diff (Java)
├── ontology-delta.json    # BusinessTerm + Rule + Anchor delta
├── verification-result.json
├── fixture-S6.json        # 신규 fixture
└── README.md              # 사람용 3-tab artifact source
```

Manifest 가 reproducibility 의 fence — 같은 prompt_hash + 같은 ontology_revision + 같은 model_version 이면 같은 proposal id (캐싱 가능).

## 9. Failure modes

| 모드 | 검출 | 대응 |
|---|---|---|
| Spec ambiguous | step 1 clarify ≥ 3 | structured form 강제 |
| Term not found | step 2 결과 0 | "term 신설 모드" → Ontology Evolver 단독 |
| Schema FK violation | step 5 static check | 재시도, FK 제약 반영 |
| 변경이 abstract action 영향 | step 5 의 signature_locked check | 21 concrete realization 점검 |
| Verification regression | step 5 RPC 결과 S1-S5 변경 | surface "행동 변화 발생, 의도?" |
| LLM hallucinated FQN | step 4 끝 FQN unique 검증 | feedback regenerate (max 3) |
| Out-of-scope architecture | step 5 합성 자체 실패 | "X 도 변경 필요" 명시 |
| Partial proposal | step 4 sub-engine success flag | 일부 발행 + manual TODO |
| Context overflow | step 2 retrieval count > N | top-N + 사용자에 추가 filter 요청 |

가장 위험: **silent hallucination** — 그럴듯한 schema 가 verification 도 우연히 PASS. 방어: (1) 새 FQN 의 *namespace pattern* 검증, (2) forward fixture 의 expected output 을 *사용자가 직접* 작성하도록 강제 — LLM 자기 채점 차단.

## 10. LLM non-determinism handling

| 기법 | 적용 |
|---|---|
| Temperature | reasoning 0.2, schema pattern selection 0.0 |
| Seed pinning | manifest 에 seed + model_version + prompt_hash 기록 |
| Prompt versioning | `prompts/recommend_schema_v{N}.md` change log |
| Structured output | Pydantic 강제, 위반 시 reject + retry (max 3) |
| Retrieval cache | (ontology_revision, query_hash) key — 동일 ontology + 동일 query = 동일 context |
| A/B mode | 동일 query 2회 (different seed), diff 크면 "review" surface |
| Golden corpus | 자주 묻는 100 spec 의 expected proposal fixture — prompt 변경 시 regression test |
| Verification 결과 attach | 어떤 결과든 RPC 가 oracle. LLM 자기주장은 verification 통과 후만 노출 |

**100% reproducibility 는 불가능** — LLM 자체가 mutable. 따라서 *동일 환경 reproducibility* 만 claim. R3 비유로는 "BigDecimal string equality" 처럼 reproducibility 의 의미 좁힘 — manifest 가 환경 fingerprint.

## 11. Honest weaknesses

1. **LLM hallucination 잔존** — verification fence 가 강력해도 fixture coverage 불완전 영역 (예: validation-only action) 에서 잘못된 logic 도 통과 가능. 100K 문서 가정 시 fixture 작성 자체가 부담.
2. **Schema-aware 합성 pipeline fragility** — schema → JPO → modeling agent → ontology 재추출 → twin 재합성 link 부서지면 verification stale.
3. **한국어 자연어 의존도** — spec 모호 시 매 turn confirm. Bulk recommendation 병목.
4. **Anchor line drift** — proposal line 은 제안 시점 AST 기준. 동시 수정 시 drift. anchor_locator hash fence 있지만 manual reconcile 필요.
5. **SQL dialect 의존** — v2 JPA + H2 가정. Postgres/Oracle 추가 작업.
6. **Multi-proposal cost** — α/β/γ 3 alternative = 합성 3 회. 캐싱 필수.
7. **권한 경계** — 자동 commit 금지 / modeling UI 경유 wall 유지 — mechanism 비용.
8. **새 feature vs 기존 누락 보강 구분 불가** — LLM 분간 어려움, 사용자 confirm 위임.
9. **RPC cost** — 6 fixture × 36 action = 수 초. 매 turn 대기 UX 저하. 부분 verification 우회 가능하나 mechanism 추가.

이 9가지를 honest 하게 인정한 상태에서도 — *결정론적 mechanism (Verification) + 비결정론적 reasoning (Recommendation) 의 명확한 분리* 가 핵심 가치다. LLM 이 잘못 추천해도 verification fence 가 silent failure 차단, verification 이 모자라도 LLM 이 가설 제안. 두 engine sandwich 가 100K 문서 규모 schema evolution 에서 유의미한 첫 mechanism 이다.
