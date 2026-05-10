# Handoff Spec — 시뮬레이션 에이전트 구현자용 명세 패키지

> **목적**: Phase D 종료 후 다음 개발자(시뮬 에이전트 구현 담당)에게 인계되는 **API/스키마 명세 deliverable**.
>
> **상태**: 2026-05-10 작성. Phase D 진행 중 (D.2 완료 / D.3~D.5 후속 추가).
>
> **위치**: `toClaude/modeling/handoff-spec/`. 외부 단독 전달 가능 (이 폴더 자체가 self-contained).

---

## 누구를 위한 패키지인가

이 폴더는 **다음 사람이 onTong 시뮬레이션 에이전트를 구현하기 위해 필요한 명세만** 모은다.
Phase A/B/C 의 ground truth 일관성 입증, design-gaps 의도, 운영 history 등은 별도 문서를 참조한다 (이 README 의 "참고 문서" 절).

### 이 패키지가 답하는 질문

1. **현재 onTong 백엔드가 시뮬 에이전트에게 충분한 API 를 제공하는가?**
2. **부족하다면 어떤 스키마/엔드포인트가 추가되어야 하는가?**
3. **시뮬 자체 (ChangeSpec → SimResult) 의 데이터 형식과 흐름은 무엇인가?**
4. **시뮬 runner (PythonGenerator + Java dispatch sandbox) 가 따라야 할 인터페이스는 무엇인가?**

---

## 파일 구성과 읽기 순서

| 순서 | 파일 | 목적 | 분량 |
|---|---|---|---|
| 1 | `00-README.md` (본 문서) | 전체 패키지 가이드 + 컨텍스트 | 짧음 |
| 2 | `01-schema-extensions.md` | 기존 BusinessRule/Action/BusinessTerm 스키마 보강 + 신규 엔티티 (DesignGap / SimulationScenario) | 중 |
| 3 | `02-ontology-api-additions.md` | `/api/ontology/*` 보강 — 약 12 신규 endpoint (BR / reverse lookup / graph traversal) | 중 |
| 4 | `03-simulation-api-spec.md` | `/api/simulation/*` 신규 router — 약 10 신규 endpoint (ChangeSpec → SimResult 라이프사이클) | 중 |
| 5 | `04-changespec-simresult-schema.md` | ChangeSpec 입력 + SimResult 출력 + critical 갭 #1/#2 (SIM_VERIFIED 판정 / Anchor invalidation) | 중 |
| 6 | `05-runner-interface.md` | PythonGenerator + Java Dispatch Sandbox + LookupDataSource + Runner state machine + Python↔Java boundary + Artifact collection + ★ 의존성 점검 | 큼 |
| 7 | `06-developer-onboarding.md` ★ | spec 5개 ↔ 실 코드/DB bridge — STEP 1 repo 지도 / STEP 2 인계 검증 명령 / STEP 3 boilerplate 6 파일 / STEP 4 첫 ChangeSpec → SimResult 흐름 / Phase E 11건 부딪히는 위치 / 자주 막히는 점 7건 | 중 |
| 8 | `07-claude-code-handoff-guide.md` ★ | Claude Code 사용자용 — 첫 conversation prompt, Section Isolation 정확한 경계 (✅ 쓰기 가능 / ❌ 쓰기 금지 / Read-only / 직접 import 금지), Step Completion Protocol 적용, TDD, sub-agent 활용, simulation 세션 specific FAQ 8건, 첫 PR 권장 형태 | 중 |

**처음 읽는 사람 (Claude Code 사용자)**: **07 → 06 → 1~7 순서로 읽으세요**.
1. **07** — Claude Code 첫 conversation prompt 그대로 입력해 본 패키지의 제약 / 프로토콜을 Claude Code 가 인지한 상태로 시작.
2. **06** — STEP 1 (repo 지도) + STEP 2 (인계 9 검증) 로 받은 상태 확인.
3. **본 README → 01 → 02 → 03 → 04 → 05** — spec 깊이 진입.
4. **06 STEP 3~4** 로 돌아와 코드 작성 시작.

