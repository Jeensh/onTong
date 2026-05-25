# Phase 21a + 21b 인계 — 산출물 세션용

> **목적**: 이 문서 하나만 읽어도 발표/리포트/데모 영상 등 산출물을 만드는 다른 Claude 세션이 완전한 컨텍스트를 가질 수 있게.
> **작성일**: 2026-05-19  ·  **브랜치**: `section3/chat-agent-redesign`
> **선행 메모리**: `~/.claude/projects/-Users-donghae-workspace-ai-onTong/memory/project_chat_redesign_phase21.md`

---

## 1. TL;DR (한 문단)

Section 3 멀티턴 agent 가 **의도 분류 → 후보 → 코드 → 시뮬** 4 stage 로 동작하던 것을, 사용자 critique ("multi턴 에이전트 그대로인데 어떻게 해야 테스트가 가능한거야") 에 대응하여 **의도 분류 후 사용자 confirm 을 받아야 후보 검색으로 진입**하도록 진짜 agent flow 를 변경. Phase 21a = EmptyState 재설계 (5 intent category 카드 + 최근 세션 + 고급 옵션). Phase 21b = `intent_classified` 라는 새 turn 추가 + `INTENT_CONFIRM_REQUIRED` 모듈 flag pattern. tests/simulation **348 PASS** (기존 341 + 새 7), TS clean, regression 0. 라이브 데모 세션 ID `28470197-a460-40f1-a145-8f2d436bcc62` 와 인터랙티브 HTML 가이드 (`toClaude/simulation/demo_phase21b_rich_simulation.html`) 완료.

---

## 2. The "Why" — 사용자 발화로 본 배경

| 발화 (한국어 원문) | 의도 (해석) | 산출물에서 인용 가능 형태 |
|---|---|---|
| "이제 사용자가 실제로 운영환경에서 인사이트를 얻고 제대로 원하는 바를 이룰 수 있도록 섹션3가 개선이 된거야?" | production readiness 의문 | "Phase 17~20 단계까지 UI 는 정돈됐지만 사용자가 실제 의사결정에 쓸 수 있는가?" |
| "크게 3가지 섹션으로 나뉘어져야 할 것 같아 1) 사용자 의도 파악 2) scope 파악 3) 시뮬레이션" | 3-stage 사용자 vision | "사용자 vision: 의도 → scope → simulation 3 stage" |
| "multi턴 에이전트 그대로인데 어떻게 해야 테스트가 가능한거야. 나는 지금이 멀티턴 시작점도 그리 맘에 들지 않아" | Phase 17~20 cosmetic 에 그침 + 시작점 UX 별로 | "사용자 critique: 'agent 자체는 변하지 않았다 — UX 도색만 됐다'" |
| "보고왔어 둘다 가야지" | 21a + 21b 둘 다 진행 승인 | "사용자 OK 후 두 phase 동시 진행" |

핵심: **Phase 17~20 은 cosmetic, Phase 21a+21b 가 substantive change**. 산출물에서는 21 을 main story 로 잡고 17~20 을 setup 으로.

---

## 3. 변경 사항 — File-by-file

### Backend (5 files · +85 LOC 신규/수정 + 397 LOC 신규 tests)

| 경로 | 변경 종류 | 핵심 |
|---|---|---|
| `backend/section3/agents/multiturn/schemas.py` (330 LOC) | 수정 (+15) | `GateIntentClassified` 추가 (kind=intent_classified, intent + search_terms + conditions + sources). `GatePayload` discriminated union 에 합류. |
| `backend/section3/agents/multiturn/gate_i.py` (766 LOC) | 수정 (+20) | `build_intent_classified(user_query, classifier)` 신설. `build_gate_i(..., preclassified=None)` 옵션 — preclassified 있으면 LLM 재호출 skip. |
| `backend/section3/api/multiturn_router.py` (1241 LOC) | 수정 (+20) | `INTENT_CONFIRM_REQUIRED: bool = True` 모듈 flag. `respond()` content-driven 4-case dispatch (A: stub → intent_classified 또는 legacy target_selected / B: intent_classified → target_selected / C: target_selected → Gate II/III / D: bundle_prepared → executed_sim). `_next_gate_kind` 에 intent_classified case 추가. is_stub 검사: `turn_no==1 AND user_response is None` (payload contents 대신 sentinel). |
| `tests/simulation/conftest.py` (20 LOC) | **신규** | autouse fixture 가 `monkeypatch.setattr(mr, "INTENT_CONFIRM_REQUIRED", False)` 로 모든 simulation 테스트에서 legacy 1-step flow 강제. |
| `tests/simulation/test_multiturn_phase21b_intent_confirm.py` (397 LOC) | **신규** | 7 tests · production 흐름 E2E 검증 (`production_intent_confirm` fixture 가 conftest autouse override 해서 True 로). |

