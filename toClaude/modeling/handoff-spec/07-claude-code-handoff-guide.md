# 07 — Claude Code 사용 가이드 (인수자용)

> **누구를 위한 문서**: 본 repo 를 git pull 받아 **Claude Code 로 Section 3 (simulation) 을 빌드할 다음 개발자**.
>
> **읽기 시점**: pull 직후. Claude Code 첫 prompt 입력 전.
>
> **목표**: Claude Code 가 본 인계 패키지의 제약 / 프로토콜 / 세션 격리 규칙을 정확히 따르도록 첫 conversation 부터 안내.

---

## 0. 30초 요약

본 repo 는 **3 개 섹션이 동시에 굴러가는 멀티 세션 프로젝트**다:

| 섹션 | 담당 | 쓰기 영역 |
|---|---|---|
| Section 1 | wiki | `toClaude/wiki/` + `backend/api/wiki.py` 등 |
| Section 2 | modeling (인계자) | `toClaude/modeling/` + `backend/modeling/` |
| **Section 3** | **simulation (= 당신)** | `toClaude/simulation/` + `backend/simulation/` + `backend/shared/contracts/simulation.py` |

당신은 Section 3 = **simulation** 세션. 다른 영역은 **read-only 참조만** 가능, 쓰기 절대 금지. 본 가이드 + `06-developer-onboarding.md` 가 당신의 entry point.

---

## 1. Claude Code 첫 conversation — copy-paste 시작

Claude Code 를 onTong 루트 (`cd /path/to/onTong`) 에서 실행. 첫 메시지로:

```
나는 onTong 의 Section 3 (simulation) 세션 담당이다.

먼저 다음을 순서대로 해줘:
1. CLAUDE.md 의 Section Isolation Rule + Step Completion Protocol + Ad-hoc Change Protocol 을 읽고 본 세션이 simulation 영역임을 명심해라.
2. toClaude/modeling/handoff-spec/07-claude-code-handoff-guide.md (= 본 문서) 를 읽어라. 본 문서는 "다음 개발자 = 당신" 을 위한 Claude Code 사용 가이드다.
3. toClaude/modeling/handoff-spec/06-developer-onboarding.md 의 STEP 1 (Repo orientation) 과 STEP 2 (환경 setup + 인계 검증) 를 실행해 인계 시점 상태를 확인해라.
4. 검증 9 항목 모두 ✅ 면 "인계 검증 통과 — STEP 3 진입 준비 완료" 라고 보고하고 멈춰라.

진행 중 의문이 생기면 사용자에게 물어봐라 — 작업 단위마다 승인 받는다.
```

이 첫 prompt 만으로 Claude Code 가:
- ✅ Section Isolation 인지
- ✅ Step Completion Protocol 인지
- ✅ 인계 패키지 읽음
- ✅ 인계 검증 자동 실행
- ✅ STEP 3 진입 전 멈춤 (작업 승인 절차)

상태로 들어감.

---

## 2. Section Isolation Rule — 당신 영역의 정확한 경계

CLAUDE.md 의 "Section Isolation Rule (Strict)" 의 simulation 세션 적용:

### 2.1 ✅ 쓰기 가능 (당신의 영역)

```
toClaude/simulation/                       ← 신설 필요. HANDOFF.md / TODO.md / CHANGES.md / demo_guide.md 등.
backend/simulation/                        ← 신설 필요 (06 STEP 3.0 의 mkdir).
  ├─ api/router.py                         ← /api/simulation/* router
  ├─ api/run_handle.py                     ← run lifecycle
  ├─ runner/python_generator.py            ← spec 05 §1
  ├─ runner/java_sandbox.py                ← spec 05 §2
  ├─ runner/lookup_source.py               ← spec 05 §3
  ├─ runner/orchestrator.py                ← spec 05 §4.5
  └─ ...
backend/shared/contracts/simulation.py     ← 신설 — ChangeSpec / SimResult / BREvidence 등 spec 04 schema
backend/main.py                            ← 단, line 67 + line 453 부근 2 줄만 추가 (06 STEP 3.2 참조). 기타 변경 절대 금지.
tests/simulation/*                         ← 신설 — TDD 권장 (CLAUDE.md 의 Smart TDD Rule)
scripts/sim_*.py                           ← 신설 OK — simulation 관련 운영 스크립트
```

### 2.2 ❌ 쓰기 절대 금지 (다른 세션 영역)

