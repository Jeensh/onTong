# Section 3 Chat — 멀티턴 Agent 재설계 SPEC

> **목표**: 현재 단발성 stream chat (`backend/section3/agents/bridge_agent.py`) 을
> Section 2 의 Authoring 패턴 (hypothesis → interview → option → confirm) 을 차용한
> **6 게이트 멀티턴 agent** 로 재설계.
>
> **작성일**: 2026-05-17
> **브랜치**: `section3/chat-agent-redesign` (origin/main 기준)
> **차용 원본**: `backend/application/authoring/` (Section 2)

---

## 0. 한 줄 요약

자연어 chat 한 턴 → LLM 이 의도 + 후보 surface → **사용자 승인** → 다음 게이트 →
또 LLM + tool → **사용자 승인** → … 총 6 게이트.

각 게이트는 (a) LLM 이 ontology + sim_v2 tool 을 호출, (b) 결과를 카드로 surface,
(c) 사용자 응답을 받아 다음 게이트 진입 가능 여부 결정.

게이트 결정은 `section3_decision_log` 테이블에 영구 저장 → 세션 끊겨도 replay 로 resume.

---

## 1. 6 게이트 정의

| # | Gate | LLM action | Tool calls | Output payload | 다음 게이트 진입 조건 |
|---|---|---|---|---|---|
| 1 | **candidates_proposed** | 의도 분류 + action 후보 검색 | `sim_v2.find_action_candidates(q)` · `ontology.search` | `{candidates: Candidate[3-5], recommended_index}` | 사용자가 후보 선택 또는 "다른 거" |
| 2 | **target_selected** | 선택 검증 + 코드/메서드 위치 조회 | `ontology.get_action_detail(id)` (mock 가능) | `{action_id, code_method_fqn, location}` | 사용자 "이거 맞아" 확인 |
| 3 | **code_extracted** | Java 핵심부만 추출 | `ontology.get_method_body(fqn)` (mock 가능) · 추가 `get_action_detail` 의 deps | `{java_source, dependencies[], highlighted_anchors}` | 사용자 "시뮬할 부분 맞음" |
| 4 | **python_generated** | sim_v2 W75 Java→Python 변환 | `sim_v2.translate_java_to_python(src)` | `{python_source, idiom_diffs[], confidence}` | 사용자 "이 코드로 돌릴까" |
| 5 | **fixtures_synthesized** | Order 등 entity fixture 합성 | `ontology.get_entity_schema(name)` (mock 가능) · `sim_v2.synthesize_fixtures(...)` | `{fixtures[1-5], schema_summary}` | 사용자 표 수정 또는 승인 |
| 6 | **sandbox_executed** | 실행 + 결과 진단 | `sim_v2.run_fixtures_in_process(...)` · `quick_diagnose_action(...)` | `{results[], invariant_status, baseline_diff}` | 사용자 "OK / 다시 / 다른 케이스" |

각 게이트 진입 시 `add_decision(kind=...)` 호출 → DB 영구화.

---

## 2. State Machine (DecisionKind)

```
candidates_proposed   ── (사용자 선택) ──▶ target_selected
target_selected       ── (사용자 확인) ──▶ code_extracted
code_extracted        ── (사용자 확인) ──▶ python_generated
python_generated      ── (사용자 확인) ──▶ fixtures_synthesized
fixtures_synthesized  ── (사용자 승인) ──▶ sandbox_executed
sandbox_executed      ── (사용자 "다시") ─▶ (어느 단계로 돌아갈지 LLM 판단)
                      ── (사용자 "OK") ───▶ session.status = done
```

추가 종료 분기:
- 사용자 "다른 후보 보여줘" @ Gate 2 → Gate 1 재실행 (이전 candidates 제외)
- 사용자 "이 코드는 아닌데" @ Gate 4 → Gate 3 재실행 (Java 추출 범위 조정)
- 사용자 "이 데이터로는 안 됨" @ Gate 5 → Gate 5 재합성 (제약조건 추가)

---

## 3. Tool Catalog