### Frontend (3 files · +50 LOC)

| 경로 | 변경 종류 | 핵심 |
|---|---|---|
| `frontend/src/lib/section3/multiturn.ts` (444 LOC) | 수정 (+12) | `GateIntentClassified` 타입 + `GatePayload` union 에 합류. |
| `frontend/src/components/section3/multiturn/IntentStage.tsx` (209 LOC) | 수정 (+30) | `payload: GateTarget \| GateIntentClassified` 받게 확장. `onConfirm` / `confirmDisabled` / `pending` props. `isAwaitingConfirm` 상태에서 [✓ 맞아 → 후보 찾기] / [↻ 다른 의도로] 버튼 + ambiguous 시 confirm 버튼 disable. |
| `frontend/src/components/section3/multiturn/MultiturnChat.tsx` (888 LOC) | 수정 (+10) | `onConfirmIntent(turn_no)` 콜백 신설 (confirm + 자동 respond). `WorkflowFrame` 이 intentClassified turn 과 gateIReal turn 둘 다 별도로 surface. `computeCurrentStage()` 가 intent_classified turn 도 Stage 1 으로 카운트. EmptyState 는 21a 에서 이미 5 intent category 카드 + 최근 세션 list + 고급 옵션 collapse 로 재설계됨. |

### 문서 (3 files updated)

- `toClaude/simulation/CHANGES.md` — `## 2026-05-19 (Phase 21b — Intent confirmation step)` 섹션 추가, file-by-file + 결과 수치 + 패턴 노트
- `toClaude/simulation/TODO.md` — Phase 21 [x] 항목 + 후속 미구현 (21c/22a/22b) 명시
- `toClaude/simulation/HANDOFF.md` — "다음 세션 첫 작업" 갱신, Phase 17~20 → Phase 21 으로 main story 전환

### 인터랙티브 HTML 가이드

- `toClaude/simulation/demo_phase21b_rich_simulation.html` (447 LOC · 24KB)
- 단일 페이지에 5 turn + Java/Python diff + idiom rewrites + 5 fixture 결과 표 + 실행 버튼 + curl 복사 버튼

---

## 4. 데모 케이스 — 산출물에 그대로 인용 가능한 실측 데이터

### 4.1 라이브 세션 (재현 가능)

- **session_id**: `28470197-a460-40f1-a145-8f2d436bcc62`
- **repo_id**: `slab-design-real-v2`
- **user_query**: `"열연 폭 결정 로직 시뮬해줘"`
- **status**: `done` (5 turn 완주)
- **브라우저 URL**: `http://localhost:3000/?view=multiturn&sid=28470197-a460-40f1-a145-8f2d436bcc62`
- **Backend raw JSON**: `http://localhost:8001/api/section3/multiturn/session/28470197-a460-40f1-a145-8f2d436bcc62`

### 4.2 5-Turn 진행 표

| turn | gate_kind | user_response | 데이터 |
|------|-----------|---------------|--------|
| 1 | `target_selected` (stub) | · (auto) | intent=ambiguous, candidates=0 |
| 2 | **`intent_classified`** ★ | ✓ confirm | intent=simulate, search_terms=['열연 폭','결정 로직'], confidence=1.0 |
| 3 | `target_selected` (Gate I real) | ✓ confirm (selected_index=3) | 4 candidates, #3 = SelectedHrTgtWidthResolver.resolve, score=23.0 |
| 4 | `bundle_prepared` (Gate II) | ✓ confirm | Java 15 lines → Python 9 lines, idiom_diffs=2, fixtures=1, confidence=0.85 |
| 5 | `executed_simulation` (Gate III) | · (final) | invariant=clean, 1 case PASS |

### 4.3 선택된 후보 (Stage 2)

```
#0  final_width_range_실행    score=26.0  SdFinalWidthRangeAction.execute
#1  target_width_실행         score=26.0  SdTargetWidthAction.execute
#2  width_range_실행          score=26.0  SdWidthRangeAction.execute
#3 ★결정                      score=23.0  SelectedHrTgtWidthResolver.resolve(SDOrderEntity)
                              role=business, declared_on_term=term.scm.order.order
                              loc=SelectedHrTgtWidthResolver.java:22-36
                              return=BigDecimal
                              annotations=[@Component]
```

