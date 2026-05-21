# Section 3 · 시뮬레이션 에이전트 RFC

> Section 3 의 새 탭 **시뮬레이션 에이전트** (route key: `simulation`) 명세.
> multiturn reference (3-gate · 6 intent) 위에 IT 운영자 페르소나 + 5 시나리오
> + intent 별 차별 UI/UX 를 입힌다. multiturn 탭은 그대로 보존.

**작성일**: 2026-05-21
**브랜치**: `jyu-simul` (← `origin/share/section2-modeling-foundation`)
**참조 spec**: `toClaude/simulation/CHAT_REDESIGN_SPEC.md` (multiturn 6-gate → 3-gate 재설계)
**reference 코드**: `backend/section3/agents/multiturn/` (17 모듈) ·
`frontend/src/components/section3/multiturn/` (13 컴포넌트)

---

## 1. 페르소나 & 5 시나리오

**페르소나**: slab-design 시스템 IT 운영자
한국어로 자연어 질문을 던지면, agent 가 ontology 응답과 Java 코드 위에서 시뮬레이션
혹은 영향도 분석을 매 단계 확인받으며 진행한다.

| # | 시나리오 | 트리거 질문 예 | 우세 intent | gate 흐름 |
|---|---|---|---|---|
| ① | 기능 개선 요청 | "단중 계산 로직 바꾸면 어디 영향?" | impact + locate | I → III(impact) |
| ② | 기준 데이터 변경 영향 | "이 standard 값을 0.5→0.3 으로 바꾸면?" | impact + simulate | I → II → III |
| ③ | 주문 데이터 변경 비교 | "이 주문의 thickness 만 바꿔 돌려봐" | simulate | I → II → III(diff) |
| ④ | 자연어 → 코드 위치 | "edging 룰은 어디 박혀있어?" | locate + explain | I → III(locate) |
| ⑤ | 신규 품종 추가 영향 | "신규 품종 HC600X 추가되면?" | hypothesis | I → II(virtual term) → III |

---

## 2. 명명 결정

| 항목 | 값 | 비고 |
|---|---|---|
| nav id (View) | `simulation` | 기존 `multiturn`, `dashboard` 와 별개 |
| nav label | `시뮬레이션 에이전트` | "멀티턴 agent" 와 라벨 구분 |
| URL | `?section=simulation&view=simulation&sid=<sid>` | section3 안의 한 view |
| API prefix | `/api/section3/simulation` | `/start`, `/respond/{sid}`, `/replay/{sid}` |
| 백엔드 폴더 | `backend/section3/agents/simulation/` | multiturn 패턴 차용, 신규 작성 |
| 프론트 폴더 | `frontend/src/components/section3/simulation/` | multiturn 패턴 차용, 신규 작성 |
| HTTP client | `frontend/src/lib/section3/simulation.ts` | multiturn.ts 패턴 차용 |
| 결정 로그 테이블 | `section3_simulation_decision_log` | multiturn 의 decision_log 와 분리 (간섭 방지) |

---

## 3. 6 Intent (multiturn 차용)

multiturn 의 `MultiturnIntent = Literal["simulate","impact","ambiguous","locate","explain","hypothesis"]`
그대로. classifier 도 그대로 import 한다 (`backend.section3.agents.multiturn.intent`).

| intent | 사용자 의도 | 시나리오 매핑 |
|---|---|---|
| simulate | 어떤 action/method 를 입력 fixture 로 돌려보고 결과를 보고 싶다 | ②③ |
| impact | 어떤 entity/method 가 바뀌면 어디가 영향받는지 추적하고 싶다 | ①② |
| locate | 자연어 키워드가 어느 코드 위치에 박혀있는지 찾고 싶다 | ④ |
| explain | 어떤 term/action 이 무엇인지 자연어로 설명을 받고 싶다 | ④ |
| hypothesis | 가상 시나리오 ("X 가 새로 추가되면", "Y 가 z 로 바뀌면") 를 검증하고 싶다 | ⑤ |
| ambiguous | LLM 이 분류 못 함 → 사용자에게 의도 확인 카드 surface | (모든 분기 진입 전) |

구현 순서: **impact → simulate → hypothesis → locate → explain**.

---

## 4. 3 Gate 흐름

multiturn 의 3-gate (`CHAT_REDESIGN_SPEC.md` §1) 그대로 채택.

