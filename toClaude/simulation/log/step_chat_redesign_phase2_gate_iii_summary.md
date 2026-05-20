# Phase 2 Gate III — Executed (Sim + Impact) (Summary)

**브랜치**: `section3/chat-agent-redesign`
**일자**: 2026-05-17
**완료 step**: 4a/4b (tests) / 4c (handlers) / 4d (/respond wire) / 4e (verification)

Phase 2 마지막 게이트. simulate / impact 두 분기 모두 wire — multiturn 의 핵심 풀 파이프라인이 production 진입.

---

## 1. Step 4c — Gate III handlers

### gate_iii_sim.py

```python
async def build_gate_iii_sim(*, bundle: GateBundle, repo_id: str) -> GateExecutedSimulation:
    function_name = _extract_function_name(bundle.python_source)
    case_dicts, fail_reason, stub_count = await asyncio.to_thread(
        _run_sim_pipeline_sync, bundle.target.action_id,
        bundle.target.code_method_fqn, repo_id,
        bundle.python_source, function_name,
    )
    results = [_to_case_result(d) for d in case_dicts]
    invariant_status = _aggregate_invariant_from_dicts(case_dicts)
    return GateExecutedSimulation(results, invariant_status, baseline_diff=None, sources)
```

Pipeline:
1. `sim_v2.load_action(target.action_id, repo_id)`
2. `sim_v2.synthesize_fixtures(action, function_name, python_source)` — W71 deterministic re-synth
3. `sim_v2.build_stubs(method_fqn, repo_id, python_source)` — W74
4. `sim_v2.run_fixtures_in_process(fixtures, stub_namespace=stubs)` — W72 invariant
5. case_dict → `CaseResult` (status: PASS/FAIL/ERROR/SKIPPED)
6. `_aggregate_invariant_from_dicts`: 모두 PASS=clean / 빈번한 FAIL 매핑 (fail_nondeterministic / fail_unexpected_throw / fail_return_type / error)

Failure mode (Q5 "빠진 대로"):
- python_source 없음 / function_name 추출 실패 / action 못 찾음 / fixture 빈 결과 → `error` payload + 0 results

test: `test_multiturn_gate_iii_sim.py` 8 PASS

### gate_iii_impact.py

```python
async def build_gate_iii_impact(*, target: ActionRef, repo_id: str, ontology_client) -> GateExecutedImpact:
    caller_result, action = await asyncio.gather(
        call_ontology_get_caller_graph(...), _load_action_async(...),
    )
    if action: diagnose_result = await call_sim_v2_quick_diagnose(action)
    findings = _diagnose_to_findings(diagnose)
    confidence = _impact_confidence(diagnose, caller_count=...)
    return GateExecutedImpact(affected_methods, sim_v2_findings=findings, confidence, sources)
```

Pipeline:
1. 병렬: `ontology.get_caller_graph` + `sim_v2.load_action`
2. action 있으면 `sim_v2.quick_diagnose_action` 호출
3. `_diagnose_to_findings`: dict → Finding list
   - ok+fixtures>0: Finding(info, "quick_diagnose_passing", "N/M fixtures pass · K stubs")
   - blocked: Finding(warn/error, "quick_diagnose_blocked", primary_failure) + Finding(warn, "primary_failure", ...)
4. `_impact_confidence`:
   - ok+fixtures: 0.8 + 0.2 * (passing/fixtures)
   - blocked + callers: 0.4
   - blocked: 0.2
   - action 없음: 0.3

test: `test_multiturn_gate_iii_impact.py` 8 PASS

---

## 2. Step 4d — /respond wire

```python
if session.status == "done":
    raise 501 ("session 이미 완료")

if next_turn == 3:
    intent = decisions[-1].payload["intent"]
    if intent == "ambiguous": raise 422
    if intent == "impact":
        target_ref = _resolve_gate_ii_target(...)
        executed = await build_gate_iii_impact(target_ref, ...)
        add_gate_decision(turn=3, executed.model_dump())
        update_session_status("done")
        return executed
    # simulate → Gate II (기존)

if next_turn == 4:
    bundle = TypeAdapter(GateBundle).validate_python(decisions[-1].payload)
    executed = await build_gate_iii_sim(bundle, repo_id)
    add_gate_decision(turn=4, executed.model_dump())
    update_session_status("done")
    return executed
```

State machine (spec v2 §2 완전 구현):
```
simulate path:  turn 1 (stub) → turn 2 (Gate I) → turn 3 (Gate II) → turn 4 (Gate III sim) → done
impact path:    turn 1 (stub) → turn 2 (Gate I) → turn 3 (Gate III impact) → done
ambiguous:      turn 3 = 422 (재분류 필요)
```

`update_session_status("done")` 호출로 Gate III 완료 후 추가 /respond 는 501.

