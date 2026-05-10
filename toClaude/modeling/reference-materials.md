# onTong — 참고자료 인덱스

> **목적**: 최종 사용자 가이드 / 발표 자료 / 외부 공유 자료 작성 시 참고할 수 있는 산출물의 단일 진입점.
>
> **상태**: 2026-05-09 시점. 새 산출물 추가 시 여기 등록.
>
> **활용 흐름**: 최종 가이드 작성자가 (1) 이 인덱스 → (2) 카테고리 → (3) 해당 산출물 read.

---

## 카테고리

### A. 발표용 통합 가이드 (외부 공유)

| 파일 | 대상 | 핵심 |
|---|---|---|
| `section1-2-3-overview.html` | 다른 관계자 (팀 외부) | Section 1 (Wiki) + Section 2 (Modeling) + Section 3 (Simulation) 풀 가이드. 12 섹션. 도메인 (철강 SCM) → 4-Layer 아키텍처 → 데이터 모델 → drama DNA → 차별 (Palantir 비교) → FAQ. |

### B. 심층 개념 가이드 (특정 개념 깊이)

| 파일 | 개념 | 핵심 |
|---|---|---|
| `anchor-binding-deep-dive.html` | AnchorBinding | 인터랙티브 6 탭. 큰 그림 / 7 종 anchor / cumulativeProductivity + findFirstMatch 9 anchor 마커 클릭 / ChangeSpec 시뮬 흐름 stepper / 영향도 3 시나리오 / 셀프 체크 6 질문. |

(향후 추가 후보)
- `verification-level-deep-dive.html` — 6 단계 state machine 의 깊이 가이드
- `authoring-ai-deep-dive.html` — graph-aware ReAct 의 23 tool / per-cap 권한 가이드
- `business-rule-deep-dive.html` — Round 5 archive 의 BusinessRule 모델 + Gap Inspector 통합

### C. 라이브 인터뷰 archive (도메인 합의 ground truth)

| 파일 | 내용 |
|---|---|
| `round5-live-authoring.html` | Round 5 — Order/Slab/HrSpec/CastSpec/EdgingSpec/EdgingGroup/HrMinWgt/HrMaxWgt 6 표준 인터뷰 archive (Phase B 입력 자료) |
| `round6-live-authoring.html` | Round 6 — Customer/Productivity 8 step 풀 사이클 ✓ Phase A 종료 (47 row ground truth) |
| `phase-b-archive-confirm.html` | **Phase B — Round 5 archive 5 entity confirm 완료 (HrMin+Max 통합 처리).** B.1~B.5 + B.6 종결 archive. **50 row** (atomic 6 + composite 8 + Action 7 + BR 3 + TR 26) + Phase A retroactive 1. Phase A+B 합계 **98 row**. |
| `phase-c-archive-confirm.html` | **Phase C — Order/Slab/21-step Algorithm 완료.** C.1~C.6 + C.7 종결 archive. **80 row** (atomic 3 + composite 12 + Action 30 + BR 13 + TR 22 + design-gaps 9). 5 결정 합의 (A/A/A/A/A). Phase A+B+C 합계 **178 row**. |
| `phase-d-handoff-package.html` | **Phase D — 다음 개발자 인계 패키지 (M4 모드).** D.1~D.4 완료 (서브에이전트 2 검수 × 4회 + 우선 수정 18건 반영). 5 결정 합의 (C/B/A/B/M4). 진행: D.5 진입. ontology DB **42 row 완전 import** (atomic 16 + BR 17 + AnchorBinding 9 — 2026-05-10 BR 5 추가). simulation path 정정 (`backend/simulation/{api,runner}/`). |

### D. 디자인 갭 / 의문 트래킹

| 파일 | 내용 |
|---|---|
| `design-gaps-and-questions.md` | **48 항목 (1 closed = 47 open)** (Phase A 22 + Phase B 5 + Phase C 9 + Phase D.3 5 + Phase D.4 6 + 인계 검증 1). 🔴 6 핵심 + 🟡 35 중간 + 🟢 6 가벼움. #48 BR 5 누락은 2026-05-10 해소 (archive 직접 grep). Phase E 일괄 결정. |
| `handoff-spec/` (별 폴더) | **시뮬 에이전트 구현자용 명세 deliverable.** 6 파일 (00 README + 01 schema-ext + 02 ontology-api + 03 simulation-api + 04 changespec/simresult + 05 runner-interface). 외부 단독 전달 가능. ontology DB 37 row import 완료 (atomic 16 + BR 12 + AnchorBinding 9). |

