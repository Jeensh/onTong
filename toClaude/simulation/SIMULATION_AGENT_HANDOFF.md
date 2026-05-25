# 시뮬레이션 에이전트 — 인계 문서

> Section 3 신규 탭 **시뮬레이션 에이전트** (`?view=simulation`) 의 구현 상태와
> 다음 작업 메모.
>
> 작업 일자: 2026-05-21
> 브랜치: `jyu-simul` (← `origin/share/section2-modeling-foundation`)
> RFC: `toClaude/simulation/SIMULATION_AGENT_RFC.md`
> 데모: `toClaude/simulation/SIMULATION_AGENT_DEMO.md`

---

## 구현 완료 (Phase A~H)

| Phase | 산출물 | 상태 |
|---|---|---|
| A | SIMULATION_AGENT_RFC.md 11-섹션 | ✅ commit |
| B | 신규 탭 scaffold (backend + frontend nav) | ✅ commit |
| C | Gate I — multiturn build_gate_i wire | ✅ 5 시나리오 query 분류 검증 |
| D | Gate II — Bundle (Java/Python/fixture) | ✅ confidence 0.85 확인 |
| E | Gate III — 5 intent 별 실행 분기 | ✅ e2e 4 intent 동작 확인 |
| F | UI intent 차별 layout (5 카드) | ✅ tsc clean |
| G | compare_runs + 변경 전·후 DIFF 카드 | ✅ endpoint 동작 |
| H | 8 e2e 테스트 + demo guide + 본 문서 | ✅ 8/8 PASS |

---

## 핵심 코드 위치

**Backend**
```
backend/section3/agents/simulation/
  __init__.py              — 모듈 docstring
  orm.py                   — section3_simulation_{session,decision_log} 테이블
  persistence.py           — start_session / add_gate_decision / replay_session
  schemas.py               — multiturn re-export + locate/explain/compare 신규
  compare_runs.py          — 변경 전·후 두 번 simulate + field-level diff
backend/section3/api/
  simulation_router.py     — /start /respond/{sid} /replay/{sid}
backend/main.py            — router include + ORM import + bootstrap
```

**Frontend**
```
frontend/src/lib/section3/
  simulation.ts            — HTTP client
frontend/src/components/section3/simulation/
  SimulationChat.tsx       — 3-pane shell + chat
  IntentCandidateCard.tsx  — target_selected 카드 (ambiguous 분기 포함)
  BundlePreviewCard.tsx    — bundle_prepared 카드 + override 입력
  ExecutedResultCard.tsx   — executed 카드 (intent 별 5종 sub-view + Compare)
frontend/src/components/section3/Section3Section.tsx — MAIN_NAV 첫 번째
```

**Tests**
```
tests/simulation/
  test_simulation_agent.py — 8 e2e (StubIntentClassifier + MockOntologyClient)
```

**Docs**
```
toClaude/simulation/
  SIMULATION_AGENT_RFC.md
  SIMULATION_AGENT_DEMO.md
  SIMULATION_AGENT_HANDOFF.md (이 파일)
```

---

## multiturn 과의 관계

- multiturn nav, agents/multiturn/, components/section3/multiturn/, multiturn_router.py 모두 **그대로 보존**
- simulation 은 multiturn 의 함수·schema 를 **import 해서 thin wrap**
- 신규 추가:
  - 별도 테이블 2개 (간섭 방지)
  - 5 intent 모두 Gate III 까지 동작 (multiturn 은 simulate/impact 만 깊게)
  - compare_with_overrides (multiturn 에는 없음)
  - intent 별 차별 UI 카드 (multiturn 은 단일 GateBundleCard / GateExecuted*Card)

---

## 검증된 흐름 (5 시나리오)

| 시나리오 | query | 분류 | 최종 게이트 | 상태 |
|---|---|---|---|---|
| ① | "단중 계산 로직 바꾸면 어디 영향?" | impact | executed_impact | ✅ |
| ② | "standard 0.5 로 바꾸면?" | impact | executed_impact | ✅ |
| ③ | "thickness 액션 시뮬" | simulate | bundle → executed_simulation | ✅ |
| ④ | "edging 룰 어디 박혀있어?" | locate | executed_lookup | ✅ |
| ⑤ | "Slab 단중이 뭐야?" | explain | executed_lookup | ✅ |
| ⑥ | "신규 품종 HC600X 추가되면?" | impact 또는 hypothesis | executed | ⚠ LLM 분류 변동 |

⚠ ⑥ 은 LLM 의 분류가 `impact` 와 `hypothesis` 사이를 오감. clarify_intent 로 사용자가 직접 명시하면 hypothesis 분기 진입.

---

## 다음 작업 후보 (P1)

1. **우측 패널 ontology graph** — 현재 placeholder. xyflow + multiturn 의 caller_graph 호출로 연결.
2. **7-tab viewer** — 현재 라벨만. 각 탭마다 ontology API 응답 표 surface.
3. **fixture 인라인 편집** — BundlePreviewCard 에 표 row 별 input. 현재는 raw JSON 한 덩어리 입력.
4. **hypothesis intent 강건화** — LLM 이 "신규 X 추가" 패턴을 더 잘 잡도록 prompt 보강 또는 키워드 매처.
5. **session 목록 페이지** — 과거 turn 들 brows + reopen (현재는 URL 의 sid 로만 reopen).
6. **stream/SSE** — 현재는 REST 단순 호출. progress 가 긴 작업 (Gate II/III) 시 사용자가 무엇 기다리는지 표시 부족.

---

## 검증 요약

```bash
PYTHONPATH=. venv/bin/pytest tests/simulation/test_simulation_agent.py -q
# → 8 passed in 2.88s

cd frontend && npx tsc --noEmit
# → 0 errors
```

API smoke:
```bash
curl -X POST http://127.0.0.1:8001/api/section3/simulation/start \
  -H 'Content-Type: application/json' \
  -d '{"user_query":"thickness 액션 시뮬","repo_id":"slab-design-real-v2"}'
```

브라우저: `http://localhost:3000/?section=simulation&view=simulation`

---

## 알려진 한계

- 우측 패널이 아직 placeholder.
- intent classifier 가 OpenAI 호출이라 latency 약 1~3초.
- "신규 X 추가" 같은 hypothesis 의도가 자주 impact 로 분류됨.
- compare_runs 의 결과가 `output_value` dict 가 비어있으면 field_diffs 0건.
- session 목록 페이지 없음 — URL 의 sid 직접 접근만 가능.
