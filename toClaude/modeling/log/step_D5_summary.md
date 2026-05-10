# Phase D — D.5 다음 개발자 onboarding 가이드

> 2026-05-10. Phase D 종결 직전. spec doc 5개 (00~05) 와 실제 코드/DB 사이의 bridge 작성.

## 산출물

- `toClaude/modeling/handoff-spec/06-developer-onboarding.md` — 신규 (350+ 줄)
- `toClaude/modeling/handoff-spec/00-README.md` — D.5 항목 추가 + "처음 해야 할 일" 시퀀스에 06 진입점 양쪽 추가 + 검수 기록 row 추가

## 06-developer-onboarding 의 구성

| 절 | 내용 |
|---|---|
| 0 | 본 문서가 답하는 6 질문 |
| 1 | 인계 시점 시스템 한 화면 요약 (Section 1/2/3 + ontology DB 카운트 다이어그램) |
| STEP 1 | Repo orientation — 디렉토리 지도 + 의존성 방향 + 5 spec 가이드 + 도메인 primer 포인터 |
| STEP 2 | 환경 setup + 인계 검증 — pip / npm / 백엔드 구동 / **★ 9 항목 SQL 검증** / curl smoke / UI 확인 / isolation 검사 |
| STEP 3 | Section 3 boilerplate — 신설 6 파일 (`shared/contracts/simulation.py` + `simulation/api/router.py` + 4 runner) + main.py wiring 1 위치 + ChangeSpec 모델 + PythonGenerator + JavaSandbox stub |
| STEP 4 | 첫 ChangeSpec → SimResult 흐름 — 시나리오 선정 (`action.scm.std.lookup_first_match`) + ChangeSpec 작성 + 흐름 통과 기대값 + 다음으로 넓힐 시나리오 (운영 사고 회귀 P-2018-0098/P-2018-0721) + verdict 6 조건 + anchor invalidation manual 부터 |
| 5 | 회복 / 재import 명령 4종 (idempotent) |
| 6 | Phase E 결정 대기 11건 — 부딪히는 STEP + 가벼운 시작 옵션 표 |
| 7 | 자주 막히는 점 7건 (Q&A) |
| 8 | 도와줄 수 있는 곳 — 6 외부 자료 위치 |
| 9 | 인계자 contact |
| 10 | 인계 완료 정의 7 항목 (1~4 = 인계자 책임, 5~7 = 인수자 책임) |

## 검증

STEP 2.3 의 9 항목 검증 SQL 을 실 DB 에 실행 → 9/9 ✅:

| 항목 | 카운트 |
|---|---|
| atomic | 16 |
| composite | 29 |
| actions | 38 |
| verified actions (≥signature_locked) | 38 |
| realizations | 43 |
| BR confirmed | 17 |
| BR with enforced_by | 17 |
| anchor confirmed | 9 |
| anchor with line | 9 |

→ 본 문서의 STEP 2.3 가 인계 시점 실 DB 와 1:1 일치. 다음 개발자가 검증 시 동일 결과 기대.

## 사용자 합의 흐름

- 사용자 질문: "지금 레벨이면 인계해서 온톨로지-코드 매핑 기반으로 에이전트 만들 수 있는 상황이라는거지?"
- 응답: Critical 처리 완료 + Phase E backlog 11건 등록 완료. D.5 (개발자 onboarding) 만 in_progress 였음.
- 사용자: "b로 진행" (D.5 완료 후 인계 옵션)
- → 본 작업 = D.5 종결.

## 영향

- **인계 가능 상태 진입** — 6 doc 으로 self-contained handoff package 완성. 외부 단독 전달 가능.
- **인수자 onboarding 마찰 최소화** — STEP 2 검증 명령 9건이 30초~1분에 완료. spec 만 보고 self-bootstrap 가능.

## 다음

- Phase D 종결 — 2 서브에이전트 fresh-context 검수 (D.5 자체 + 06 의 "STEP 4 첫 흐름" 시나리오 적정성)
- Phase E 진입 준비 — backlog #37~#47 결정 시 사용자 합의 절차

## 관련 파일

- `toClaude/modeling/handoff-spec/06-developer-onboarding.md`
- `toClaude/modeling/handoff-spec/00-README.md` (수정)
- 본 step summary: `toClaude/modeling/log/step_D5_summary.md`
