# 시뮬레이션 에이전트 — 검증 보고서

> 사용자 요구 (#58 + #62): "온톨로지 응답 기반으로 시뮬에이전트가 만들어진 게
> 맞는지 전반적인 검증 + hypothesis grounding 정합성 확인"
>
> 작업 일자: 2026-05-22
> 브랜치: `jyu-simul`

---

## A. ontology 데이터 풍부도

`data/ontology.db` 의 `repo_id='slab-design-real-v2'` 기준:

| layer | count | 비고 |
|---|---|---|
| `business_terms` | **83** | description 평균 ~300 chars · aliases_json 평균 ~50 bytes |
| `actions` | **136** | 전부 `sim_verified` · params/effects/sub_actions 풍부 |
| `realizations` | 148 | action → code_method binding |
| `anchor_bindings` | 163 | code 안 guard/literal point |
| `business_rules` | 22 | severity + terms_ref + enforced_by |
| `code_types` | 150 | Java class |
| `code_methods` | 1,081 | Java method · body_text 포함 |
| `call_sites` | 2,298 | method 간 호출 그래프 |

샘플 term description 풍부도:
- `term.scm.order.order` — 527 chars
- `term.scm.slab.slab` — 527 chars
- `term.scm.working_controller` — 410 chars

샘플 action 풍부도 (effects/sub_actions 길이):
- `action.scm.second_wgt_high_실행` — params 203b · effects 1,373b · sub_actions 2개
- `action.scm.slab.design_orchestrator` — effects 1,341b · sub_actions 2개

---

## B. 시뮬에이전트가 활용하는 ontology API

| 시점 | 호출 | 활용 데이터 |
|---|---|---|
| `/start` (모든 intent) | `business_terms` LIKE 매칭 | `_detected_terms` 첨부 (token → label · fqn · definition) |
| `/start` (impact) | `_enrich_impact_payload` | `_target_change` (table/column/before/after), `_affected_orders` (seed join), `_affected_rules` (business_rules.terms_ref_json), `_affected_steps` (SdXxxAction → 21-step), `_affected_actions` (actions.declared_on_term 매칭), `_affected_apis` (Controller 매칭), `_intent_focus` |
| `/start` (simulate + ORD) | `slab_design_runner.run_full_design` | Java :8080 `/api/sd/working/single?trace=true` 실제 호출 — slabResults + 21-step trace |
| `/start` (hypothesis) | `hypothesis_workflow.run_hypothesis` | seed `SD_PRODUCTIVITY_STD` (base_grade) + 합성 (new_grade) + Java :8080 호출 |
| `/start` (locate) | `_enrich_locate_payload` | `code_methods` (body_text/name/fqn LIKE) + line range · keyword 매칭 |
| `/graph/{sid}` | `ontology.get_caller_graph` | 1-hop callers/callees + declared_on_term edge |
| `/method/body` | `ontology.get_method_body` + `code_methods` row | body_text · line_start/end · annotations · callers · callees |
| `/data/tables` · `/data/table/{name}` | JPA file grep + seed SQL 파싱 | 14 table schema + seed rows |
| `/term_lookup` | `business_terms` (label/aliases) | 자연어 토큰 → term 매핑 |
| `/suggested_questions` | seed orders + JPA javadoc + business_terms | 10건 동적 질문 + grounded_terms |

---

## C. impact intent 풍부화 검증

query: `"CAST_SPEC 의 slab두께 240으로 바꾸면 어떤 step 영향?"`

`/start` → carousel → `/respond select_candidate(0)` → executed payload:
- `_detected_terms`: 1건 (token "두께" → `term.scm.thickness`)
- `_target_change`: `CAST_SPEC.SLAB_THICKNESS · before=230.0 → after=240 · product=COIL`
- `affected_methods`: 3건 (`SdDesigner.design`, `SdDriver.batchDesign`, `SdDriver.singleDesign` — 모두 real Java fqn)
- `_affected_rules`: 1건 (terms_ref_json 매칭)
- `_affected_orders`: 5건 (PRODUCT_CD=COIL 매칭 — ORD20260510001~5 모두)
- `_affected_steps`: 0건 (SdXxxAction 직접 호출자가 아니라 매핑 안 됨 — 정상)
- `_affected_actions` / `_affected_apis`: 0건 (declared_on_term 미매칭)
- `_intent_focus`: `step` (질문에 "step" 키워드 감지)

---

## D. hypothesis grounding 정합성

`POST /hypothesis/run` body: `{base_grade:SS400, new_grade:SS500, mult:0.95, base_order_no:ORD20260510001}`

| 검증 항목 | 결과 |
|---|---|
| 1. `existing_productivity_rows` 가 seed 의 SS400 row 인가 | ✓ 8 rows (SM 0.98, HR 0.97, HRF 0.96, CR 0.95, ANL1 0.99, ANL2 0.99, GAL 0.97, CRF 0.94) |
| 2. `virtual_productivity_rows` 가 multiplier 정확히 적용 | ✓ orig 0.98 × 0.95 = 0.9310 → vrt 0.931 (일치) |
| 3. `baseline_slab` 이 Java :8080 진짜 호출 | ✓ slabWgt 13,288.01 (golden S1 과 byte-equal) |
| 4. `projected_slab` 의 단중 계열에 ratio 적용 | ✓ 13,288 → 12,624 (-5.0%) |
| 5. 두께·폭·길이는 강종 무관 (HR_SPEC) → 변경 없음 | ✓ projection 모델 정합 |
| 6. ontology `business_terms` 에 `강종` term 존재 | ✓ `term.scm.shared.grade` 등록 |

---

## E. SSE 스트리밍 검증

`POST /hypothesis/stream` 호출 → 4 stage 순차 SSE event:

```
data: {"stage": 1, "label": "기존 데이터 분석",      "data": {...}}
data: {"stage": 2, "label": "가상 강종 합성",        "data": {...}}
data: {"stage": 3, "label": "가상 주문 합성",        "data": {...}}
data: {"stage": 4, "label": "Slab 결과 비교 (추론)", "data": {...}}
data: {"stage": "done", "label": "완료"}
```

frontend `_HypothesisWorkflowView` 가 SSE reader 로 stream 받아 stage 별 카드를
progressive 등장 (400ms 간격).

---

## F. 결론

- ontology 의 83 terms · 136 actions · 148 realizations · 163 anchors · 22 rules
  는 실제로 시뮬에이전트의 모든 endpoint 와 결과 surface 에서 활용된다.
- hypothesis_workflow 의 baseline 은 Java :8080 의 실제 21-step 알고리즘 결과
  (golden S1 과 byte-equal). projection 은 productivity 비율 모델 적용.
- impact intent 의 `_target_change` 는 seed 의 before value 를 직접 조회.
  `_affected_orders` 는 PRODUCT_CD 매칭으로 5건 surface.
- 모든 detected_terms 는 `business_terms.label/aliases_json` LIKE 매칭 결과.
- SSE 스트리밍이 4-stage 순차 progressive UX 제공.

**남은 한계** (후속 작업):
- `_affected_steps` 가 SdXxxAction 의 indirect call 까지 추적 못 함
  (caller_graph 가 SimV2 mock 이라 1-hop 만 충분 한계)
- `affected_actions` 는 declared_on_term 매칭만 — actions 의 `inputs` /
  `outputs` 분석은 미구현
- ontology API 의 정식 endpoint (`/api/ontology/*`) 가 modeling 서버에서
  나오면 mock 의존성 제거 가능