```
                    ┌─ intent=simulate ────▶ bundle_prepared ─▶ executed (sim)
target_selected ────┤
                    ├─ intent=impact ──────────────────────────▶ executed (impact)
                    ├─ intent=locate ──────────────────────────▶ executed (locate)
                    ├─ intent=explain ─────────────────────────▶ executed (explain)
                    └─ intent=hypothesis ──▶ bundle_prepared ─▶ executed (sim·virtual)
```

각 게이트마다 `add_gate_decision(...)` 로 transcript 영구화. SSE 가 아닌 REST
요청·응답 모델 (multiturn 과 동일).

### 4.1 Gate I — `target_selected`
- LLM 호출: intent classification + 후보 검색
- payload: `{intent, candidates[], recommended_index, selected}`
- 다음 진입: 사용자가 후보 선택 / "다른 거" / "이 의도 아님"

### 4.2 Gate II — `bundle_prepared` (simulate · hypothesis 만)
- payload: `{java_source, python_source, idiom_diffs[], fixtures[], schema_summary}`
- 다음 진입: "이 bundle 로 진행" / fixture 행 인라인 수정

### 4.3 Gate III — `executed`
intent 별 분기:

| intent | 동작 + payload 핵심 |
|---|---|
| simulate | `sim_v2.run_fixtures_in_process` → `{results[], invariant_status, baseline_diff}` |
| impact | `ontology.get_caller_graph` + 영향 entity 추적 → `{affected_methods[], affected_rules[], affected_terms[], graph}` |
| locate | repo grep + ontology.code_methods → `{locations:[{file,line,method,snippet}], graph_highlight}` |
| explain | term/action 응답 합성 → `{summary, related:{terms,actions,rules}, ontology_objects[]}` |
| hypothesis | 가상 Term 합성 + simulate flow → `{virtual_term, sim_results, baseline_diff}` |

---

## 5. Intent 별 화면 wireframe (3-pane)

기본 layout: **좌(chat 33%) · 중(active gate 40%) · 우(graph + 7-tab viewer 27%)**.
중·우 패널이 intent 별로 swap.

### 5.1 simulate
```
좌(chat)              중(Bundle + 결과 diff)              우(graph + tabs)
- 사용자: …           STEP II/III · Bundle 카드           Term → Action → Method
- agent: thickness   ┌─ Java 원본 (collapsed)            ─ 그래프 (xyflow)
  action 찾았어요     ├─ Python (강조)                   ─ 7-tab viewer
- agent: bundle      ├─ idiom_diffs                     · Terms · Actions
  준비됐어요          ├─ Order fixture 표 (행 수정)       · CodeTypes · Rules
- [confirm card]     └─ [이 bundle 로 진행]             · Anchors · CallSites
                     ────────────────────────           · DelegatesTree
                     STEP III · 결과 2-col diff
                     변경 전 │ 변경 후 │ DIFF
```

### 5.2 impact
```
좌(chat)              중(영향 그래프 + 표)               우(caller_graph + delegates)
- 자연어 질문         ┌─ 영향받는 method ⌃ N건           caller_graph
- agent 응답          │  [표: fqn / via / score]         delegates_tree
- [의도 확인]         ├─ 영향받는 rule ⌃ N건             (영향 분포 highlight)
                     ├─ 영향받는 term ⌃ N건
                     └─ 그래프 (highlight 노드)
                       [재실행 / 다른 시작점]
```

### 5.3 locate
```
좌(chat)              중(코드 위치 표)                   우(code-types + call_sites)
- "edging 룰 어디?"   ┌─ 키워드 매칭 위치                code-types 탭
- agent: 5건 찾음     │  file:line · method · snippet    call_sites 탭
                     ├─ 정렬: relevance / file path     (highlight)
                     └─ 행 click → snippet 확장
```

### 5.4 explain
```
좌(chat)              중(자연어 답변 + 관련 객체)        우(term detail + rules)
- "Slab 단중이 뭐?"   ┌─ summary (markdown)              term detail
- agent: …            ├─ 관련 Term inline 카드            · effective_parts
                     ├─ 관련 Action inline 카드          · business_rules
                     └─ 관련 Rule inline 카드            · realizations
```

### 5.5 hypothesis
```
좌(chat)              중(가상 attribute + sim diff)      우(영향 그래프)
- "신규 품종 HC600X"  STEP II · 가상 Term attribute 입력  영향 분포
- agent: 가상 합성   ┌─ HC600X.thickness_min = 0.20    (가상 노드 강조)
- agent: 영향 분석   └─ [bundle 합성]
                     STEP III · simulate 결과 비교
                     기존 품종 결과 │ HC600X 결과 │ DIFF
```