```
toClaude/wiki/                             ← Section 1 영역
toClaude/modeling/                         ← Section 2 영역 (인계자 영역, read-only 참조만)
toClaude/_shared/                          ← 사용자 명시 승인 시만 수정
backend/api/                               ← Section 1 (wiki) router
backend/application/                       ← Section 1 + Agent registry
backend/modeling/                          ← Section 2 영역 (read-only 참조만)
backend/shared/contracts/ontology_query.py ← Section 2 가 정의, 당신은 import 만
data/ontology.db                           ← read-only — 인계 시점 ground truth. 시뮬 결과를 다른 DB 에 저장하든지, 시뮬 전용 테이블을 별도로 추가.
data/wiki/                                 ← Section 1 영역
frontend/                                  ← UI 변경은 modeling 세션 책임. simulation 시각화 UI 가 필요하면 사용자 합의 후 modeling 세션에 이관.
```

### 2.3 ✅ Read-only 참조 (의존)

```
backend/modeling/api/ontology_query.py     ← OntologyQueryClientImpl Python facade — import 가능 (DTO + facade 만)
backend/shared/contracts/ontology_query.py ← TermDTO / ActionDTO / CallSiteDTO 등 — import 가능
http://localhost:8001/api/ontology/*       ← REST 호출 가능 (process 분리도 OK)
toClaude/modeling/                         ← 6 spec doc + design-gaps + archive 모두 참조 OK
```

### 2.4 ❌ 절대 직접 import 금지 (CI 차단)

```
backend.modeling.mapping_layer.*           ← internal layer
backend.modeling.domain_layer.*            ← internal layer
backend.modeling.code_layer.*              ← internal layer
backend.modeling.persistence.*             ← internal layer
```

→ 위는 `tools/check_agent_isolation.py` 가 정적 검사로 차단. CI 에 박아두면 사고 방지.

위반 시 Claude Code 는 사용자에게 즉시 알리고 작업 중단. 우회 시도 ❌.

---

## 3. Step Completion Protocol — 코드 작성 = 절반

CLAUDE.md 의 "Step Completion Protocol (Strict)" 7 항목. simulation 세션 적용 예:

### 3.1 한 step (예: "ChangeSpec / SimResult Pydantic 모델 정의") 완료 = 다음 7 항목 모두 끝

1. **Code 구현** — `backend/shared/contracts/simulation.py` 작성
2. **검증** — `tests/simulation/test_changespec_schema.py` (TDD 권장 — 본 step 시작 전 작성) ALL PASS
3. **`toClaude/simulation/log/step_<id>_summary.md`** — 본 step 요약 → 끝나면 `toClaude/simulation/archive/`
4. **`toClaude/simulation/demo_guide.md`** — 본 step 의 데모 시나리오 + troubleshooting append
5. **`toClaude/simulation/TODO.md`** — `[x]` 처리
6. **Memory `project_status.md`** — 현 단계 + 다음 단계 갱신 (`~/.claude/projects/.../memory/`)
7. **사용자 보고 + 멈춤** — 다음 step 으로 자동 진행 ❌. 사용자 승인 후만 진행.

코드 끝 = step 끝 ❌. 7 항목 다 = step 끝 ✅.

### 3.2 Ad-hoc Change Protocol (작업 중간 사용자 추가 요청)

**한 turn 안에서** 다음 4 항목 모두 갱신:

1. `toClaude/simulation/TODO.md` — 새 task row 추가
2. `toClaude/simulation/CHANGES.md` — `[x]` (즉시 처리) 또는 `[ ]` (보류) 로 기록
3. `toClaude/simulation/demo_guide.md` — 사용자 가시 변경이면 시나리오 추가
4. Memory `project_status.md` — 중요한 변경이면 갱신

코드만 바꾸고 doc 미반영 ❌. 동기화 끝까지 한 번에.

---

## 4. Smart TDD Rule — 새 백엔드 로직은 테스트 먼저

CLAUDE.md 의 "Smart TDD Rule (Backend)" 적용:

새 backend 로직 / API endpoint / Agent tool 작성 시:

1. **`CHECKLIST.md` 의 해당 섹션을 읽어라** — `toClaude/simulation/CHECKLIST.md` (신설 필요. modeling 세션의 `toClaude/modeling/CHECKLIST.md` 가 template).
2. **앱 코드 전에 `tests/simulation/test_<feature>.py` 자동 테스트 스크립트 작성**
3. **앱 코드 작성**
4. **테스트 ALL PASS** 후만 TODO `[x]`

**예외**: 단순 UI / CSS-only 변경 (simulation 영역에는 거의 없음). 백엔드 로직은 항상 TDD.

---

## 5. Pre-Demo Verification Protocol — pytest 통과 ≠ 정상

사용자 데모 직전:

1. **`bash toClaude/_shared/verify.sh` 실행** — pytest + tsc + API + 채팅 + 충돌 체크 자동 검증
2. **해당 기능 체크리스트 직접 실행** — `toClaude/simulation/CHECKLIST.md` 의 curl 명령
3. **Edge case 테스트** — 빈 입력, 단일 결과, 다수 결과, 큰 fixture 등
4. **증거 기반 보고** — 추정 ❌. 실 응답 / 로그 첨부.