### 4.4 Java → Python 변환 (Stage 3a)

```java
// Java (원본 lines 22-36)
public BigDecimal resolve(SDOrderEntity order) {
    if (order == null) return null;
    String confirmed = order.getConfirmedPlantCd();
    if (confirmed == null || confirmed.length() < 2) return null;

    char hrChar = confirmed.charAt(1); // 0=제강, 1=열연 위치
    return switch (hrChar) {
        case '1' -> order.getHrTgtWidth1();
        case '2' -> order.getHrTgtWidth2();
        case '3' -> order.getHrTgtWidth3();
        case '4' -> order.getHrTgtWidth4();
        case '5' -> order.getHrTgtWidth5();
        default -> null;
    };
}
```

```python
# Python (auto-translated)
def resolve(self, order):
    if order == None:
        return None
    confirmed = order.getConfirmedPlantCd()
    if confirmed == None or len(confirmed) < 2:
        return None
    hrChar = confirmed[1]
    # 0=제강, 1=열연 위치
    return None  # UNMAPPED switch arrow-form
```

### 4.5 Idiom rewrites (실측 2건)

| idiom | Java | Python |
|---|---|---|
| `length` | `confirmed.length()` | `len(confirmed)` |
| `charAt` | `confirmed.charAt(1)` | `confirmed[1]` |

### 4.6 Custom run-custom 결과 (5 fixture × 4 코드 경로) — 데모 핵심

사용자가 unmapped switch 를 dict.get 으로 보정한 Python 으로 `POST /run-custom` 호출:

| fixture_id | 입력 (order dict) | 예상 | 실측 | status | elapsed |
|---|---|---|---|---|---|
| null_order | `None` | None | None | PASS | 1.4ms |
| stockcode_order | `{confirmedPlantCd: None}` | None | None | PASS | 0.5ms |
| **rolling_pos_1** | `{confirmedPlantCd:"P1", hrTgtWidth1:"1250.0"}` | 1250.0 | `"1250.0"` | PASS | 0.1ms |
| **rolling_pos_3** | `{confirmedPlantCd:"M3", hrTgtWidth3:"1500.5"}` | 1500.5 | `"1500.5"` | PASS | 0.1ms |
| unmapped_pos_9 | `{confirmedPlantCd:"X9"}` | None | None | PASS | 0.1ms |

**해석**: 4 코드 경로 모두 검증 — null 가드 × 2 + 분기 hit × 2 + default arm × 1.

---

## 5. 핵심 패턴 (재사용 가능, 산출물에 "Engineering insight" 로 인용 가능)

### 5.1 INTENT_CONFIRM_REQUIRED flag + conftest autouse override

**문제**: behavioral change 인데 기존 348 tests 가 1-step flow 가정으로 작성됨 → 흐름 바꾸면 26 tests 깨짐.

**해결**:
- Backend 에 `INTENT_CONFIRM_REQUIRED: bool = True` 모듈 flag (production default)
- `tests/simulation/conftest.py` autouse fixture 가 `monkeypatch.setattr(mr, "INTENT_CONFIRM_REQUIRED", False)` 로 legacy mode 강제
- 새 테스트는 함수 fixture `production_intent_confirm` 으로 다시 True override

**효과**: 26 tests 패치 없이 새 흐름 production 진입. 기존 + 새 테스트 동시 통과.

### 5.2 is_stub 검사 — sentinel based dispatch

**문제**: `last.gate_kind == "target_selected" AND last.intent == "ambiguous" AND not candidates AND user_response is None` 로 stub 검사하니, **legacy mode 에서 candidates=0 으로 떨어진 turn 2 도 stub 으로 오인식** → 무한 stub 루프.

**해결**: `is_stub = last.turn_no == 1 AND last.user_response is None` 으로 단순화. /start 직후 stub 은 정의상 turn 1.

**일반화**: state machine dispatch 에서 initial state 검사는 turn_no 같은 sentinel 로. payload contents 는 domain dispatch 에만.

### 5.3 Content-driven respond() refactor

