# Phase 5 — Polish (SSE server-push + next_gate_kind UI) (Summary)

**브랜치**: `section3/chat-agent-redesign`
**일자**: 2026-05-18
**완료 step**: P5a (backend SSE) / P5b (frontend SSE subscribe) / P5c (next_gate_kind hint) / P5d (verification)

Phase 1-4d 의 production wiring 위에 UX polish — 클라이언트 polling 을 server-push (SSE) 로 전환 + state machine hint surface.

---

## 1. P5a — backend SSE server-push

`backend/section3/api/multiturn_router.py` `/session/{sid}/stream` 확장:

```python
async def _events():
    MAX_TICKS = 60       # 30초 lifetime
    TICK_SEC = 0.5
    last_signature = None
    for _ in range(MAX_TICKS):
        current = p.replay_session(session_id)
        if current is None:
            yield b"event: gone\ndata: {}\n\n"; return
        sig = (len(decisions), status, user_response presence tuple)
        if sig != last_signature:
            yield f"event: snapshot\ndata: {json.dumps(snapshot)}\n\n"
            last_signature = sig
        if status == "done":
            yield b"event: done\ndata: {}\n\n"; return
        await asyncio.sleep(TICK_SEC)
    # tick budget 소진 → close → EventSource 자동 reconnect
```

**핵심 디자인**:
- 0.5초 폴링 + signature diff 시에만 새 snapshot emit (network 효율)
- session.status="done" 도달 시 즉시 done event + close
- 30초 maximum lifetime — EventSource 의 자동 reconnect 패턴 활용 (long polling 아닌 short-lived stream chain)
- session 삭제 감지 시 gone event

### Frontend ↔ Backend SSE event 종류

| event | 의미 | client 동작 |
|---|---|---|
| `snapshot` | decisions / status 변경 | state 갱신 |
| `done` | session 종료 | EventSource close, 더 이상 reconnect 안 함 |
| `gone` | session 삭제됨 | EventSource close |
| (timeout) | 30초 tick 소진 | EventSource 자동 reconnect |

test (`test_multiturn_router.py`):
- 기존 `test_stream_emits_current_snapshot` — break 첫 snapshot 후 close
- **신규** `test_stream_emits_done_when_session_complete` — Gate III impact 완료 후 SSE 가 즉시 snapshot + done event emit

---

## 2. P5b — frontend SSE subscribe

`useMultiturnSession.ts` 확장:

```tsx
useEffect(() => {
  if (!state.sessionId) return;
  if (state.session?.status === "done") {
    esRef.current?.close(); return;
  }
  const es = new EventSource(`/api/section3/multiturn/session/${sid}/stream`);
  es.addEventListener("snapshot", (ev) => {
    const data = JSON.parse(ev.data);
    setState(prev => ({...prev, decisions: data.decisions, ...}));
  });
  es.addEventListener("done", () => es.close());
  es.addEventListener("gone", () => es.close());
  return () => es.close();
}, [state.sessionId, state.session?.status]);
```

**동작**:
- sessionId 설정 → EventSource open
- snapshot event 도달 시 state.decisions / session.status 갱신
- done/gone event 시 close (자동 reconnect 안 함)
- timeout 으로 close 시 EventSource 가 자동 reconnect (브라우저 기본 동작)
- session.status="done" 또는 unmount 시 명시 close

mutation 후 `refresh()` 도 병행 — SSE 의 0.5초 latency 보완 (즉시 update).

---

## 3. P5c — next_gate_kind UI surface

`useMultiturnSession.confirm()` 이 `ConfirmResponse` 반환값 사용:
- state 에 `lastNextGateKind: string | null` 추가
- `SessionHeader` 가 status != "done" 일 때 `→ {nextGateKind}` 표시 (blue text)

UX: 사용자가 [이걸로 진행] 누르면 header 에 "→ bundle_prepared" 표시 — 다음 단계가 어떤 게 올지 명시.

---

## 4. P5d — Verification

### 4.1 tests (157 PASS)

- tests/simulation 138 (+1 SSE done test)
- tests/api/test_ontology_router 19

### 4.2 서버 검증

**SSE first snapshot (active session)**:
```
GET /session/{sid}/stream
↓ ~0.5초 안에
event: snapshot
data: {"session_id":"...", "status":"active", "decisions":[turn_1...]}
```

**SSE done event (Gate III 완료 후)**:
```
event: snapshot
event: done
(EventSource close)
```

**TypeScript clean**: 신규 useMultiturnSession.useEffect (EventSource) + MultiturnChat.SessionHeader 갱신 모두 통과.

---

## 5. 잔여 (외부 의존성)

| # | Item | 의존성 |
|---|---|---|
| ontology.db method body 시드 | modeling builder |
| ontology.db caller_graph 시드 | modeling builder |
| ontology.db entity_schemas 시드 | modeling builder |
| W74 typed-return stub 보충 | sim_v2 |
| bridge_agent.py deprecate | 사용자 동의 |
| idiom_diffs surface | sim_v2 (rewrite_method_invocation hook 변경) |

위 작업 완료 시 sec3 코드 변경 없이 자동 활용 (Phase 4d 의 점진적 swap pattern).

---

## 6. Phase 1~5 누적

| Phase | 산출물 | tests |
|---|---|---|
| 1 | 인프라 (schemas / orm / persistence / 5 endpoint) | 67 |
| 2 | Gate I+II+III(sim+impact) 모두 backend wired | 122 (+55) |
| 3 | Frontend MultiturnChat + 5 컴포넌트 | 122 (no new tests, TS clean) |
| 4 | HybridOntologyClient + next_gate_kind state machine | 137 (+15) |
| 4d | sec2 측 3 endpoint + sec3 hybrid 본체 wire (양 섹션 협업) | 156 (+19 router + 0 sim 갱신) |
| 5 | SSE server-push + next_gate_kind UI surface | 157 (+1) |

**최종 tests: 157 PASS**. Backend Gate I/II/III + Frontend 4 GateCard + sec2 ↔ sec3 통신 production wired + SSE 실시간.
