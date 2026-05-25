# Section 3 Chat — 멀티턴 Agent 재설계 SPEC (v2)

> **목표**: 현재 단발성 stream chat (`backend/section3/agents/bridge_agent.py`) 을
> sim_v2 자산 + Section 2 ontology 를 활용하는 **3 게이트 멀티턴 agent** 로 재설계.
>
> **작성일**: 2026-05-17 (v2)
> **브랜치**: `section3/chat-agent-redesign`
> **차용 원본**: `backend/application/authoring/` (Section 2)
> **이전 버전**: v1 — Section 3 개발자가 작성한 6 게이트 spec (git history 의 `9cb354e`)

---

## 0. v2 변경 요약 (사용자 검토 + 4 sub-agent 결과 반영)

| 영역 | v1 | v2 |
| --- | --- | --- |
| Gate 수 | **6 gates** | **3 gates** (Alt A) |
| Pending-action 패턴 | `core/session.py` 의 `add_pending_action` "재사용" | **폐기** — wiki 패턴 오인. authoring 의 직접 confirm 패턴 차용 |
| decision_log 마이그레이션 | alembic | **alembic 없이**, `Base.metadata.create_all()` 패턴 (authoring 의 실제 방식) |
| LLM client | 미정 | OpenAI (`backend/section3/llm/openai_client.py` 기존 유지) |
| async 경계 | 묵시적 | sim_v2 sync 함수 호출은 `asyncio.to_thread` 명시 |
| repo_id 처리 | hardcoded constant | 세션 state |
| replay 의미 | 모호 | **source-of-truth (hydrate)** — payload 자체 self-contained |
| Q5 비전 (사용자) | 없음 | §13 신설 — **영향도 검토 + 시뮬레이션 두 흐름 + Provenance** |

**한 줄 결론**: 6 게이트는 Section 2 의 1,227 LOC 패턴을 미러링해 과한 측면 — 3 게이트로 압축해도 핵심 UX ("사용자가 각 단계 결과 보고 승인") 보존. wiki 패턴 차용 오류는 발견 즉시 수정.

---

## 1. 3 게이트 정의

| # | Gate | LLM action | Tool calls | Output payload (요약) | 다음 진입 조건 |
|---|---|---|---|---|---|
| I | **target_selected** | 자연어 → intent 분류 + 후보 검색 + 선택 검증 | `sim_v2.find_action_candidates` · `ontology.search_action_by_keyword` · `ontology.get_action_detail` | `{intent: "simulate"|"impact", candidates[], recommended_index, selected: ActionRef|None}` | 사용자가 후보 선택 또는 "다른 거" |
| II | **bundle_prepared** | Java 추출 → Python 변환 → fixture 합성 (한 번에 surface, 표 안에서 사용자가 행 수정 가능) | `ontology.get_method_body` · `sim_v2.translate_java_to_python` · `ontology.get_entity_schema` · `sim_v2.synthesize_fixtures` | `{java_source, python_source, idiom_diffs[], fixtures[], schema_summary}` | 사용자 "이 bundle 로 진행" 또는 행 수정 |
| III | **executed** | 실행 + 진단 (시뮬 분기) 또는 영향도 그래프 (impact 분기) | sim 분기: `sim_v2.run_fixtures_in_process` · `sim_v2.quick_diagnose_action` · impact 분기: `sim_v2.quick_diagnose_action` · `ontology.get_caller_graph` (mock) | 시뮬: `{results[], invariant_status, baseline_diff}` · 영향도: `{affected_methods[], confidence, sim_v2_findings}` | 사용자 "OK / 다시 / 다른 케이스" |

각 게이트 진입 시 `add_gate_decision(kind=...)` 호출 → `section3_decision_log` DB 영구화.

### 1.1 Gate I 의 intent 분류 (Q5 비전 반영)

자연어 query 가 들어오면 Gate I 의 LLM 이 두 분기 중 하나로 결정:

- **`intent="simulate"`** — "주문 검증 액션 시뮬해줘", "엣징 사양 룰 돌려봐" 등 → Gate II / III 모두 거침
- **`intent="impact"`** — "cumulativeProductivity 바꾸면 뭐가 영향받아?" 등 → Gate II skip, Gate III 의 impact 분기로 직행

판단 모호 시 사용자에게 "어느 쪽이 의도인가요?" 카드 surface.

---

## 2. State Machine