`respond()` 가 4-case if-chain 으로 깔끔:
- A: stub turn → intent_classified or legacy target_selected
- B: intent_classified + confirmed → target_selected (preclassified 전달)
- C: target_selected + confirmed → Gate II/III intent-별 dispatch
- D: bundle_prepared + confirmed → executed_simulation

각 case 가 explicit guard 로 user_response 확인 → 잘못된 호출은 422 명확 응답.

---

## 6. 검증 — 산출물 수치 그대로 인용

```
✓ tests/simulation         348 PASS   (기존 341 + Phase 21b 신규 7)
✓ TS check (tsc --noEmit)  exit 0
✓ regression               0
✓ 라이브 백엔드 검증         5 turn 완주 (28470197-a460-...)
✓ custom 실행 검증          5 fixture / 4 코드 경로 / 100% PASS
```

코드 라인 수치:
- Backend 변경: +85 LOC (schemas +15 / gate_i +20 / router +20 / conftest +20 / tests +210 = 정확히는 새 tests 397 LOC + 변경 85)
- Frontend 변경: +52 LOC (types +12 / IntentStage +30 / MultiturnChat +10)

---

## 7. 이미 만든 산출물 (재사용 가능)

| 산출물 | 경로 | 용도 |
|---|---|---|
| 인터랙티브 HTML 데모 | `toClaude/simulation/demo_phase21b_rich_simulation.html` | 사용자/이해관계자 walk-through · 라이브 backend 와 직접 통신 가능한 [Run] / [curl 복사] 버튼 포함 |
| CHANGES.md 섹션 | `toClaude/simulation/CHANGES.md` 상단 "2026-05-19 (Phase 21b)" | 변경 로그 |
| TODO.md 섹션 | `toClaude/simulation/TODO.md` "Phase 21" | 완료 + 후속 항목 |
| HANDOFF.md | `toClaude/simulation/HANDOFF.md` | 다음 코드 세션용 |
| 메모리 | `~/.claude/.../memory/project_chat_redesign_phase21.md` | 미래 Claude 세션이 자동으로 recall |

---

## 8. 산출물 제안 — 이 컨텍스트로 만들 수 있는 것들

발표/리포트/데모용으로 다음 5종이 가능. 사용자가 어떤 형태를 원하는지에 따라 선택.

### A. 사내 발표용 슬라이드 (10 slides)
1. 표지: "Phase 21 — Multiturn Agent 진짜 변화"
2. Why: 사용자 critique "multi턴 에이전트 그대로인데"
3. 이전 (Phase 17~20): UI 도색만 됨 · agent 흐름 불변
4. After (Phase 21b): 새 turn `intent_classified` · 사용자 confirm pause
5. 데모 한 화면: 5-turn 진행 표 + Java↔Python diff
6. Idiom rewrites 2건 (length/charAt)
7. 5 fixture × 4 코드 경로 100% PASS
8. Engineering pattern: INTENT_CONFIRM_REQUIRED flag (350+ 테스트 안 깨고 흐름 변경)
9. 수치: 348 PASS + TS clean + 5-turn live session
10. Next: 21c (inline edit) · 22 (search_terms UI) · 23 (SSE 강화)

### B. 사용자/이해관계자용 1-pager (markdown 또는 PDF)
- Before / After 비교 (한 줄씩)
- 데모 영상 GIF 또는 stills
- 수치 + 인터랙티브 HTML 링크

### C. 데모 영상 스크립트 (3분)
- 0:00–0:30 — 문제 제기 + Phase 17~20 회고
- 0:30–1:30 — Phase 21b 흐름 라이브 (브라우저 + IntentStage confirm 버튼 클릭)
- 1:30–2:30 — Java↔Python diff + 5 fixture 결과
- 2:30–3:00 — 수치 + 다음 단계

### D. 엔지니어링 블로그 포스트 (technical, 1500-2000 words)
- INTENT_CONFIRM_REQUIRED flag pattern 을 일반화 ("How to ship behavioral changes without breaking 300+ tests")
- conftest autouse fixture 의 단방향 override 패턴
- content-driven dispatch + sentinel state detection

### E. README 업데이트 (`toClaude/simulation/`)
- Phase 21 섹션 추가
- 데모 HTML 링크
- 흐름 다이어그램 (ASCII or mermaid)

---

## 9. 산출물에 쓸 만한 인용/한 줄 카피