### 5.6 ambiguous
중앙 패널에 의도 명확화 카드:
```
어느 쪽이 의도인가요?
[ ] thickness 액션을 시뮬 (simulate)
[ ] thickness 가 어디 영향 (impact)
[ ] thickness 코드 위치 (locate)
[다시 입력]
```

---

## 6. Tool Catalog (multiturn 차용)

```python
# backend/section3/agents/simulation/tools.py — multiturn.tools 그대로 import
from backend.section3.agents.multiturn.tools import (
    OntologySearchTool, OntologyActionDetailTool, OntologyMethodBodyTool,
    OntologyEntitySchemaTool, OntologyCallerGraphTool,
    Sim2FindCandidatesTool, Sim2TranslateTool, Sim2SynthesizeFixturesTool,
    Sim2RunFixturesTool, Sim2QuickDiagnoseTool,
)
```

신규 추가 도구 (5 종 intent 완성용):
- `ontology.repo_grep` — locate intent. ripgrep wrapper, code_methods 와 join.
- `ontology.synthesize_virtual_term` — hypothesis intent. `virtual:<slug>` Term 합성.
- `sim_v2.compare_runs` — simulate/hypothesis intent. baseline vs after 결과 diff.

---

## 7. 데이터 영속화

- 신규 테이블: `section3_simulation_decision_log`
  - `session_id`, `kind` (`target_selected`/`bundle_prepared`/`executed`/`ambiguous_clarified`),
    `payload_json`, `created_at`
  - PK: `(session_id, seq)` 자동 증가
- 세션 메타: `section3_simulation_session`
  - `session_id`, `repo_id`, `intent`, `status` (`active`/`done`/`aborted`), `created_at`, `updated_at`
- 마이그레이션: alembic 없이 `Base.metadata.create_all()` (multiturn 과 동일 방식)

---

## 8. 기존 컴포넌트 재사용 vs 신규

| 영역 | 재사용 | 신규 |
|---|---|---|
| intent classifier | `multiturn/intent.py` | — |
| tools 목록 | `multiturn/tools.py` 9개 | 3개 (repo_grep / virtual_term / compare_runs) |
| schemas | `multiturn/schemas.py` 베이스 | intent 별 payload 확장 (impact/locate/explain) |
| persistence | `multiturn/persistence.py` pattern | 새 테이블 2개 |
| LLM client | `backend/section3/llm/openai_client.py` | — |
| sandbox/translator | `backend/sim_v2/*` | — |
| 프론트 chat shell | `multiturn/MultiturnChat.tsx` 패턴 | `SimulationChat.tsx` 신규 |
| 게이트 카드 | `multiturn/GateBundleCard.tsx` 패턴 | intent 별 5종 카드 |
| 그래프 | `OntologyGraphMini` (xyflow) 패턴 | impact/hypothesis 노드 색상 추가 |
| 7-tab viewer | 기존 패턴 차용 | intent 별 노출 탭 조정 |

---

## 9. 구현 Phase 요약 (Plan)

| Phase | 산출물 | 검증 |
|---|---|---|
| A | 본 RFC commit | 사용자 OK |
| B | backend agents/simulation + api router + frontend chat shell + nav 추가 | `/start` → `/respond` 1-cycle smoke + tsc clean |
| C | Gate I — intent 분류 + 6 intent 후보 검색 | 5 시나리오 query 별 후보 surface 확인 |
| D | Gate II — Bundle (Java/Python/Order fixture) — simulate·hypothesis 한정 | thickness action body→python→fixture 표 |
| E | Gate III — 5 intent 분기 실행 | 시나리오 ②③⑤ before/after slab diff surface |
| F | intent 5종 차별 layout 완성 | 5종 캡처 |
| G | 변경 전/후 slab 결과 비교 deep | field-level diff + invariant 변화 |
| H | 5 시나리오 e2e 테스트 + demo guide + 인계 + HTML zip | pytest + tsc + 캡처 보고서 |

---

## 10. 기존 multiturn 보존 정책

- multiturn nav 그대로 유지
- multiturn `agents/` `components/` 폴더 read-only (cherry-pick 차용 OK)
- multiturn 의 6-gate spec (CHAT_REDESIGN_SPEC.md) 그대로 보존

---

## 11. 미해결·후속

- ontology.caller_graph 가 현재 mock 인지 real 인지 확인 후 Phase E impact 분기 깊이 결정
- LLM 비용/속도 — 6 intent classifier + 후보 검색 = 1 turn 당 LLM 호출 2~3 회 예상
- 변경 전/후 비교의 trace 깊이 — step-level vs field-level 선택은 Phase G 진입 전 확정