---

## Ontology DB 현황 (2026-05-10 기준)

> **위치**: `data/ontology.db` (SQLite). main.py startup 시 `bootstrap_database()` 자동 호출.
>
> **검증 일자**: 2026-05-10 — 인계 가능성 점검에서 fresh-context Explore agent + import script 결과.

| 종류 | archive 합의 | 실 storage (slab-design-real repo) | 상태 |
|---|---|---|---|
| atomic | 16 | 16 | ✅ 완전 (2026-05-10 import) |
| composite | 22 | 1220+ | ✅ 충족 (auto import 된 것 다수 포함) |
| Action | 41 | 1512+ | ✅ 충족 |
| BusinessRule | 17 | 17 | ✅ 완전 (1차 추출 12 + 2차 grep 검증 5 추가) |
| TypeRealization | 60+ | 1428 | ✅ 충족 |
| AnchorBinding | 9 | 9 | ✅ 완전 (2026-05-10 import) |

### Import 흐름 (재실행 가능)

```bash
python3 scripts/import_phase_archive.py --dry-run   # 검증
python3 scripts/import_phase_archive.py             # 실행
```

스크립트 위치: `scripts/import_phase_archive.py`. archive 의 atomic 16 + BR 12 + AnchorBinding 9 를 inline 정의 + INSERT OR IGNORE.

### 미완 영역 (Phase E 처리)