특히 다음에는 반드시:
- SSE 이벤트 추가/변경 → 실 SSE 으로 시퀀스 확인
- 시뮬 결과 변경 → 실 ChangeSpec 으로 end-to-end 통과 확인

---

## 6. Session Start Protocol — 세션 이어서 시작 시

다음 세션에서 "이어서 하자" 라고 사용자가 말하면 Claude Code 는:

1. **담당 섹션 확인** — simulation 세션이면 진행, 다른 세션이면 사용자에게 확인
2. **`toClaude/simulation/HANDOFF.md` 읽기** — 다음 작업 + 환경 설정
3. **`toClaude/simulation/CHANGES.md` 의 `[ ]` 항목 확인** — 미처리 추가 요청
4. **미처리 추가 요청 먼저 처리**
5. **`toClaude/simulation/TODO.md` 의 다음 incomplete step 부터 재개**

→ 따라서 세션 종료 직전 / 큰 작업 단위 직후 **HANDOFF.md 갱신은 의무**.

---

## 7. Memory Bootstrap — Claude Code 의 영구 메모리에 simulation 영역 표시

Claude Code 는 `~/.claude/projects/-Users-donghae-workspace-ai-onTong/memory/` 에 영구 memory 를 가진다. 다음을 첫 세션에서 만들 것:

### 7.1 `feedback_section_simulation.md` (신규)

```markdown
---
name: simulation 세션 격리
description: 본 사용자는 onTong 의 Section 3 (simulation) 세션 담당. 다른 영역 쓰기 금지.
type: feedback
---

본 세션은 onTong 의 Section 3 (simulation) 담당.

쓰기 가능: toClaude/simulation/, backend/simulation/, backend/shared/contracts/simulation.py
쓰기 금지: toClaude/modeling/, toClaude/wiki/, backend/modeling/, backend/api/wiki.py 등 다른 섹션 영역
read-only OK: 위 금지 영역 모두 (참조)

**Why**: onTong 은 3 섹션이 병렬 세션으로 진행됨. 영역 침범 시 다른 세션의 작업 손실 위험.
**How to apply**: 모든 file 쓰기 작업 전에 경로가 위의 ✅ 영역인지 확인. 모호하면 사용자에게 확인.
```

### 7.2 `project_status.md` (수정 또는 신규)

modeling 세션의 entry 를 참고만 하고, simulation 세션 전용 entry 추가:

```markdown
## simulation 세션 (Section 3) — 시작
- 시작일: <오늘>
- 인계 패키지: toClaude/modeling/handoff-spec/00~07
- ground truth: data/ontology.db (read-only)
- 다음 작업: STEP 3.0 mkdir + STEP 3.1 신설 6 파일 골격
```

---

## 8. 막혔을 때 — Sub-agent 활용

CLAUDE.md 의 "Skill routing" 가 simulation 세션에 직접 적용되는 것:

| 상황 | 사용할 도구 |
|---|---|
| 어디부터 손대야 할지 모르겠을 때 | `Plan` 서브에이전트 — 본 step 의 implementation plan 요청 |
| 매핑된 ontology 항목이 어디 있는지 찾을 때 | `Explore` 서브에이전트 — codebase 탐색 |
| 버그가 났을 때 | `/investigate` skill |
| 운영 사고 회귀 시뮬 작성 시 | `/office-hours` skill (도메인 / 의도 명확화) |
| 큰 변경 후 PR 직전 | `/review` skill |
| Claude Code 자체의 사용법 (skill / hook / MCP / IDE 통합) | `claude-code-guide` 서브에이전트 |

당신이 자주 활용할 패턴:
- "Plan 서브에이전트에게 STEP 4.1 의 첫 ChangeSpec → SimResult 흐름 implementation plan 을 요청" → 6 spec doc 의존성 파악된 step-by-step plan 받음.
- "Explore 서브에이전트에게 BR.enforced_by 가 코드에서 어떻게 throw 되는지 grep" → false-positive / false-negative 차이 파악.

---

## 9. 자주 막히는 점 — simulation 세션 specific FAQ

### Q1. modeling 세션의 `OntologyQueryClientImpl` 을 import 해도 되나?
✅ OK. `backend.modeling.api.ontology_query` 만. internal layer (mapping_layer / domain_layer / code_layer / persistence) 는 ❌.

### Q2. `tests/test_simulation_*.py` 어디에 둬야?
`tests/simulation/` 폴더 신설 권장. 기존 modeling tests 와 분리.

### Q3. simulation 결과를 ontology.db 에 저장해도 되나?
❌ 권장 안 함. ontology.db 는 인계 시점 ground truth. 시뮬 결과는:
- (a) 별도 SQLite — `data/simulation_runs.db` 신설
- (b) 같은 ontology.db 안에 `simulation_*` prefix 테이블 추가 (modeling 의 11 테이블과 명확히 구분)