```
                    ┌─ intent=simulate ─▶ bundle_prepared ─▶ executed (sim)
target_selected ────┤
                    └─ intent=impact ──────────────────────▶ executed (impact)

(어느 단계든)
사용자 "다른 후보"  → target_selected 재실행 (이전 candidates 제외)
사용자 "이 bundle 아님" → bundle_prepared 재실행 (사용자가 수정한 조건 반영)
사용자 "다른 fixture" → bundle_prepared 의 fixture 부분만 재합성
사용자 "다시 실행"   → executed 재실행 (같은 bundle)
사용자 "OK"          → session.status = done
```

**"다시" fan-out 명시화** (v1 의 LLM 위임 폐기): 각 카드에 후보 행동을 enumerable 한 button 으로 surface — `[다른 후보] [bundle 수정] [실행 재시도] [완료]`. LLM 은 *내용* 만 채우고 *분기 결정* 은 사용자가.

---

## 3. Tool Catalog

```python
# backend/section3/agents/multiturn/tools.py
TOOLS = {
    # Ontology (Section 2 API — Phase 1 mock, Phase 2 swap)
    "ontology.search_action_by_keyword":  OntologySearchTool,
    "ontology.get_action_detail":         OntologyActionDetailTool,
    "ontology.get_method_body":           OntologyMethodBodyTool,
    "ontology.get_entity_schema":         OntologyEntitySchemaTool,
    "ontology.get_caller_graph":          OntologyCallerGraphTool,    # impact 분기

    # sim_v2 (backend/section3/sim_v2_bridge.py 그대로 wrap)
    "sim_v2.find_action_candidates":      SimV2CandidatesTool,
    "sim_v2.translate_java_to_python":    SimV2TranslateTool,         # W75
    "sim_v2.synthesize_fixtures":         SimV2FixturesTool,          # W71
    "sim_v2.run_fixtures_in_process":     SimV2RunTool,
    "sim_v2.quick_diagnose_action":       SimV2DiagnoseTool,
}
```

게이트별 `allowed` 좁히기 (safety):
- Gate I: `[search_action_by_keyword, find_action_candidates, get_action_detail]`
- Gate II: `[get_method_body, translate_java_to_python, get_entity_schema, synthesize_fixtures]`
- Gate III sim: `[run_fixtures_in_process, quick_diagnose_action]`
- Gate III impact: `[get_caller_graph, quick_diagnose_action]`

Tool 호출은 `RunTracker` + `ToolLogger` 패턴 (Section 2 의 `option_proposer.py` 차용) — budget 추적 + DB 로깅 + SSE event.

---

## 4. Payload Discriminator Union

```python
# backend/section3/agents/multiturn/schemas.py
from typing import Annotated, Literal, Union
from pydantic import BaseModel, Field


# Provenance (Q5 비전 — "확실한 근거 surface")
class Provenance(BaseModel):
    source: Literal[
        "ontology",          # Section 2 API
        "sim_v2",            # sim_v2 자산
        "llm_inference",     # LLM 추론
        "user_input",        # 사용자 입력
    ]
    detail: str              # e.g. "ontology.get_action_detail(action_id=42)"
    confidence: float | None # 0.0~1.0 또는 None


class GateTarget(BaseModel):
    kind: Literal["target_selected"] = "target_selected"
    intent: Literal["simulate", "impact", "ambiguous"]
    user_query: str
    candidates: list[ActionCandidate]
    recommended_index: int | None
    selected: ActionRef | None
    sources: list[Provenance]


class GateBundle(BaseModel):
    kind: Literal["bundle_prepared"] = "bundle_prepared"
    target: ActionRef
    java_source: str
    python_source: str
    idiom_diffs: list[IdiomDiff]
    fixtures: list[FixtureRow]
    schema_summary: SchemaSummary
    sources: list[Provenance]
    confidence: float


class GateExecutedSimulation(BaseModel):
    kind: Literal["executed_simulation"] = "executed_simulation"
    mode: Literal["simulate"] = "simulate"   # UI sugar
    results: list[CaseResult]
    invariant_status: InvariantStatus
    baseline_diff: list[BaselineDiff] | None
    sources: list[Provenance]


class GateExecutedImpact(BaseModel):
    kind: Literal["executed_impact"] = "executed_impact"
    mode: Literal["impact"] = "impact"        # UI sugar
    affected_methods: list[AffectedMethod]
    sim_v2_findings: list[Finding]
    confidence: float
    sources: list[Provenance]


# Flat union — kind 자체에 simulation/impact 인코딩 (Pydantic 의 nested
# Annotated discriminator 가 같은 kind 두 변종을 중복 인식하기 때문).
GatePayload = Annotated[
    Union[GateTarget, GateBundle, GateExecutedSimulation, GateExecutedImpact],
    Field(discriminator="kind"),
]
```