LLM 에게 노출되는 tool 6개 (Section 2 의 `authoring_full` 패턴과 동일하게 PRESET 정의):

```python
# backend/section3/agents/multiturn/tools.py
TOOLS = {
    "ontology.search_action_by_keyword": OntologySearchTool,         # ★ Section 2 OntologyClient 재사용
    "ontology.get_action_detail":        OntologyActionDetailTool,    # ⚠ 협업 요청 #2 — 미구현 시 mock
    "ontology.get_method_body":          OntologyMethodBodyTool,      # ⚠ 협업 요청 #2 — 미구현 시 mock
    "ontology.get_entity_schema":        OntologyEntitySchemaTool,    # ⚠ 협업 요청 #2 — 미구현 시 mock
    "sim_v2.find_action_candidates":     SimV2CandidatesTool,         # ★ sim_v2_bridge 이미 존재
    "sim_v2.quick_diagnose_action":      SimV2DiagnoseTool,           # ★ sim_v2_bridge 이미 존재
    "sim_v2.translate_java_to_python":   SimV2TranslateTool,          # ★ sim_v2_bridge 이미 존재 (W75)
    "sim_v2.synthesize_fixtures":        SimV2FixturesTool,           # ★ sim_v2_bridge 이미 존재 (W71)
    "sim_v2.run_fixtures_in_process":    SimV2RunTool,                # ★ sim_v2_bridge 이미 존재
}
```

각 게이트의 `allowed` 세트 — 권한 좁히기:
- Gate 1: `[search_action_by_keyword, find_action_candidates]`
- Gate 2: `[get_action_detail]`
- Gate 3: `[get_method_body, get_action_detail]`
- Gate 4: `[translate_java_to_python]`
- Gate 5: `[get_entity_schema, synthesize_fixtures]`
- Gate 6: `[run_fixtures_in_process, quick_diagnose_action]`

Tool 호출은 `RunTracker` + `AuthoringToolLogger` 패턴 (Section 2 의 `option_proposer.py:200-220`) 으로 budget + DB 로깅 + SSE event.

---

## 4. Payload Discriminator Union

```python
# backend/section3/agents/multiturn/schemas.py

class GateCandidates(BaseModel):
    kind: Literal["candidates_proposed"] = "candidates_proposed"
    user_query: str
    candidates: list[ActionCandidate]
    recommended_index: int | None
    fallback_message: str | None  # "더 명확한 키워드를 알려주세요" 등

class GateTarget(BaseModel):
    kind: Literal["target_selected"] = "target_selected"
    action_id: str
    code_method_fqn: str
    location: CodeLocation

class GateCode(BaseModel):
    kind: Literal["code_extracted"] = "code_extracted"
    java_source: str
    dependencies: list[Dependency]
    highlighted_anchors: list[AnchorRange]

class GatePython(BaseModel):
    kind: Literal["python_generated"] = "python_generated"
    python_source: str
    idiom_diffs: list[IdiomDiff]
    confidence: float

class GateFixtures(BaseModel):
    kind: Literal["fixtures_synthesized"] = "fixtures_synthesized"
    fixtures: list[FixtureRow]
    schema_summary: SchemaSummary

class GateSandbox(BaseModel):
    kind: Literal["sandbox_executed"] = "sandbox_executed"
    results: list[CaseResult]
    invariant_status: InvariantStatus
    baseline_diff: BaselineDiff | None

GatePayload = Annotated[
    Union[GateCandidates, GateTarget, GateCode, GatePython, GateFixtures, GateSandbox],
    Field(discriminator="kind"),
]
```

차용 원본: Section 2 의 `Hypothesis` union (`backend/application/authoring/capabilities/hypothesis.py:210-213`).

---

## 5. 영속화 — `section3_decision_log` 테이블

