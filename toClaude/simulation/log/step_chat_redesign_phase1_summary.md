# Step Chat-Redesign Phase 1 — Summary (2026-05-17)

> Section 3 chat 의 단발 → 3 게이트 멀티턴 agent 재설계 인프라.
> CHAT_REDESIGN_SPEC.md v2 의 Phase 1 (인프라 + Scaffold) 1a~1f 완료.

브랜치: `section3/chat-agent-redesign`

---

## 무엇을 했나 — Phase 1 Step 1a~1f

| Step | 결과물 | 검증 |
| --- | --- | --- |
| **1a** spec v2 + HANDOFF | `CHAT_REDESIGN_SPEC.md` v2 (411 LOC) · `HANDOFF.md` 갱신. 6→3 gates, §6 폐기, alembic 없이, Q5 비전 §13 신설 | 사용자 4 sub-agent 검토 페이지로 결정 |
| **1b** scaffold + schemas | `backend/section3/agents/multiturn/{__init__.py, schemas.py}` (~190 LOC) — GatePayload union (4 leaf, kind discriminator) + Provenance + sub-models | `test_multiturn_schemas.py` 15/15 |
| **1c** ORM + persistence | `orm.py` (Section3SessionRow + Section3DecisionLogRow) · `persistence.py` (lifecycle + decision + replay-hydrate) · `main.py` startup import | `test_multiturn_persistence.py` 13/13 |
| **1d** OntologyClient + tools | `ontology_client.py` (Protocol + Mock + HTTP stub) · `tools.py` (9 tool wrapper + ToolResult + ALLOWED_PER_GATE) | `test_multiturn_ontology_client.py` 11/11 · `test_multiturn_tools.py` 5/5 |
| **1e** Endpoints | `backend/section3/api/multiturn_router.py` (5 endpoint) · `main.py` include | `test_multiturn_router.py` 10/10 |
| **1f** integration verification | 백엔드 startup + curl 4 endpoint + edge cases + SSE | 67/67 회귀 |

---

## 4 sub-agent 결과 반영 (사용자 검토)

| 영역 | v1 → v2 |
| --- | --- |
| Gate 수 | 6 → 3 (Gate I 후보+선택 / II 코드+Python+fixtures bundle / III 실행+진단) |
| §6 Pending action | `core/session.py:add_pending_action` 폐기 (wiki 패턴 오인) → authoring DB-only direct confirm |
| decision_log | alembic 없이 `Base.metadata.create_all()` (authoring 의 실제 패턴) |
| LLM client | OpenAI 유지 |
| async 경계 | sim_v2 sync 함수는 `asyncio.to_thread` 명시 |
| repo_id | 세션 state |
| replay | source-of-truth hydrate (sim_v2 재호출 X) |
| **Q5 비전** | §13 신설 — 영향도 검토 + 시뮬레이션 두 흐름 · Section 2 API 통신 · 모든 카드에 **Provenance** surface |

---

## 핵심 자산

### 1. 패키지 구조
```
backend/section3/agents/multiturn/
├── __init__.py
├── schemas.py          # GatePayload union + Provenance + sub-models
├── orm.py              # Section3SessionRow + Section3DecisionLogRow
├── persistence.py      # lifecycle + decision_log + replay (hydrate)
├── ontology_client.py  # OntologyClient Protocol + Mock + HTTP stub
└── tools.py            # 9 tool wrapper + ToolResult + ALLOWED_PER_GATE
```

### 2. Endpoint (prefix `/api/section3/multiturn`)
- `POST /start` — session 생성 + Gate I (Phase 1 stub: intent="ambiguous")
- `POST /respond/{session_id}` — **501** Phase 2 (LLM gate progression)
- `POST /confirm/{session_id}/{turn_no}` — 카드 버튼 응답
- `GET /session/{session_id}` — replay (hydrate)
- `GET /session/{session_id}/stream` — SSE snapshot (Phase 1 minimal)

### 3. 4 Gate Payload (discriminator: `kind`)
- `GateTarget` — Gate I (intent: simulate/impact/ambiguous + candidates + selected + sources)
- `GateBundle` — Gate II (java + python + idiom_diffs + fixtures + schema_summary)
- `GateExecutedSimulation` — Gate III sim (results + invariant_status + baseline_diff)
- `GateExecutedImpact` — Gate III impact (affected_methods + sim_v2_findings)

### 4. 9 Tool (4 sim_v2 + 5 ontology, gate 별 allowlist)
| Gate | 허용 tool |
| --- | --- |
| `target_selected` | search_action_by_keyword · get_action_detail · sim_v2.find_action_candidates |
| `bundle_prepared` | get_method_body · get_entity_schema · sim_v2.translate_java_to_python · sim_v2.synthesize_fixtures |
| `executed_simulation` | sim_v2.run_fixtures_in_process · sim_v2.quick_diagnose_action |
| `executed_impact` | get_caller_graph · sim_v2.quick_diagnose_action |

---

## 검증 (Pre-Demo Verification Protocol)

### 단위 회귀
- `tests/simulation/` — **67/67 passed** (schemas 15 + persistence 13 + ontology_client 11 + tools 5 + router 10 + sim_v2_bridge 13)

### 통합 verification (curl, port 8001)
| 시나리오 | 결과 |
| --- | --- |
| `POST /start` with 한국어 user_query | 200, session_id 발급, payload 한국어 unicode-escape JSON 보존 |
| `POST /confirm/{sid}/1` | 200, `{ok:true, next_gate_kind:null}` |
| `GET /session/{sid}` (replay) | 200, decisions[0].user_response 에 confirm 액션 + 한국어 comment 보존 |
| `GET /session/{sid}/stream` | SSE `event: snapshot` 1회 emit |
| `POST /respond/{sid}` (Phase 1 stub) | 501 |
| `GET /session/unknown` | 404 |
| `POST /confirm/{sid}/999` (unknown turn) | 404 |
| `POST /start` (missing repo_id) | 422 |

### Q5 비전 ("확실한 근거")
- Gate I stub 의 `sources[0]` = `{source:"user_input", detail:"start_session(user_query='엣징...')", confidence:null}` — 카드에 출처 표시 가능

---

## Phase 1 미구현 (Phase 2 작업)

- `POST /respond` 의 실제 gate logic (LLM intent 분류 + tool 호출 + 다음 gate 전환)
- Gate I 의 candidates 진짜 채움 (`sim_v2.find_action_candidates` + `ontology.search_action_by_keyword`)
- Gate II 의 bundle 진짜 합성 (Java 추출 + W75 translate + W71 fixtures + entity_schema)
- Gate III 두 분기 (sim / impact) 의 실제 실행
- `confirm.next_gate_kind` 계산 (state machine)
- Frontend `MultiturnChat.tsx` + `GateXxxCard.tsx` + `ProvenanceBadge.tsx`
- `HTTPOntologyClient` 실 wire (Section 2 API 준비 시 swap)

---

## 다음 step

Phase 2 진입. Gate 단위 production wiring (Section 2 협업 #2: OntologyClient 5 endpoint 가 mock 으로도 Phase 2 전체 완주 가능).
세부: `HANDOFF.md` 의 "🔴 다음 세션 첫 작업" + `CHAT_REDESIGN_SPEC.md` §10 Phase 2.