차용 원본: Section 2 의 `Hypothesis` union (`backend/application/authoring/capabilities/hypothesis.py:210-213`) — 3 mutually exclusive shape 와 동일 구조.

**Provenance 가 모든 payload 의 first-class 필드** — frontend 카드에 "이 정보는 X 에서 왔다" 를 매번 surface (Q5 비전).

---

## 5. 영속화 — `section3_decision_log` 테이블 (alembic 없이)

`authoring_decision_log` (`backend/application/authoring/orm.py`) 와 동일 구조. **authoring 패턴 그대로 `Base.metadata.create_all()` 사용 (alembic 없음)**:

```python
# backend/section3/agents/multiturn/orm.py
from sqlalchemy import Column, Integer, String, Text, DateTime, Index
from backend.core.db import Base


class Section3DecisionLogRow(Base):
    __tablename__ = "section3_decision_log"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    session_id      = Column(String, nullable=False, index=True)
    turn_no         = Column(Integer, nullable=False)
    gate_kind       = Column(String, nullable=False)       # "target_selected" | ...
    payload_json    = Column(Text, nullable=False)          # GatePayload serialized
    user_response_json = Column(Text, nullable=True)        # 사용자 응답 (없으면 None)
    created_at      = Column(DateTime, nullable=False)

    __table_args__ = (Index("ix_section3_decision_log_session_turn",
                            "session_id", "turn_no"),)
```

```python
# backend/section3/agents/multiturn/persistence.py

def add_gate_decision(session_id, turn_no, gate_payload, ...) -> int: ...
def list_gate_decisions(session_id) -> list[Section3Decision]: ...
def update_user_response(decision_id, user_response) -> None: ...
def replay_session(session_id) -> SessionState: ...
```

**replay 의미 = source-of-truth (hydrate)** — payload_json 이 자체로 완결. sim_v2 tool 재실행 없음. payload 의 fixed snapshot 을 그대로 카드로 재구성. 추론 결과의 drift 없음 보장.

**`Base.metadata.create_all()` wire**: `backend/main.py` 의 startup 부분에 `Section3DecisionLogRow` import 후 자동 생성. (`backend/application/authoring/orm.py` 의 패턴 그대로)

---

## 6. Confirm 패턴 (~~Pending Action Gate~~ 폐기)

> **v1 의 §6 폐기**: spec v1 은 `backend/core/session.py:70-87` 의 `add_pending_action` /
> `resolve_action` 을 "재사용" 한다고 했으나, **이 함수는 wiki 전용** (`ApprovalAction = WikiWriteAction | ...`).
> Section 2 의 authoring 은 이걸 안 씀. 따라서 직접 차용 불가.

**v2 의 패턴**: Section 2 authoring 의 실제 방식 그대로 — DB-only direct confirm.

```
1. Gate N 완료 시 → add_gate_decision(session_id, turn_no, payload) → row id 반환
2. SSE event 에 row id + payload 동봉
3. 사용자가 카드의 [선택] / [bundle 수정] / [다른 후보] 버튼 클릭
4. POST /api/section3/multiturn/confirm/{session_id}/{turn_no}
   body: {action: "confirm" | "modify" | "retry", user_response: {...}}
5. 서버: update_user_response(row id, user_response) → 다음 gate 진입 또는 같은 gate 재실행
```

**장점**: server restart 후도 resume 가능 (in-memory state 없음). decision_log 가 단일 source-of-truth.

차용 원본: `backend/api/authoring.py:1182-1227` (Section 2 confirm endpoint).

---

## 7. Endpoint

### 신설
- `POST /api/section3/multiturn/start` — session 생성 + Gate I 진입
- `POST /api/section3/multiturn/respond/{session_id}` — 사용자 메시지 받아 다음 gate 처리
- `POST /api/section3/multiturn/confirm/{session_id}/{turn_no}` — 카드 버튼 응답 처리
- `GET  /api/section3/multiturn/session/{session_id}` — replay (decision_log 기반 hydrate)
- `GET  /api/section3/multiturn/session/{session_id}/stream` — SSE 실시간 진행

### 기존 (보존)
- `POST /api/section3/chat` — 옛 단발 chat. frontend toggle 로 분기.

---

## 8. Frontend

### 새 컴포넌트 (`frontend/src/components/section3/multiturn/`) — 4 컴포넌트 (8 → 4)
- `MultiturnChat.tsx` — 메인 컨테이너, SSE 구독, 게이트 카드 누적
- `GateTargetCard.tsx` — Gate I 후보 + intent + 선택 버튼
- `GateBundleCard.tsx` — Gate II 코드 + Python + fixture (탭/아코디언으로 한 카드 안에 묶음, fixture 행 inline edit)
- `GateExecutedCard.tsx` — Gate III sim/impact 분기 결과
- `ProvenanceBadge.tsx` (공용) — Q5 비전, 모든 카드에 "근거" 표시