### E. 결정 기록 (project_decisions)

(메모리 — `~/.claude/projects/-Users-donghae-workspace-ai-onTong/memory/`)
- `project_decisions_v3.md` — 2026-04-26 12 결정 (시뮬 + UI/UX)
- `project_decisions_v4_action.md` — 2026-05-01 16 결정 (Action 모델 + Two-Layer)
- `project_authoring_graph_agent.md` — 2026-05-05 Authoring agent + 23 tool

### F. 기타 참고

| 파일 | 내용 |
|---|---|
| `agent-graph-architecture.html` | Authoring AI 23 tool 카탈로그 + per-cap 권한 + ReAct 설계 |
| `r6_validation_report.md` | R6-VAL 결과 (자바독 strip 검증, cap 2 confidence 0.50/0.45) |
| `demo_guide.md` | R6 + P1a 흐름 데모 가이드 |
| `scenarios.md` (sample-repos/slab-design-real/toClaude/) | 데모 시나리오 |
| `ALGORITHM.md` (sample-repos/slab-design-real/toClaude/) | 21-step 알고리즘 |
| `DRAMA_DNA.md` (sample-repos/slab-design-real/toClaude/) | drama DNA 6종 정리 |

---

## 최종 사용자 가이드 작성 시 권장 활용

### 시나리오 1 — 외부 발표 자료 만들기
1. `section1-2-3-overview.html` 그대로 share (12 섹션 발표 흐름)
2. 깊이 필요한 개념 → `anchor-binding-deep-dive.html` 등 link
3. 솔직한 미해결 영역 → `design-gaps-and-questions.md` (🔴 6 항목)

### 시나리오 2 — 내부 사용자 매뉴얼 만들기
1. Round 5/6 archive 의 사용자 인용 발췌 (도메인 운영 사례)
2. `anchor-binding-deep-dive.html` 의 인터랙티브 자료 활용
3. drama DNA 예시 (`DRAMA_DNA.md` + Round 6 의 컬럼 alias chaos 시각화)

### 시나리오 3 — 신참 모델러 onboarding
1. `section1-2-3-overview.html` 의 1 (한눈에) + 2 (drama DNA) 빠르게
2. `anchor-binding-deep-dive.html` 의 6 셀프 체크 카드 → 이해도 측정
3. Round 6 archive 의 Q1~Q9 흐름 따라가며 본인 인터뷰 시뮬

---

## 자료 검수 / 검토 기록

| 산출물 | 검수자 | 결과 위치 |
|---|---|---|
| `anchor-binding-deep-dive.html` | 3 서브에이전트 fresh-context (가독성 / 기술 정확성 / 비판적) | 2026-05-09 검수 결과 — 채팅 기록 / 추후 별도 정리 가능 |
| Phase A 종료 (47 row ground truth + Round 6 산출물) | 2 서브에이전트 fresh-context (Phase A 일관성 / Phase B 진입 준비) | 2026-05-09. **반영된 우선 수정 3건**: ① Step 1 archive atomic 6→7 retroactive 정정 (round6 archive section + master plan A.8.7 row 갱신), ② anchor ④ user_queue 3 위치 통일 (anchor-binding 9 anchor 표 일괄), ③ CastSpec 정의 정정 (round6 Phase B 준비 cheatsheet "주조 화학 성분" → "연주공장 두께/폭/길이 spec" + HANDOFF cheatsheet 표 신설). **사용자 결정 5건**: Phase B 범위 / atomic share 정책 / BR 등록 정책 / PK 결함 entity 처리 / 우선 수정 시점 → A/A/A/A/지금 합의. |
| Phase B 종료 (50 row + Phase A retroactive + Phase A+B 98 row) | 2 서브에이전트 fresh-context (Phase A 일관성 + Phase B 진입 준비) | 2026-05-10. Agent 1 우선 수정 3건 반영 (count off-by-one / round6 retroactive 자기모순 / design-gaps 동기화) + Agent 2 5 결정 합의 (A/A/A/A/A). |
| Phase C 종료 (80 row + Phase A+B+C 178 row) | 2 서브에이전트 fresh-context (대기) | 2026-05-10. Phase C 6 step (Order 4-sub / Slab+SlabResult / SdDesigner / Validator+Phase1 / 21-step body / SaveAction+history) 완료. 검토 대상: ① Phase A+B+C 통합 일관성 / ② Phase D API 설계 진입 준비. |

---

마지막 업데이트: 2026-05-09 (Phase A 종료 검수 + 우선 수정 3건 반영)