---

## 3. Step 4e — Verification

### 3.1 자동 검증 (tests/simulation 122 PASS)

| 파일 | tests |
|---|---|
| test_multiturn_schemas | 15 |
| test_multiturn_persistence | 13 |
| test_multiturn_ontology_client | 11 |
| test_multiturn_tools | 5 |
| **test_multiturn_router** | **23** (20 → 23) |
| test_multiturn_intent | 10 |
| test_multiturn_gate_i | 11 |
| test_multiturn_gate_ii | 7 |
| **test_multiturn_gate_iii_sim** | **8 신규** |
| **test_multiturn_gate_iii_impact** | **8 신규** |
| test_sim_v2_bridge | 13 |

**총 122 PASS** (105 → 122, +17)

### 3.2 서버 검증 (port 8001, 실 OpenAI + 실 sim_v2)

**Simulate path (turn 1→4)**:
```
"주문 검증 시뮬해줘"
→ turn 1 ambiguous stub
→ turn 2 intent=simulate · top=정합성_검증
→ confirm selected_index=0
→ turn 3 bundle_prepared (java 431 chars, python 400 chars, 1 fixture)
→ turn 4 executed_simulation:
   invariant_status: error · 1 ERROR result (W74 stub 데이터 부재, Q5 "빠진 대로")
   sources: ['sim_v2']
   session.status: done · turn count: 4
```

**Impact path (turn 1→3)**:
```
"cumulativeProductivity 바꾸면 어디 영향?"
→ turn 1 ambiguous stub
→ turn 2 intent=impact · 1 candidate (cumulativeProductivity)
→ confirm selected_index=0
→ turn 3 executed_impact:
   affected_methods: 0 (sec2 API 부재, SimV2BackedOntologyClient 의 빈 결과)
   findings: 1 — quick_diagnose_passing "12/12 fixtures pass · 3 stubs"
   confidence: 1.0
   sources: ['ontology', 'sim_v2']
   session.status: done · turn count: 3
```

**Edge cases**:
- session.status="done" 후 /respond → **501** ("session 이미 완료") ✓
- turn 3 + ambiguous → 422 ✓
- turn 3 + no confirm → 422 ✓
- turn 3 + selected_index 범위 밖 → 422 ✓

---

## 4. 다음 진입점 (Phase 2 마무리)

| # | Item | Status |
|---|---|---|
| Gate I (intent + candidates) | ✅ |
| Gate II (java + python + fixtures bundle) | ✅ |
| Gate III sim (run_fixtures + invariant) | ✅ |
| Gate III impact (caller_graph + diagnose) | ✅ |
| `confirm.next_gate_kind` 계산 | (간이 done/501) |
| Frontend MultiturnChat + GateCard + ProvenanceBadge | TBD (Phase 3) |

state machine 의 `next_gate_kind` 계산은 현재 단순 — confirm response 는 항상 `next_gate_kind=None`. UI 는 /respond 의 결과 payload 의 `kind` 로 자체 판단. 더 정교한 state machine 은 frontend 단에서 가능.

---

## 5. Q5 비전 (영향도 + 시뮬 두 흐름) 완성

사용자 자유 의견의 정확한 실현:

> "최종적으로 자연어 기반 영향도 검토 + 파이썬 코드 시뮬레이션이 자연어 인터뷰
> 및 UI기능 기반으로 시작해서 동작할 수 있도록 해야해. 그 재료는 섹션2에서 만든
> 온톨로지 및 코드 매핑이 기반이 되어야하고, 둘의 통신은 api로 하고. 최종적으로
> 사용자는 에이전트와 대화하면서 빠진내용은 빠진대로, 실제 작성된 온톨로지 기반의
> 추론 및 검토를 편하고 확실한 근거를 보면서 진행할 수 있어야해"

- **자연어 → intent 분류** (Gate I) — simulate / impact 자동
- **영향도 검토 흐름** (impact path) — 3 turns: 자연어 → 후보 confirm → caller_graph + 진단
- **시뮬레이션 흐름** (simulate path) — 4 turns: 자연어 → 후보 confirm → bundle → 실행 결과
- **온톨로지 기반** — sim_v2 가 ontology.db 의 actions / code_methods / business_terms 로 모든 단계 backed
- **API 통신** — OntologyClient Protocol 5 endpoint (Phase 1~3 = SimV2Backed mock, Phase 4 = HTTPOntologyClient swap)
- **"빠진 내용은 빠진대로"** — 모든 게이트가 부분 실패 시에도 surface (entity_schema 부재 / W74 stub 부족 / caller_graph 부재 모두 정상 동작)
- **"확실한 근거"** — 모든 payload 가 `sources: list[Provenance]` (source / detail / confidence)

Section 3 멀티턴 agent 의 **Phase 2 production wiring 완료**.