### 기존 보존
- `BridgeChatPanel.tsx` (단발 chat)
- Section 상단 토글: "🆕 멀티턴 시뮬레이션 시도"

---

## 9. 협업 요청 (Section 2 owner)

| # | 항목 | mock 우선 가능? |
|---|---|---|
| 1 | `ontology.db` 시드 보충 | △ (mock 으로 demo 가능, 실측은 후순위) |
| 2 | OntologyClient API 5 endpoint (search / action_detail / method_body / entity_schema / **caller_graph**) | ✅ — Phase 1 mock, Phase 2 swap |
| ~~3~~ | ~~alembic 마이그레이션~~ | **삭제** — authoring 패턴 따라 alembic 안 씀 |

### Mock 전략 (Phase 1)
미구현 endpoint 는 sim_v2 fallback 으로:
- `ontology.get_action_detail(id)` → sim_v2 `load_action(session, id, repo_id)`
- `ontology.get_method_body(fqn)` → sim_v2 `load_body_text(session, fqn, repo_id)`
- `ontology.get_entity_schema(name)` → sim_v2 `synthesize_fixtures` 의 schema 추출 로직을 helper 로 추출 (`fixture_synthesizer.extract_entity_schema()` 신설)
- `ontology.get_caller_graph(fqn)` → sim_v2 `quick_diagnose_action` 의 일부 (영향도 결과 + 빈 graph)

**httpx-based abstraction**: `OntologyClient` 가 실제 API 구조를 흉내내는 클래스. mock 은 `MockOntologyClient` 가 위 sim_v2 fallback 호출. swap 시 base URL 만 변경.

---

## 10. Phased Rollout

### Phase 0 (완료)
- [x] 4 인계 문서 정독
- [x] v1 spec 작성
- [x] v2 갱신 (4 sub-agent 검토 + 사용자 결정 반영)

### Phase 1 — 인프라 + Scaffold (이번 세션 ~ 다음 며칠)
- [x] **Step 1a** — spec v2 + HANDOFF 갱신 (이 문서)
- [ ] **Step 1b** — package scaffold + schemas (`backend/section3/agents/multiturn/__init__.py`, `schemas.py`)
- [ ] **Step 1c** — ORM + persistence (`orm.py`, `persistence.py`, `Base.metadata.create_all` wire)
- [ ] **Step 1d** — Tools wrapper + `OntologyClient` mock (httpx abstraction)
- [ ] **Step 1e** — 4 endpoint 신설 (gate logic 은 stub)
- [ ] **Step 1f** — unit tests + verification
- [ ] **Step 1g** — Step 1 summary + doc sync

### Phase 2 — 게이트 단위 (1~2주, 1 게이트씩 production wiring)
- [ ] Gate I (target) — intent 분류 + 후보 + LLM 통합
- [ ] Gate II (bundle) — Java/Python/fixture 묶음 + edit-in-place
- [ ] Gate III sim 분기 — run + diagnose
- [ ] Gate III impact 분기 — caller_graph + diagnose

### Phase 3 — 통합 + 검증
- [ ] End-to-end: "주문 검증 액션 시뮬" / "cumulativeProductivity 영향도"
- [ ] Replay 시나리오 (decision_log hydrate)
- [ ] "다른 후보" / "bundle 수정" / "다시 실행" 분기
- [ ] 데모 시나리오 3개 (시뮬 / 영향도 / 모호)

### Phase 4 (optional)
- [ ] frontend toggle default 멀티턴으로
- [ ] 옛 `bridge_agent.py` 흐름 deprecate

---

## 11. 위험 / Open Question

| # | 위험 | 완화 |
|---|---|---|
| 1 | LLM cost (3 게이트 + tool) | per-gate token budget · Haiku→Sonnet escalation · 사용자 한 세션 cap |
| 2 | 사용자 인내 (3 게이트도 느릴 수 있음) | 각 카드 streaming surface · "auto" toggle (LLM 자동 confirm) Phase 3 에서 |
| 3 | 세션 cleanup (decision_log 누적) | retention 7일 default · 사용자 별 cap |
| 4 | 동시성 (같은 session 동시 요청) | turn_no 기반 optimistic CAS (`UPDATE ... WHERE turn_no = ?`) |
| 5 | Section 2 dependency | mock 으로 Phase 1~3 완주 가능. swap 은 Phase 4 |
| 6 | Replay vs sim_v2 drift | source-of-truth = payload hydrate. tool 재실행 없음 |
| 7 | Auth/ownership | session_id 를 UUID + cookie 바인딩 — Phase 2 |
| 8 | Budget 소진 mid-session | `gate_blocked` decision kind 추가 · 사용자 confirm 시 같은 turn_no 로 retry |

