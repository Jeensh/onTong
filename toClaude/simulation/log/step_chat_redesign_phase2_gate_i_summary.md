# Phase 2 Gate I — LLM intent + 후보 채움 (Summary)

**브랜치**: `section3/chat-agent-redesign`
**일자**: 2026-05-17
**완료 step**: 2a (intent classifier) / 2b (Gate I handler) / 2c (/respond wire) / 2d (verification)

---

## 1. Step 2a — Multiturn intent classifier

신규 `backend/section3/agents/multiturn/intent.py`:

- `IntentDecision(intent, confidence, reasoning)` — frozen dataclass + `__post_init__` validation
- `MultiturnIntentClassifier` — `@runtime_checkable` Protocol (test swap)
- `StubIntentClassifier` — `forced_intent` + `per_query` override 지원
- `classify_with_llm(user_query, llm=None)` — OpenAI `chat_json` 호출, unknown intent → ambiguous fallback
- `OpenAIIntentClassifier` — Protocol adapter (router DI)

기존 `backend/section3/llm/intent_classifier.py` 와 분리:
- 기존: 3 intent (impact_analysis / simulate / explain) + parameters
- 신규: 3 intent (simulate / impact / ambiguous) — Gate I 두 분기 + 모호

test: `tests/simulation/test_multiturn_intent.py` 10 PASS

---

## 2. Step 2b — Gate I handler

신규 `backend/section3/agents/multiturn/gate_i.py`:

```python
async def build_gate_i(
    *,
    user_query: str,
    repo_id: str,
    classifier: MultiturnIntentClassifier,
    ontology_client: OntologyClient,
    top_n: int = 5,
) -> GateTarget:
    intent_decision = classifier.classify(user_query)
    onto, sim = await asyncio.gather(
        call_ontology_search(...), call_sim_v2_find_action_candidates(...),
    )
    candidates = _merge_candidates(...)
    sources = [llm_inference, ontology, sim_v2]
    return GateTarget(...)
```

- 병렬: `asyncio.gather` 로 ontology + sim_v2 동시 호출
- dedupe: 같은 `code_method_fqn` → 한 행 + score 합산 (ontology label 우선)
- recommended_index = 0 if candidates else None
- Provenance 3개 자동 첨부 (Q5 비전 — "확실한 근거")

test: `tests/simulation/test_multiturn_gate_i.py` 11 PASS

`MockOntologyClient._match_score` 도 토큰 단위 매칭으로 개선 (query 가 label 보다 길어도 매칭).

---

## 3. Step 2c — POST /respond wire

`backend/section3/api/multiturn_router.py`:

- 기존 501 → Gate progression
- `FastAPI Depends(get_classifier)` / `Depends(get_ontology_client)` 로 DI
  - default: OpenAI + MockOntologyClient(empty)
  - test: `app.dependency_overrides[...]` 로 swap
- 분기:
  - 다음 turn_no == 2 → Gate I real (build_gate_i → add_gate_decision)
  - turn_no >= 3 → 501 (Gate II/III 미구현)
- `req.message` 가 빈 문자열이면 `session.user_query` 로 fallback
- `RespondResponse(session_id, turn_no, payload)` 신규 response model

test 업데이트: `tests/simulation/test_multiturn_router.py`
- `client_factory` fixture 추가 — `forced_intent` / `sim_v2_candidates` / `catalog` 주입
- 기존 `test_respond_phase1_returns_501` → 6개 Phase 2 테스트로 교체
  - simulate / impact / empty message / persistence / 404 / turn 3 → 501

---

## 4. Step 2d — Verification

### 4.1 자동 검증 (tests/simulation)

| 파일 | tests |
|---|---|
| test_multiturn_schemas.py | 15 PASS |
| test_multiturn_persistence.py | 13 PASS |
| test_multiturn_ontology_client.py | 11 PASS |
| test_multiturn_tools.py | 5 PASS |
| test_multiturn_router.py | 15 PASS (10 → 15) |
| **test_multiturn_intent.py** | **10 PASS (신규)** |
| **test_multiturn_gate_i.py** | **11 PASS (신규)** |
| test_sim_v2_bridge.py | 13 PASS |

**전체: 93 PASS** (67 → 93, +26)

### 4.2 서버 검증 (port 8001)

`.env` OPENAI_API_KEY 로딩 → 실 OpenAI 호출.

**Test 1 — simulate intent + 실데이터 후보**:
```
POST /start  {"user_query":"주문 검증 시뮬해줘", "repo_id":"slab-design-real-v2"}
→ turn 1 ambiguous stub

POST /respond/{sid}  {"message":"주문 검증 시뮬해줘"}
→ turn 2: intent=simulate
   candidates (5):
     - 정합성_검증 (SdOrderValidator.validate) — score 10.0
     - slab design — score 9.0
     - final_length_range_실행 — score 9.0
     - final_width_range_실행 — score 9.0
     - first_weight_실행 — score 9.0
   reasoning: "주문 검증을 시뮬레이션해달라는 요청으로, 명확하게 시뮬레이션을 요구하고 있습니다."
   confidence: 0.9
```

**Test 2 — impact intent + cumulativeProductivity**:
```
POST /respond  "cumulativeProductivity 바꾸면 어디가 영향받나?"
→ intent=impact
   candidates (1): cumulativeProductivity action
   reasoning: "영향 분석에 해당합니다"
```

**Edge cases**:
- /respond 으로 unknown session → **404** ✓
- /respond turn 3 (Gate I 후) → **501 "Gate II/III 미구현"** ✓
- SSE snapshot 에 turn 1 + turn 2 모두 emit ✓

---

## 5. 협업 의존성

- **Section 2 API (OntologyClient HTTP)** — 아직 mock 단계. Phase 4 에서 swap.
- **ontology.db 시드** — `data/ontology.db` 의 slab-design-real-v2 38 actions 가 sim_v2.find_action_candidates 의 실데이터 소스. 실 데모 OK.

---

## 6. 다음 Phase 2 항목

| # | Item | Status |
|---|---|---|
| Gate I (intent + candidates) | ✅ 완료 |
| Gate II (java + python + fixtures bundle) | 다음 |
| Gate III sim (run_fixtures + invariant) | TBD |
| Gate III impact (caller_graph + diagnose) | TBD |
| `confirm.next_gate_kind` 계산 | TBD |
| Frontend MultiturnChat + GateCard + ProvenanceBadge | TBD |

Gate II 진입 시 starting point:
- `/respond` 의 next_turn==3 분기 추가
- `call_ontology_get_method_body` + `call_sim_v2_translate` + `call_ontology_get_entity_schema` + `call_sim_v2_synthesize_fixtures` 병렬
- `GateBundle` payload 채움
- target 정보 (turn 2 의 `selected` 또는 사용자 confirm 으로 결정) 필요 → `update_user_response` 와 연계