`authoring_decision_log` (`backend/application/authoring/orm.py`) 와 동일 컬럼 구조 (협업 요청 #3):

```sql
CREATE TABLE section3_decision_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id VARCHAR NOT NULL,
    turn_no INTEGER NOT NULL,
    gate_kind VARCHAR NOT NULL,       -- DecisionKind literal
    payload_json TEXT NOT NULL,        -- GatePayload serialized
    user_response_json TEXT,           -- 사용자 선택/수정 내용 (없으면 NULL)
    created_at DATETIME NOT NULL,
    INDEX(session_id, turn_no)
);
```

Section 3 의 `add_decision()` + `list_decisions()` 함수 (Section 2 의 `session.py:190-233` 패턴 그대로):

```python
# backend/section3/agents/multiturn/persistence.py
def add_gate_decision(session_id, turn_no, gate_payload, user_response=None): ...
def list_gate_decisions(session_id) -> list[GateDecision]: ...
def replay_session(session_id) -> SessionState: ...  # 세션 끊긴 후 resume
```

> **마이그레이션 협업 요청**: `migrations/versions/2026_05_18_006_section3_decision_log.py` 신설 필요.
> Section 2 의 `authoring_decision_log` 마이그레이션 패턴 그대로 — Section 2 owner 가 진행 권장.

---

## 6. Pending Action Gate

Section 2 의 `backend/core/session.py:70-87` (`add_pending_action` / `resolve_action`) 그대로 재사용.

흐름:
1. Gate N 결과 surface 시 `add_pending_action(session_id, gate_payload)` 호출 → UUID 받음
2. SSE event 에 그 UUID 동봉
3. 사용자가 카드의 선택/승인 버튼 클릭 → `POST /api/section3/confirm/{gate_kind}/{action_id}` 호출
4. 서버는 `resolve_action(action_id, approved=True)` 호출 → 다음 게이트 진입

장점: core 모듈이라 신규 구현 0, 그대로 차용.

---

## 7. Endpoint 신설 / 변경

### 신설
- `POST /api/section3/multiturn/start` — session 생성 + Gate 1 진입
- `POST /api/section3/multiturn/respond/{session_id}` — 사용자 응답 받아 다음 게이트 처리
- `POST /api/section3/multiturn/confirm/{gate_kind}/{action_id}` — pending action 해소
- `GET  /api/section3/multiturn/session/{session_id}` — replay (decision_log 기반)
- `GET  /api/section3/multiturn/session/{session_id}/stream` — SSE 실시간 게이트 진행

### 기존 (보존)
- `POST /api/section3/chat` — 옛 단발 chat 그대로 (병행 운영). frontend 가 새 멀티턴 enable flag 로 분기.

차용 원본: Section 2 의 `backend/api/authoring.py:1182-1227` (confirm endpoint).

---

## 8. Frontend 변화

### 새 컴포넌트 (`frontend/src/components/section3/multiturn/`)
- `MultiturnChat.tsx` — 메인 컨테이너, SSE 구독, 게이트 카드 누적 렌더
- `GateCandidatesCard.tsx` — 후보 list + ★ 추천 + "다른 거" 버튼
- `GateTargetCard.tsx` — action 상세 + 확인/수정 버튼
- `GateCodeCard.tsx` — Java 코드 surface + highlight (sim_v2 anchor 활용)
- `GatePythonCard.tsx` — Python 변환 결과 + idiom diff
- `GateFixturesCard.tsx` — Order 테이블 + 행 수정 가능
- `GateSandboxCard.tsx` — 실행 결과 + invariant status + "다시/OK" 버튼
- `useMultiturnSession.ts` — store hook (Zustand)

### 기존 (보존)
- `BridgeChatPanel.tsx` — 옛 단발 chat 그대로
- Toggle: section 상단에 "🆕 멀티턴 chat 시도" 버튼 → MultiturnChat 으로 switch

차용 원본: `frontend/src/components/sections/modeling/AuthoringMode.tsx:55-100` (turn 진행 UI 패턴).

---

## 9. 협업 요청 (Section 2 owner)

| # | 항목 | 영역 | mock 으로 우선 가능? |
|---|---|---|---|
| 1 | `ontology.db` 시드 보충 (impact_analysis 살리기) | `backend/modeling/ontology/` | ❌ — impact_analysis 게이트 도입 시 필수 |
| 2 | OntologyClient API 3 endpoint | `backend/modeling/api/` | ✅ — mock 으로 시작, 추후 swap |
| 3 | `section3_decision_log` 마이그레이션 | `migrations/versions/` | ⚠ — alembic 셋업 필요. Section 3 측에서 PR 후 Section 2 리뷰? |

### Mock 전략 (협업 요청 #2)
미구현 endpoint 는 다음 fallback:
- `ontology.get_action_detail(id)` → sim_v2 의 `load_action(session, id, repo_id)` 결과를 동일 schema 로 변환
- `ontology.get_method_body(fqn)` → sim_v2 의 `load_body_text(session, fqn, repo_id)` 그대로
- `ontology.get_entity_schema(name)` → sim_v2 의 `synthesize_fixtures` 가 내부적으로 사용하는 schema 추출 로직 직접 호출

→ Section 2 endpoint 가 나오면 swap. Section 3 코드는 영향 없음 (tool wrapper 만 교체).

---

## 10. Phased Rollout

### Phase 0 (현재, 진행 중)
- [x] 4 인계 문서 정독
- [x] 본 spec 작성
- [ ] User 리뷰 + adjustment

### Phase 1 — 인프라 (~1주)
- [ ] `backend/section3/agents/multiturn/` 패키지 scaffold
- [ ] `section3_decision_log` ORM + alembic 마이그레이션 (협업 요청 #3)
- [ ] `GatePayload` discriminator union schema
- [ ] Pending action wiring (core 재사용)
- [ ] 4 endpoint 신설 (`start`/`respond`/`confirm`/`session`)
- [ ] Mock ontology tool wrapper 3개

### Phase 2 — 게이트 단위 (~2주, 1 게이트씩)
- [ ] Gate 1 (candidates) — sim_v2 find_action_candidates wiring + 카드 UI
- [ ] Gate 2 (target) — selection 확인 + 카드
- [ ] Gate 3 (code) — Java 추출 + highlight 카드
- [ ] Gate 4 (python) — sim_v2 W75 + diff 카드
- [ ] Gate 5 (fixtures) — entity schema → fixture table 카드
- [ ] Gate 6 (sandbox) — run + result 카드

### Phase 3 — 통합 + 검증 (~3-4일)
- [ ] End-to-end: "주문 검증 액션이 뭐야" → 6 게이트 완주
- [ ] Replay 시나리오 — 세션 끊기고 다음날 resume
- [ ] "다시" 분기 — gate 4 에서 gate 3 으로 돌아가기 등
- [ ] 데모 시나리오 3 개: action 직접 / 자연어 일반 / 자연어 모호

### Phase 4 — 옛 path deprecate (optional)
- [ ] Frontend 토글 default 를 멀티턴으로
- [ ] 옛 `bridge_agent.py` 의 `_handle_explain` / sandbox 분기 deprecate notice
- [ ] 일정 기간 후 옛 endpoint 제거

---

## 11. 위험 / Open Question

1. **LLM cost** — 6 게이트 × tool 호출 시 비용 증가. budget 추적 + Sonnet/Opus tier 선택 필요.
2. **사용자 인내** — 6 게이트 다 통과는 느림. "skip" / "auto" 모드 (LLM 추천을 자동 승인) 옵션 고려.
3. **세션 cleanup** — 끊긴 세션 무한 누적 시 decision_log 비대화. retention 정책?
4. **동시성** — 같은 세션에 동시 요청 들어오면? lock 또는 sequence number?
5. **Section 2 dependency 일정** — 협업 요청 3 항목 timeline 미정. mock 으로 얼마나 진행 가능한가?

---

## 12. 참고

- 본 spec 의 원본: `toClaude/simulation/section3_handoff_report.html` §6 (멀티턴 재설계 방향)
- Section 2 차용 매트릭스: 같은 보고서 §6.7
- Section 2 코드 위치 (read-only): `backend/application/authoring/`
- sim_v2 자산: `backend/section3/sim_v2_bridge.py` (16 public 심볼)