---

## 12. 참고

- v1 spec: git history 의 commit `9cb354e` (`toClaude/simulation/CHAT_REDESIGN_SPEC.md` 의 첫 버전, 291 LOC, 6 gates)
- 사용자 결정 페이지: `toClaude/simulation/chat-redesign-review.html`
- Section 2 차용 원본:
  - `backend/application/authoring/capabilities/hypothesis.py` (Hypothesis discriminator union)
  - `backend/application/authoring/session.py:190-233` (add_decision + list_decisions)
  - `backend/api/authoring.py:1182-1227` (confirm endpoint)
- sim_v2 자산: `backend/section3/sim_v2_bridge.py` (16 public 심볼, 9 tool wire 됨)

---

## 13. Q5 비전 — 영향도 검토 + 시뮬레이션 두 흐름 (사용자 요구사항)

> **사용자 인용 (2026-05-17)**:
> "시뮬레이션 영역(섹션3)에는 최종적으로 자연어 기반 영향도 검토 + 파이썬 코드
> 시뮬레이션이 자연어 인터뷰 및 UI기능 기반으로 시작해서 동작할 수 있도록 해야해.
> 그 재료는 섹션2에서 만든 온톨로지 및 코드 매핑이 기반이 되어야하고, 둘의 통신은
> api로 하고. 최종적으로 사용자는 에이전트와 대화하면서 빠진내용은 빠진대로,
> 실제 작성된 온톨로지 기반의 추론 및 검토를 편하고 확실한 근거를 보면서
> 진행할 수 있어야해"

### 13.1 두 흐름

**(A) 시뮬레이션 분기** (`intent="simulate"`)
- 입력: "주문 검증 액션 시뮬해줘", "엣징 사양 룰 돌려봐"
- Gate I → II → III(sim)
- 출력: invariant_status / baseline_diff / case 결과

**(B) 영향도 검토 분기** (`intent="impact"`)
- 입력: "cumulativeProductivity 바꾸면 뭐가 영향받아?"
- Gate I → III(impact) (Gate II skip)
- 출력: caller graph + sim_v2 finding + confidence

### 13.2 재료 출처 — Section 2 ↔ Section 3 API 통신

- **모든 ontology 접근은 `OntologyClient` (httpx-based) 통과** — 직접 DB 접근 X
- Phase 1: `MockOntologyClient` 가 sim_v2 fallback 호출
- Phase 2 (Section 2 API ready): `HTTPOntologyClient` 로 swap. 호출 측 코드 변경 0.

### 13.3 Provenance — "확실한 근거"

모든 `GatePayload` 가 `sources: list[Provenance]` 필드 보유. 각 카드 UI 에 다음 형태로 surface:

```
[Gate II Bundle]
  Java source ← ontology.get_method_body("com.ontong.scm.OrderService.validateOrder")
                Provenance: ontology / confidence: 1.0
  Python source ← sim_v2.translate_java_to_python(...)
                  Provenance: sim_v2 / confidence: 0.93
                  Idiom diffs: List.add → .append, BigDecimal → Decimal
  Fixtures (5 rows) ← sim_v2.synthesize_fixtures(..., schema=order_schema)
                       Provenance: sim_v2 / confidence: 1.0
                       Source schema: ontology.get_entity_schema("Order")
```

### 13.4 "빠진내용은 빠진대로"

ontology 가 불완전해도 차단 안 됨. Provenance 가 `confidence` 를 surface 하므로:

- `ontology.get_method_body` 실패 → fallback `sim_v2.load_body_text` (confidence: 0.85)
- entity_schema 없음 → primitive type 으로만 fixture 합성 (confidence: 0.5)
- caller_graph 없음 → "Section 2 의 graph data 누락 — sim_v2 의 sandbox 만 의존" 명시 카드

사용자는 카드의 confidence + sources 를 보고 신뢰도 직관 판단.

---

## 14. 다음 행동 (이 문서 commit 후)

1. **Step 1b 진입** — `backend/section3/agents/multiturn/` 패키지 scaffold + `schemas.py` 작성
2. Step 1g 까지 진행 후 Phase 2 진입

세부: `toClaude/simulation/HANDOFF.md` 의 "🔴 다음 세션 첫 작업" 갱신본 참조.
