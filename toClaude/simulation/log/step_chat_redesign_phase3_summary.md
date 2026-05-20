# Phase 3 — Frontend MultiturnChat (Summary)

**브랜치**: `section3/chat-agent-redesign`
**일자**: 2026-05-17
**완료 step**: P3a (API client) / P3b (hook) / P3c (4 GateCard + ProvenanceBadge) / P3d (MultiturnChat) / P3e (nav) / P3f (verification)

Phase 2 production wiring 위에 한국어 UI 얹음. 사용자는 자연어 입력 → 단계별 카드 (대상 → 번들 → 실행 / 영향도) 를 보며 진행.

---

## 1. P3a — API client

`frontend/src/lib/section3/multiturn.ts`:

- TS types 백엔드 schemas.py 와 1:1 — `Provenance / GateTarget / GateBundle / GateExecutedSimulation / GateExecutedImpact` 등
- 4 함수:
  - `startSession(user_query, repo_id)` → POST /start
  - `respond(sid, message)` → POST /respond/{sid}
  - `confirmTurn(sid, turn_no, action, user_response)` → POST /confirm/{sid}/{turn_no}
  - `getSession(sid)` → GET /session/{sid}
- `MultiturnError(status, detail)` — `fetch` 실패 시 throw, UI 가 status/detail 분기

Next.js dev `rewrites()` 가 `/api/*` → `http://localhost:8001/api/*` 라 base path = `/api/section3/multiturn` 만 사용 (BACKEND_DIRECT 안 씀 — SSE 는 Phase 3 에서 안 쓰므로 proxy OK).

---

## 2. P3b — useMultiturnSession hook

`frontend/src/components/section3/multiturn/useMultiturnSession.ts`:

- state: `{ sessionId, session, decisions, pending, error }`
- actions: `start(query, repo_id)` / `respond(message)` / `confirm(turn_no, action, user_response)` / `reset()`
- 모든 mutation 후 `apiGetSession(sid)` 으로 refresh — source-of-truth replay (spec v2 §5). 백엔드 결과가 ground truth, 클라이언트 cache 없음

---

## 3. P3c — 4 GateCard + ProvenanceBadge

5 컴포넌트 (`frontend/src/components/section3/multiturn/`):

### ProvenanceBadge.tsx
- 4 source 별 색상 칩 (ontology=blue / sim_v2=purple / llm_inference=amber / user_input=gray)
- icon + label + confidence (%) + tooltip(detail)
- `ProvenanceRow` 로 모든 카드 footer 에 통일

### GateTargetCard.tsx (Gate I)
- intent 배지 (시뮬레이션 / 영향도 검토 / 모호)
- 후보 리스트 — radio + "추천" 라벨 + score + code_method_fqn
- [이걸로 진행] (default = recommended_index) / [다른 후보 검색]
- ambiguous intent / empty candidates 시 confirm disabled

### GateBundleCard.tsx (Gate II)
- confidence % (color-coded green/amber/red)
- 4-tab: Python (default) / Java / Fixtures / Schema
- pre 코드 블록 (max-h-72 scrollable) · fixtures 표 · schema 표
- [실행 (Gate III)] — python_source 없으면 disabled
- empty (entity_schema 부재) → "Section 2 API 미연결 (Phase 4 swap 후 surface). Q5: 빠진 내용은 빠진대로"

### GateExecutedSimulationCard.tsx (Gate III sim)
- invariant_status 배지 (clean / fail_* / error)
- PASS / FAIL / ERROR / SKIPPED count
- case 표 (fixture_id / status / output / error)
- 세션 완료 표시

### GateExecutedImpactCard.tsx (Gate III impact)
- confidence 막대 그래프
- affected_methods 표 (fqn / distance / via)
- findings 리스트 (severity 색상)
- caller_graph 비어있으면 "Section 2 API 미연결" surface

---

## 4. P3d — MultiturnChat 컨테이너

`MultiturnChat.tsx`:

- 빈 상태: repo_id 입력 + 4 예시 질문 grid
- session 시작 시: header (session id / repo / status) + 카드 누적 렌더
- **자동 진행 로직**:
  - turn 1 (ambiguous stub) 도착 → 카드 surface 안 함, 자동 `respond(user_query)` → turn 2 (Gate I real)
  - turn 2 의 [이걸로 진행] → `confirm(2, "confirm", {selected_index})` + `respond("이걸로 진행")` 연쇄
  - turn 3 GateBundle [실행] → `respond("실행")` → turn 4 (Gate III sim)
  - turn 3 GateExecutedImpact → 세션 종료, 추가 액션 없음
- pending pulse (Loader2 spinner + 한국어 안내)
- error banner (HTTP status + detail)

---

## 5. P3e — Section3Section nav

`Section3Section.tsx`:

- 기존 nav 5개 → 6개 (`멀티턴 (v2)` 추가, dashboard 다음에 배치)
- icon = Sparkles
- URL `?view=multiturn` 라우팅
- View union 갱신 + VALID 배열 갱신

---

## 6. P3f — Verification

### 6.1 TypeScript

- 신규 multiturn 파일 6개 (api client + hook + 5 컴포넌트) 모두 TS clean
- 기존 EventStreamView.tsx 에 pre-existing TS 에러 있으나 Phase 3 작업과 무관

### 6.2 Backend ↔ Frontend 연동

`/api/section3/multiturn/*` Next.js `rewrites()` proxy → `http://localhost:8001/api/section3/multiturn/*` 정상.

풀 플로우 via proxy (port 3000):
```
POST /start "주문 검증 시뮬해줘"   → turn 1 ambiguous stub
POST /respond                       → turn 2 intent=simulate · 5 candidates
POST /confirm/{sid}/2 selected=0    → ok=true
POST /respond                       → turn 3 bundle_prepared
```

`port 3000` (사용자 기존 dev) + `port 8001` (backend) 모두 동작.

### 6.3 사용자 클릭 검증 (잔여)

UI 의 실제 클릭/렌더는 사용자가 브라우저에서 직접 검증. 진입점:

```
http://localhost:3000/?view=multiturn
```

자동 시나리오:
1. "주문 검증 시뮬해줘" 입력 → [시작]
2. 자동으로 turn 2 카드 surface (5 candidates, 추천 = 정합성_검증)
3. [이걸로 진행] → turn 3 GateBundle (java / python / fixtures / schema 4-tab)
4. [실행] → turn 4 GateExecutedSimulationCard (case 표 + invariant)

또는 `"cumulativeProductivity 바꾸면 영향?"` → turn 3 GateExecutedImpactCard 종료.

---

## 7. 다음 (Phase 4)

| # | Item | Status |
|---|---|---|
| Phase 2 backend (Gate I+II+III) | ✅ |
| Phase 3 frontend (MultiturnChat) | ✅ |
| Phase 4 — Section 2 API swap | TBD |
| ontology.db 시드 (caller_graph / entity_schemas) | TBD |
| 옛 bridge_agent.py deprecate | TBD |
| (TBD) `idiom_diffs` surface | TBD |
| (TBD) SSE 실시간 스트리밍 (`/session/{sid}/stream` 풀 활용) | TBD |

Phase 3 의 UI 는 polling-based (`getSession` 매번 호출). Phase 4 에서 SSE 구독으로 전환 가능 — turn 진입 시 자동 update + 백엔드 의 LLM/tool 호출 진행 상태 surface.