- inheritance_edges / composition_edges 테이블 0 row — atomic 분리 후 관계 정의 (선택)
- (BR 5개 누락은 2026-05-10 해소 — design-gap #48 closed)

---

## 현 상태 요약

### 현재 백엔드가 가진 것 (검증됨)

- **18 endpoint** under `/api/ontology/*` (`backend/modeling/api/ontology_router.py`)
  - List: terms / code-types / actions
  - Get-by-fqn: term / code-type / action
  - Composition: effective-parts (atomic 평탄화)
  - Code traversal (forward): call-sites / realizations-for-input / resolve-path
  - Anchor: anchor-bindings (per Action / per code_method)
  - Queue: unmapped-methods / ambiguous-call-sites / verification-progress
  - Search
- **5 추가 router** (graph_api / queue_actions_api / modules_api / perspective_api / recommend_api)
- **DTO**: TermDTO / CodeTypeDTO / ActionDTO / CompositionDTO / CallSiteDTO / RealizationDTO / AnchorBindingDTO / VerificationLevel / SearchHitDTO / 기타

### 현 백엔드에 **없어서 추가되어야 하는 것** (3 sub-agent fresh-context 검토 합성)

#### A. 스키마 부재 — `01-schema-extensions.md`

1. **BusinessRule.enforced_by** (List[CodeMethodFqn]) — 코드 가드 위치
2. **BusinessRule.violated_at_call** (CallSite[]) — 위반이 가능한 call site 추적
3. **BusinessRule.operational_history** (IncidentRef[]) — P-2018-0098 등 운영 사고 backtrack
4. **Action.realizes** (List[ActionFqn]) — PRIMARY ↔ realization 명시
5. **Action.delegates_to** (List[ActionFqn]) — workflow → 하위 호출 그래프
6. **BusinessTerm.facets.default_value** — 시뮬 fixture 시 기본값
7. **DesignGap entity** (id / area / question / impact / candidate_resolution / status) — 36 항목 1급 객체화
8. **SimulationScenario entity** (id / kind / inputs / expected_artifacts / origin) — 시나리오 카탈로그

#### B. Graph traversal 부재 — `02-ontology-api-additions.md`

9. `/api/ontology/business-rules` — list/get/by-action/by-method
10. `/api/ontology/actions/{fqn}/delegates-to-tree` — transitive call graph
11. `/api/ontology/actions/{fqn}/realizing-methods` — PRIMARY 코드 위치
12. `/api/ontology/atoms/{fqn}/used-by` — atomic → TR/Anchor 역참조
13. `/api/ontology/code-methods/{fqn}/callers` — reverse caller lookup
14. `/api/ontology/anchor-bindings/by-literal` — literal → anchor 역참조
15. `/api/ontology/design-gaps` — list/get/filter
16. `/api/ontology/scenarios` — list/get/by-action

#### C. 시뮬 자체 라이프사이클 부재 — `03-simulation-api-spec.md`

17. `/api/simulation/scenarios` — 카탈로그
18. `/api/simulation/runs` — 실행 시작 / 상태 / 결과
19. `/api/simulation/runs/{id}/sim-result` — SimResult 조회
20. `/api/simulation/runs/{id}/changespec` — 입력 ChangeSpec 조회
21. `/api/simulation/diff` — 두 run 비교
22. `/api/simulation/anchor-invalidate` — 코드 변경 시 stale anchor 마킹
23. `/api/simulation/verification/promote` — VerificationLevel 진급

---

## 합의된 5 결정 (Phase D 진입 직전)

| # | 결정 | 영향 |
|---|---|---|
| Q1 | 산출 범위 = **C** (ChangeSpec/SimResult schema + Runner I/F + 핵심 갭 4건) | D.3/D.4 의 명세 깊이 |
| Q2 | ChangeSpec format = **B** (action_fqn + atomic_overrides + scenario_fixture) | `04-changespec-simresult-schema.md` |
| Q3 | Critical 갭 4건 시점 = **A** (D.3 에서 일괄 명세) | 운영 일정 |
| Q4 | Backend 통합 vs 별 API = **B** (`/api/simulation/*` 별 router) | 본 패키지 `03-simulation-api-spec.md` |
| Q5 | Phase D 모드 = **M4** (서브에이전트 2 검토 + 사용자 형식 통합) | 검수 절차 |

---

## 섹션 경계 — modeling 영역 vs simulation 영역

> **목적**: onTong 은 3 섹션 (wiki / modeling / simulation) 이 별 세션으로 진행되는 멀티 세션 프로젝트. 본 패키지 (`handoff-spec/`) 는 modeling 세션이 simulation 세션에게 인계하는 명세이므로, **두 영역의 코드/책임 경계가 명확히 분리되어야** 한 영역의 변경이 다른 영역에 무한 dependency 를 일으키지 않는다.

### 책임 분담

| 영역 | 코드 위치 | 책임 |
|---|---|---|
| **modeling 세션** (현재) | `backend/modeling/api/*.py` (ontology_router 등) <br>`backend/modeling/persistence/*` <br>`backend/modeling/{ontology,domain_layer,mapping_layer,code_layer}/*` <br>`backend/shared/contracts/ontology_query.py` | Code/Mapping/Domain 4-Layer 의 storage + query API 제공. Ontology / BusinessRule / Action / AnchorBinding / DesignGap / SimulationScenario 의 정의 + read-only query. |
| **simulation 세션** (다음) | `backend/simulation/api/*` (기존 빈 폴더 — endpoint 추가) <br>`backend/simulation/runner/*` (신규 폴더 — sandbox + python gen) <br>`backend/shared/contracts/simulation.py` (신규 ChangeSpec/SimResult) | ChangeSpec → SimResult 라이프사이클. Python 코드 생성 + Java sandbox dispatch + verdict 판정 + anchor invalidation. |
| **공유** | `backend/shared/contracts/*.py` | DTO 정의 — modeling 이 정의, simulation 이 import only. |

### 의존성 방향 (단방향)

```
┌──────────────────────────────────────────────────────────────────────┐
│  simulation/ (Section 3)                                             │
│  ─────────────────────────                                           │
│  - /api/simulation/* router (POST /runs, sim-result 등)              │
│  - sandbox runner (Python gen + Java dispatch)                       │
│  - ChangeSpec/SimResult 모델 정의                                     │
│       │                                                              │
│       │ depends on (import + HTTP call)                              │
│       ▼                                                              │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │  modeling/ (Section 2 — 본 세션)                                │  │
│  │  ────────────────────────────────                              │  │
│  │  - /api/ontology/* router (read-only)                          │  │
│  │  - OntologyQuery / BR / Action / AnchorBinding storage         │  │
│  │  - DesignGap / SimulationScenario 카탈로그                       │  │
│  └────────────────────────────────────────────────────────────────┘  │
│                                                                      │
│  ✗ modeling 은 simulation 의 어떤 모듈도 import 하지 않음            │
│  ✗ modeling 은 simulation router 의 endpoint 를 호출하지 않음         │
└──────────────────────────────────────────────────────────────────────┘
```

### 인계 인터페이스 (modeling → simulation)

modeling 세션이 simulation 세션에게 제공하는 것은 다음 세 가지 뿐:

1. **REST endpoint** — `/api/ontology/*` (`02-ontology-api-additions.md` 보강 후 약 30 endpoint). simulation 세션은 HTTP 만으로 호출 가능 (process 분리 / 같은 process 모두 OK).
2. **Python facade** — `backend/modeling/api/ontology_query.py` 의 `OntologyQueryClientImpl`. simulation 세션이 같은 process 안에서 import 가능 (HTTP 우회).
3. **DTO** — `backend/shared/contracts/ontology_query.py` 의 모든 DTO. import only, 정의 변경은 modeling 세션 책임.

### simulation 세션이 책임지는 것 (modeling 세션이 손대지 않을 영역)

실 폴더 구조 — `backend/simulation/{api,tools,mock,client}/` 가 이미 비어있는 폴더로 존재. 본 명세는 그 위에 신규 파일 + `runner/` 신규 폴더 추가:

```
backend/simulation/api/__init__.py            (기존)
backend/simulation/api/router.py              ★ /api/simulation/* endpoint
backend/simulation/api/run_handle.py          ★ run lifecycle state machine
backend/simulation/api/verdict.py             ★ Section 3 verdict 판정 로직
backend/simulation/api/anchor_invalidate.py   ★ Section 4 invalidation
backend/simulation/runner/python_generator.py ★ D.4 명세 (Section 1)
backend/simulation/runner/java_sandbox.py     ★ D.4 명세 (Section 2) + 3-tier (stub/jvm_subprocess/graalvm)
backend/simulation/runner/dispatch.py         ★ D.4 dispatch 정합성 검증
backend/simulation/runner/lookup_source.py    ★ D.4 LookupDataSource (Section 3)
backend/simulation/runner/orchestrator.py     ★ D.4 running 단계 entry (Section 4.5)
backend/shared/contracts/simulation.py        ★ ChangeSpec / SimResult / BREvidence 등
```

기존 빈 폴더 `backend/simulation/{tools,mock,client}/` 는 simulation 세션 자유 활용.

### 실수 방지 규칙

- **modeling 세션은 위의 ★ 표시 파일을 만들거나 수정하지 않는다**. 본 세션 (modeling) 이 simulation 모듈을 만들면 의존성 그래프가 역전됨.
- modeling 세션이 simulation 동작을 위해 추가 API 가 필요하면 `02-ontology-api-additions.md` 에 endpoint 추가만 한다 (HTTP 호출은 simulation 세션이 직접).
- ChangeSpec / SimResult 모델 정의는 `backend/shared/contracts/simulation.py` 가 가장 깔끔 — modeling 의 ontology_query.py 와 같은 폴더이지만 **별 파일** 로 cohesion 분리.
- 두 세션이 같은 파일 (예: shared 의 contracts) 에 동시에 쓰기를 시도하지 않도록 — 분리된 파일 + import 만 연결.

### CLAUDE.md 의 Section Isolation Rule 과의 관계

CLAUDE.md 의 "Section Isolation Rule" 은 `toClaude/<section>/` 폴더 단위의 쓰기 분리. 본 절은 **`backend/` 안의 코드 분리** 추가 가이드:

| 영역 | toClaude 쓰기 | backend 코드 쓰기 |
|---|---|---|
| modeling 세션 | `toClaude/modeling/` | `backend/modeling/*` + `backend/shared/contracts/ontology_query.py` |
| simulation 세션 | `toClaude/simulation/` | `backend/api/simulation/*` + `backend/simulation/*` + `backend/shared/contracts/simulation.py` |
| wiki 세션 | `toClaude/wiki/` | `backend/api/wiki.py` 등 (별도) |

---

## 적용 가이드

### 시뮬 에이전트 구현자가 처음 해야 할 일

> 시간 추정 제거 — 페이스는 본인 결정. 순서만 따르면 됨.

0. **`07-claude-code-handoff-guide.md` 읽고 §1 의 첫 conversation prompt 입력** — Claude Code 가 본 패키지의 격리 / 프로토콜 / 제약을 인지한 상태로 시작
1. **`06-developer-onboarding.md` STEP 1~2 실행** — repo 지도 + 인계 DB/API/UI 검증 (검증 9 항목 ✅ 확인 후에만 spec 깊이 진입)
2. 본 README 읽기 (전체 컨텍스트 + 5 결정)
3. `01-schema-extensions.md` 의 스키마 추가 영향 파악 — 8 추가 항목이 기존 4-Layer (Code/Mapping/Domain/Simulation) 의 어디에 자리잡는지
4. `02-ontology-api-additions.md` 의 신규 endpoint 카탈로그 훑기
5. `03-simulation-api-spec.md` 의 ChangeSpec→SimResult 라이프사이클 그림 잡기
6. `04-changespec-simresult-schema.md` 의 ChangeSpec/SimResult 정밀 schema + verdict 판정 6 조건 + anchor invalidation 흐름 파악
7. `05-runner-interface.md` 의 PythonGenerator + JavaSandbox + LookupDataSource + Orchestrator entrypoint (4.5) + RunInputs (4.6) + ★ 의존성 점검 (Section 7) 파악
8. 본 README 의 "참고 문서" 에서 `phase-d-handoff-package.html` 의 D.1 onboarding 으로 넘어가 도메인 primer 읽기
9. **`06-developer-onboarding.md` 로 돌아가 STEP 3~4 실행** — Section 3 boilerplate 6 파일 골격 + 첫 ChangeSpec → SimResult 흐름 통과

### 명세 적용 순서 (코드)

1. **Schema 추가** (`01-schema-extensions.md` Section 1~3) — 기존 DTO/모델 확장 (Realization DTO 명시 포함)
2. **Migration** — DB/storage 의 BR/Action/BusinessTerm 컬럼 추가, DesignGap/SimulationScenario 테이블 신설
3. **Ontology API 보강** (`02-ontology-api-additions.md`) — endpoint 단위 incremental
4. **Simulation API 신규** (`03-simulation-api-spec.md`) — `/api/simulation/*` router 신설
5. **ChangeSpec/SimResult 모델 정의** (`04-changespec-simresult-schema.md`) — `backend/shared/contracts/simulation.py` 신규 + verdict 판정 + anchor invalidation 흐름
6. **시뮬 runner** (`05-runner-interface.md`) — PythonGenerator + Java sandbox + LookupDataSource + state machine. `backend/api/simulation/*` + `backend/simulation/runner/*` 신규

---

## 참고 문서 (이 패키지 외부)

> 이 패키지만으로 부족할 때 펼쳐서 보는 자료. 아래는 모두 `toClaude/modeling/` 안에 위치.

| 문서 | 내용 |
|---|---|
| `phase-d-handoff-package.html` D.1 | 도메인 primer + 4 sub-domain map + 16 atomic pool + 시뮬 흐름 5 step |
| `phase-c-archive-confirm.html` C.7 | Phase A+B+C 178 row ground truth 표 (atomic 16 / composite 22 / Action 41 / BR 17 / TR ~60+) |
| `phase-b-archive-confirm.html` B.6 | Round 5 archive 5 entity confirm 결과 |
| `round6-live-authoring.html` | Phase A 종료 archive (Customer / Productivity 인터뷰) |
| `design-gaps-and-questions.md` | 36 항목 (Phase A 22 + Phase B 5 + Phase C 9). 본 패키지의 DesignGap 엔티티 source |
| `anchor-binding-deep-dive.html` | AnchorBinding 7 종 + 9 anchor 마커 (코드 레벨 매핑 의도) |
| `agent-graph-architecture.html` | 23 tool + per-cap 권한 (시뮬 에이전트와 별개의 Authoring agent 명세) |

### memory (선택)

- `~/.claude/projects/-Users-donghae-workspace-ai-onTong/memory/project_decisions_v3.md` — 12 결정 (시뮬 + UI/UX)
- `~/.claude/projects/-Users-donghae-workspace-ai-onTong/memory/project_decisions_v4_action.md` — 16 결정 (Action 모델 + Two-Layer)

---

## 검수 / 검토 기록

| 일자 | 항목 | 결과 |
|---|---|---|
| 2026-05-10 | D.2 API 충분성 검토 | 3 fresh-context 서브에이전트 검토 → 8 공통 갭 합의 → 본 패키지 작성 |
| 2026-05-10 | D.3 산출 (`04-changespec-simresult-schema.md`) | ChangeSpec/SimResult schema + critical 갭 #1/#2. fresh-context 서브에이전트 2 검수 → 우선 수정 6건 반영 + WARN 5건 design-gaps #37~#41 등록 |
| 2026-05-10 | D.4 산출 (`05-runner-interface.md`) | PythonGenerator + Java sandbox + LookupDataSource + state machine + Python↔Java boundary + 의존성 점검. fresh-context 서브에이전트 2명 검토 진행 중 |
| 2026-05-10 | D.5 산출 (`06-developer-onboarding.md`) | spec 5개 ↔ 실 코드/DB bridge. STEP 1~4 + 회복 명령 + Phase E 11건 부딪히는 위치 + FAQ. 검증 명령 9건은 본 인계 시점 실 DB 카운트로 작성. |
| 2026-05-10 | Phase D 종결 검수 (D.5 + STEP 4 시나리오) — fresh-context 서브에이전트 2 | Critical 5건 모두 반영: (1) `backend/simulation/` 폴더 부재 사실 정정 + STEP 3.0 mkdir 추가 (2) main.py wiring 정확한 라인 (67 + 453) 명시 (3) STEP 4 action FQN `lookup_first_match` → `match_customer_limit_for_order` 정정 (DB 검증 통과) (4) atomic_overrides 키 `customer_grade_code` → `term.scm.shared.{cmp,org,proc,grade}` (atomic FQN) (5) lookups 형식 spec 05 §3.3 정합 `{table_spec_fqn:pk}` + `{pk, table_spec_fqn, columns}`. Major 3건 (frontend optional, LLM env, mkdir) 도 반영. |
| 2026-05-10 | 07 Claude Code 가이드 작성 (`07-claude-code-handoff-guide.md`) | 인수자 (다음 개발자) 가 git pull 후 Claude Code 첫 conversation 부터 본 인계 패키지의 격리/프로토콜/제약을 인지한 상태로 시작하도록 가이드. 첫 prompt copy-paste, Section Isolation 정확한 경계 4 카테고리, Step Completion / TDD / sub-agent 활용 / FAQ 8건 / 첫 PR 권장 dimension 3개. |

---

마지막 업데이트: 2026-05-10