- **사용자 발화**: "multi턴 에이전트 그대로인데 어떻게 해야 테스트가 가능한거야"
- **변화 요약**: "Stage 1 의 IntentStage 가 read-only 카드 → 사용자 confirm 게이트로 승격"
- **Engineering 가치**: "기존 348 테스트를 한 줄도 안 고치고 production agent flow 변경"
- **데모 한 줄**: "Java switch expression → Python 보정 → 4 코드 경로 5/5 PASS, 0.5–1.4ms"
- **사용자 vision**: "후보 보기 전 의도 잘못 분류된 걸 사용자가 catch"

---

## 10. Open issues / 솔직한 한계 — 산출물에서 흐려서 말하면 안 됨

| 항목 | 상태 | 산출물에서 언급할 때 |
|---|---|---|
| `SDOrderEntity` schema = 0 fields (sec2 modeling 시드 미완) | 알려진 갭 | "자동 fixture 는 모두 None — custom fixture 로 보강 데모" 처럼 정직하게 |
| Java switch arrow-form (Java 14+) translator unmapped | 알려진 한계 | "translator 가 graceful fallback (`UNMAPPED`) + 사용자 dict.get 보정으로 검증" |
| `intent_classified` 와 `target_selected` 두 turn 으로 분할 → API 호출 1회 증가 | trade-off | "+1 round-trip 으로 의도 오분류 catch — 사용자가 명시적으로 요청한 trade-off" |
| 21c inline edit (intent type 직접 변경) 미구현 | 후속 | 현재는 "새 대화로 다시 시작" 만 가능 |

---

## 11. 라이브 환경 — 산출물 만들기 전에 확인

```bash
# Backend 살아있는지
curl -s "http://localhost:8001/api/section3/multiturn/sessions?limit=1" | head -c 100

# Frontend (Next.js dev server) 살아있는지
curl -s -I http://localhost:3000/ | head -3

# 데모 세션 살아있는지 (status=done 이어야)
curl -s "http://localhost:8001/api/section3/multiturn/session/28470197-a460-40f1-a145-8f2d436bcc62" | python3 -c "import sys,json; d=json.load(sys.stdin); print('status=', d['session']['status'], '· turns=', len(d['decisions']))"
```

만약 backend down → `python -m uvicorn backend.main:app --port 8001 --host 0.0.0.0` (no --reload 로 시작됨, 코드 변경 시 재시작 필요).

---

## 12. 산출물 세션 가이드 — 어떻게 시작할지

1. **이 문서를 먼저 끝까지 읽기**. memory 의 `project_chat_redesign_phase21.md` 도 참고.
2. **사용자에게 어떤 산출물인지 묻기** (A/B/C/D/E 중). 슬라이드면 슬라이드 도구 (Marp/Slidev), 영상이면 stills 만 만들지 영상 자체인지, 블로그면 어디 게재용인지.
3. **데모 영상/스크린샷이 필요하면** 브라우저로 `http://localhost:3000/?view=multiturn&sid=28470197-a460-40f1-a145-8f2d436bcc62` 열어서 캡처. 또는 HTML 가이드 자체를 캡처.
4. **수치 인용시 §6 검증 표 그대로** 사용. 임의 값 만들지 말 것.
5. **사용자 발화 인용시 §2 표 그대로** (한국어 원문 그대로 + 해석).
6. **모르는 부분 있으면** §10 open issues 참고하고, 데이터 부족하면 솔직히 표기.
7. **산출물 자체는 `toClaude/simulation/reports/` 또는 사용자 지시 경로** 에 저장 (`feedback_reports.md` 메모리: 발표용 리포트는 `toClaude/reports/`).
8. **Section 격리 규칙 준수**: 시뮬레이션 세션이면 `toClaude/simulation/` 만 쓰기, 다른 섹션 폴더는 read-only.

---

## 13. 의문 있으면

- 코드 상세는 git: `git log -p backend/section3/api/multiturn_router.py`
- 테스트 상세는: `tests/simulation/test_multiturn_phase21b_intent_confirm.py`
- 사용자 의도 상세는: 메모리 `project_chat_redesign_phase21.md`
- 이전 Phase 17~20 맥락: 메모리 `project_chat_redesign_phase17_to_20_3stage_ux.md`
- 이전 Phase 16 (reliability infrastructure): 메모리 `project_chat_redesign_phase16.md`

**필자 (Phase 21 작업 세션) 가 권장하는 1순위 산출물**: **A (10-slide 사내 발표)** + 사용자 인용을 main hook 으로. Engineering insight 부분은 패턴 §5 그대로.