(a) 가 깔끔. (b) 도 OK 하지만 prefix 엄수 + modeling 테이블 절대 ALTER 금지.

### Q4. main.py 수정해도 되나?
✅ Section 3 router import 1 줄 + include_router 1 줄만. 라인 67 + 라인 453 부근 (06 STEP 3.2 참조). 기존 wiring 변경 ❌.

### Q5. `frontend/src/components/sections/modeling/` 의 UI 도 쓰면 안 되나?
❌ Section 2 영역. 시뮬 결과 시각화 UI 가 필요하면 사용자에게 합의 받아 **modeling 세션 (사용자 / 담당자) 이 빌드** 하도록 요청. 당신이 직접 만들지 말 것.

### Q6. `toClaude/_shared/verify.sh` 가 simulation 검증을 안 함
다음 세션에서 사용자 합의 후 `verify.sh` 에 simulation 항목 추가. 처음에는 `toClaude/simulation/CHECKLIST.md` 의 curl 만으로 검증.

### Q7. ChangeSpec.scenario_fixture.lookups 의 정확한 row 형식 (Phase E #41)
spec 05 §3.3 의 `{table_spec_fqn}:{pk}` + `{pk, table_spec_fqn, columns}` 따름. 06 STEP 4.2 의 첫 시나리오가 형식 굳히기 PR. 변경 시 spec 05 + design-gap #41 동시 갱신.

### Q8. Claude Code 가 가끔 modeling 폴더 수정 시도하려 함
**즉시 멈추고 본 가이드 §2 다시 읽으라고 prompt** 또는 `/clear` + 재시작. memory 의 `feedback_section_simulation.md` 가 잘 박혀있으면 재발 적음.

---

## 10. CLAUDE.md 핵심 (참조용)

본 가이드는 CLAUDE.md 의 simulation 적용본. 원본은 `/CLAUDE.md` 에 있고, Claude Code 가 자동으로 읽음. 항목 다시 확인할 곳:

| 항목 | CLAUDE.md 절 |
|---|---|
| Language Rule (Korean for user, English for code) | "🌍 Language & Output Rules" |
| Section Isolation | "🔒 Section Isolation Rule" |
| Step Completion 7 항목 | "📋 Step Completion Protocol" |
| Ad-hoc Change 4 동기화 | "🔀 Ad-hoc Change Protocol" |
| Session Start 흐름 | "🔄 Session Start Protocol" |
| TDD Rule | "🧪 Smart TDD Rule" |
| Pre-Demo Verification | "🔍 Pre-Demo Verification Protocol" |
| Archive Rule | "📁 Archive Rule" |
| Skill routing | "## Skill routing" |

---

## 11. 첫 PR 의 dimensions (인수자 시작 PR 권장 형태)

PR 1 — **boilerplate**:
- mkdir + 6 신설 파일 골격 (06 STEP 3.0 + 3.1)
- main.py 2 줄 추가
- `tools/check_agent_isolation.py` 통과
- `pytest tests/simulation/` 0 test 통과 (테스트 폴더 + conftest 만)

PR 2 — **ChangeSpec / SimResult schema**:
- `backend/shared/contracts/simulation.py` Pydantic 모델
- `tests/simulation/test_schema.py` 모델 invariant 검증
- 06 STEP 4.2 의 first scenario ChangeSpec 이 schema validation 통과

PR 3 — **첫 흐름 stub**:
- LookupDataSource fixture 모드만
- JavaSandbox stub_dispatch tier
- PythonGenerator echo-stub
- Orchestrator + run lifecycle
- `POST /api/simulation/runs` + `GET /api/simulation/runs/{id}/sim-result`
- 06 STEP 4.3 흐름이 verdict=sim_verified 로 통과

이후 BR violation / anchor invalidation / 운영 사고 회귀 등으로 확장.

---

## 12. 인수자에게 — 마지막 한 마디

본 인계 패키지는 38 일간의 archive 합의 + 178 row ground truth + 4 layer 코드 분리 + 7 단계 사용자 합의를 거친 결과다. spec 5개 doc 은 검수 통과한 명세이지만, 운영하면서 부딪히는 ambiguity 는 Phase E backlog #37~#47 에 등록되어 있다 — **부딪히는 그 시점에 사용자에게 물어 결정** 하면 됨. 혼자 결정 ❌.

본 가이드의 **§1 첫 conversation prompt** 만 그대로 입력하면 Claude Code 가 본 패키지의 모든 제약 / 프로토콜 / 격리 규칙을 인지한 상태로 작업 시작.

질문은 사용자 / 인계자 (modeling 세션 담당) 에게.

---

마지막 업데이트: 2026-05-10 (Phase D 종결 직전, 인계 가능 상태)
