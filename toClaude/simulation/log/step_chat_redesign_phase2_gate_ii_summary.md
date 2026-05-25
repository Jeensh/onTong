# Phase 2 Gate II — Java + Python + Schema + Fixtures Bundle (Summary)

**브랜치**: `section3/chat-agent-redesign`
**일자**: 2026-05-17
**완료 step**: 3a (tests) / 3b (gate_ii.py) / 3c (/respond turn 3 wire) / 3d (verification)

---

## 1. Step 3a/3b — Gate II handler

신규 `backend/section3/agents/multiturn/gate_ii.py`:

```python
async def build_gate_ii(
    *, target: ActionRef, repo_id: str,
    ontology_client: OntologyClient, max_combinations: int = 12,
) -> GateBundle:
    body = await ontology.get_method_body(target.code_method_fqn)
    if body: (python_source, function_name) = await sim_v2.translate(body)
    entity_name = _extract_entity_name(target.code_method_fqn)
    schema = await ontology.get_entity_schema(entity_name)
    if python_source:
        action = await asyncio.to_thread(sim_v2.load_action, target.action_id)
        if action: fixtures = await sim_v2.synthesize_fixtures(action, ...)
    confidence = weighted_avg(body, translated, schema, fixtures)
    return GateBundle(target, java_source, python_source, idiom_diffs=[],
                       fixtures, schema_summary, sources, confidence)
```

- 4 단계 sequential (이전 결과 의존): body → translate → schema → fixtures
- 각 단계 실패 시 해당 surface 빈 값 + confidence ↓ ("빠진 내용은 빠진대로" Q5)
- `_extract_entity_name` — 정규식 `\(\s*([A-Za-z_][A-Za-z0-9_]*)` 으로 첫 파라미터 타입
- `_load_action_async` — sync `sim_v2_bridge.load_action` 를 `asyncio.to_thread` 로 wrap
- `_bundle_confidence` — 4 flag (body/translate/schema/fixtures) 의 가중합 (0.35/0.30/0.15/0.20)
- `idiom_diffs` — 현재 [] (W75 가 자동 적용하지만 diff surface 없음, 후속 hook 필요)

test: `tests/simulation/test_multiturn_gate_ii.py` — **7 PASS**
- happy path full bundle
- 4-source Provenance 수집
- body 누락 → empty + low confidence
- translate 실패 → java OK, python=""
- entity_schema 누락 → empty SchemaSummary
- entity 추출 정확성
- model_dump kind discriminator

---

## 2. Step 3c — POST /respond turn 3 wire

`multiturn_router.py /respond`:

```python
if next_turn == 3:
    intent = gate_i_decision.payload["intent"]
    if intent == "ambiguous":  raise 422 ("재분류 필요")
    if intent == "impact":     raise 501 ("Gate III impact 미구현")
    # intent == "simulate"
    target_ref = await _resolve_gate_ii_target(...)
    bundle = await build_gate_ii(target_ref, ...)
    save turn_no=3 decision_log
```

State machine (spec v2 §2):
- `simulate` → bundle_prepared → executed (sim)
- `impact` → executed (impact) ← Gate II skip

`_resolve_gate_ii_target` 가드:
- turn 2 가 `target_selected` 여야
- `user_response.action == "confirm"` 여야 (아니면 422)
- `selected_index` 가 int + candidates 범위 안 (아니면 422)
- `ontology.get_action_detail(action_id)` 로 location 보강, 없으면 empty CodeLocation

---

## 3. SimV2BackedOntologyClient — production default

신규 클래스 in `ontology_client.py`:

`sim_v2_bridge` 의 sync 함수를 `asyncio.to_thread` 로 래핑한 production data source:
- `get_method_body` → `sim_v2_bridge.load_body_text` (ontology.db code_methods)
- `get_action_detail` → `sim_v2_bridge.load_action` (있으면 ActionRef 변환)
- search/entity_schema/caller_graph → 빈 결과 (Phase 4 에서 Section 2 API wire)

`get_ontology_client()` default 가 이걸 반환. test 는 `app.dependency_overrides[get_ontology_client] = lambda: MockOntologyClient(catalog=...)` 으로 swap.

---

## 4. Step 3d — Verification

### 4.1 자동 검증 (tests/simulation)

| 파일 | tests |
|---|---|
| test_multiturn_schemas | 15 PASS |
| test_multiturn_persistence | 13 PASS |
| test_multiturn_ontology_client | 11 PASS |
| test_multiturn_tools | 5 PASS |
| test_multiturn_router | **20 PASS** (15 → 20) |
| test_multiturn_intent | 10 PASS |
| test_multiturn_gate_i | 11 PASS |
| **test_multiturn_gate_ii** | **7 PASS (신규)** |
| test_sim_v2_bridge | 13 PASS |

**전체: 105 PASS** (93 → 105, +12 = 7 Gate II + 5 router 추가)

### 4.2 서버 검증 (port 8001, 실 OpenAI + 실 sim_v2)

**풀 플로우 (simulate)**:
```
POST /start "주문 검증 시뮬해줘"   → turn 1 (ambiguous stub)
POST /respond                       → turn 2 intent=simulate, top=정합성_검증
POST /confirm/{sid}/2  selected_index=0
POST /respond "이 bundle 로 진행"  → turn 3 GateBundle:
  - target.code_method_fqn = com.example.slabdesign...SdOrderValidator.validate(SDOrderEntity)
  - java_source: 431 chars (실 Java body, ValidationResult, checkStockOrder 등)
  - python_source: 400 chars (W75 idiom 변환)
  - schema entity: "" / fields: 0 (Q5 "빠진 대로" — sec2 API 부재)
  - fixtures: 1 (action.scm.order.정합성_검증#0)
  - confidence: 0.85
  - sources: ['ontology', 'sim_v2', 'ontology', 'sim_v2'] — 4 Provenance
```

**Edge cases**:
- impact intent → turn 3 = 501 ("Gate III impact 미구현") ✓
- turn 3 without confirm → 422 ("turn 2 가 confirm 되지 않음") ✓
- selected_index 범위 밖 → 422 ✓
- turn 4 → 501 ✓

---

## 5. 다음 Phase 2 항목

| # | Item | Status |
|---|---|---|
| Gate I (intent + candidates) | ✅ |
| Gate II (java + python + fixtures bundle) | ✅ |
| Gate III sim (run_fixtures + invariant) | 다음 |
| Gate III impact (caller_graph + diagnose) | 다음 |
| `confirm.next_gate_kind` 계산 | TBD |
| Frontend MultiturnChat + GateCard + ProvenanceBadge | TBD |

Gate III 진입 시 starting point:
- `/respond` 의 next_turn==4 분기 추가 (sim) / next_turn==3 impact 분기 wire
- sim 경로: `call_sim_v2_run_fixtures(fixtures, function_name, python_source)` + `call_sim_v2_quick_diagnose` → `GateExecutedSimulation`
- impact 경로: `call_ontology_get_caller_graph(target.code_method_fqn)` + `quick_diagnose` → `GateExecutedImpact`
- W74 typed-return stub 통합 필요 시 sim_v2 협업 요청

---

## 6. 부수 산물

- `MockOntologyClient._match_score` — Gate I 작업 중 토큰 단위 매칭으로 개선
- `idiom_diffs` field — 현재 빈 리스트. Section3Translator 결과에서 idiom 변환 mapping 추출 hook 필요 (TODO).
