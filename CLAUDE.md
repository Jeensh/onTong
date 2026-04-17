# gstack

Use the `/browse` skill from gstack for all web browsing. Never use `mcp__claude-in-chrome__*` tools.

## Available Skills

- `/office-hours`
- `/plan-ceo-review`
- `/plan-eng-review`
- `/plan-design-review`
- `/design-consultation`
- `/review`
- `/ship`
- `/land-and-deploy`
- `/canary`
- `/benchmark`
- `/browse`
- `/qa`
- `/qa-only`
- `/design-review`
- `/setup-browser-cookies`
- `/setup-deploy`
- `/retro`
- `/investigate`
- `/document-release`
- `/codex`
- `/cso`
- `/autoplan`
- `/careful`
- `/freeze`
- `/guard`
- `/unfreeze`
- `/gstack-upgrade`

---

# 🌍 Language & Output Rules (Strict)

Language is strictly partitioned by context to optimize token usage and reasoning quality.

1. **User Communication (Korean):**
   - All responses, explanations, summaries, and questions directly delivered to the user should be in natural Korean.

2. **Internal Reasoning & ReAct (English):**
   - All internal thoughts, planning, tool invocations, and ReAct loop outputs (Thought/Action/Observation) must be strictly in English.

3. **Code & Engineering (English):**
   - All variable names, function names, commit messages, and inline code comments must be in English.

---

# 🔒 Section Isolation Rule (Strict)

같은 워크스페이스에서 여러 Claude 세션이 병렬로 작업한다. 파일 쓰기 충돌을 방지하기 위해 다음을 엄격히 준수한다.

## 섹션 구조
- **Section 1 — wiki**: 위키 섹션 (담당: 위키 Claude 세션)
- **Section 2 — modeling**: 모델링 섹션 (담당: 모델링 Claude 세션)
- **Section 3 — simulation**: 시뮬레이션 섹션 (담당: 사람 개발자 또는 별도 세션)

## 폴더 매핑
- `toClaude/wiki/` — 위키 세션 전용 쓰기 영역
- `toClaude/modeling/` — 모델링 세션 전용 쓰기 영역
- `toClaude/simulation/` — 시뮬레이션 세션 전용 쓰기 영역 (필요 시 생성)
- `toClaude/_shared/` — 세 섹션 공용 참조. **사용자 승인 없이 수정 금지**.

## 규칙
1. **자기 섹션 폴더만 쓰기**: 현재 세션의 담당 섹션 폴더 밖으로 파일을 생성/수정하지 않는다.
2. **다른 섹션 폴더는 read-only**: 참조는 가능하나 절대 수정하지 않는다.
3. **`_shared/` 수정 금지**: 사용자의 명시적 승인이 있을 때만 수정한다.
4. **세션 담당 확인**: 세션 시작 시 사용자가 담당 섹션을 명시하지 않으면 물어본다.
5. **경로 표기**: 아래 프로토콜에서 `toClaude/<section>/` 경로는 현재 세션이 담당한 섹션 폴더를 의미한다. 예: 모델링 세션이면 `toClaude/<section>/TODO.md` = `toClaude/modeling/TODO.md`.

## 예외: 제품 콘텐츠 `wiki/` 루트
프로젝트 루트의 `wiki/`(위키 제품 지식베이스 콘텐츠)는 세션 격리 대상이 아니다. 작업 전 `git status`로 다른 세션이 건드리는 파일과 겹치지 않는지 확인한다.

---

# 📋 Step Completion Protocol (Strict)

Each step is NOT done until ALL of the following are completed in order. Do NOT skip any item. Do NOT wait for the user to remind you.

1. **Code implementation** — all tasks in the step
2. **Verification** — run CHECKLIST.md tests for the step (automated where possible)
3. **`toClaude/<section>/log/step{N}_summary.md`** — write step summary, then move to `toClaude/<section>/archive/`
4. **`toClaude/<section>/demo_guide.md`** — append new demo scenarios + troubleshooting
5. **`toClaude/<section>/TODO.md`** — mark completed tasks `[x]`
6. **Memory `project_status.md`** — update current status and next step
7. **Stop and report** — present checklist review results to user

Code complete ≠ Step complete. All 7 items above = Step complete.

---

# 🔀 Ad-hoc Change Protocol (Strict)

When the user requests ANY change mid-session (bug fix, new feature, UI tweak, label change, etc.), you MUST update ALL relevant documents in the SAME turn as the code change. Do NOT wait until the end of the step.

1. **`toClaude/<section>/TODO.md`** — add new task rows with `[x]` if already done, or `[ ]` if pending
2. **`toClaude/<section>/CHANGES.md`** — log the change with `[x]` (done) or `[ ]` (deferred)
3. **`toClaude/<section>/demo_guide.md`** — add/update test scenarios if the change is user-facing
4. **Memory `project_status.md`** — update current status if significant

Code change without document sync = incomplete work. Never let docs drift from code.

---

# 🔄 Session Start Protocol (Strict)

At the start of every new session (e.g., "하던 일 이어서 하자"), ALWAYS:

1. **담당 섹션 확인** — 사용자가 명시하지 않으면 물어본다. (wiki / modeling / simulation)
2. **Read `toClaude/<section>/HANDOFF.md` FIRST** — 다음 작업, 최근 컨텍스트, 환경 설정. 다른 컴퓨터로 이동해 ~/.claude 메모리가 없는 경우에도 이 파일만 있으면 이어서 가능.
3. **Read `toClaude/<section>/CHANGES.md`** — check for unprocessed `[ ]` items
4. **Process pending changes FIRST** — before resuming normal work
5. After processing, mark items `[x]` and reflect in TODO.md / master_plan.md as needed
6. Then read `toClaude/<section>/TODO.md` and resume from the next incomplete step

Never skip step 1. The user may have added requirements between sessions.

**HANDOFF.md 갱신 의무**: 세션 종료 전 또는 큰 작업 단위 완료 시 `toClaude/<section>/HANDOFF.md`의 "다음 세션 첫 작업" 섹션을 최신으로 유지할 것.

---

# 🧪 Smart TDD Rule (Backend)

For any NEW backend logic, API endpoint, or Agent tool:

1. **Read** the relevant section in `CHECKLIST.md` (testing manual)
2. **Write an automated test script** (e.g., `tests/test_step_1e.py`) BEFORE writing app code
3. **Write the app code**
4. **Run the test script** — only mark `[x]` in `TODO.md` when ALL PASS

**Exception:** Simple UI/CSS-only changes do not require TDD scripts.

---

# 🔍 Pre-Demo Verification Protocol (Strict)

pytest 통과 + TS 빌드 성공 ≠ 기능 정상. 사용자에게 데모를 넘기기 전에 반드시 아래를 수행할 것.

1. **`bash toClaude/_shared/verify.sh` 실행** — 자동 검증 스크립트 (pytest + tsc + API + 채팅 + 충돌 오탐 체크)
2. **해당 기능 체크리스트 실행** — `CHECKLIST.md`에서 변경 관련 섹션의 curl 명령을 직접 실행
3. **Edge Case 테스트** — 빈 입력, 단일 결과, 다수 결과 등 경계 조건 확인
4. **증거 기반 보고** — "잘 될 것이다" 추정 금지. 실행 결과(로그, curl 응답)를 근거로 보고

특히 다음 경우에 이 프로토콜이 중요:
- SSE 이벤트 추가/변경 → 실제 채팅으로 이벤트 시퀀스 확인
- 프론트엔드 UI 변경 → 브라우저에서 직접 렌더링 확인
- 데이터 파이프라인 변경 → 실제 데이터로 end-to-end 흐름 확인

**위반 시**: 데모에서 기본적인 버그가 발견되면 사용자 신뢰를 잃는다. 반드시 지킬 것.

---

# 📁 Archive Rule

- Do NOT read past step summaries (`toClaude/<section>/archive/*.md`) unless explicitly asked.
- `TODO.md` is the ONLY file where task status (`[x]`) is tracked (Single Source of Truth).
- `CHECKLIST.md` is a testing manual only — no checkboxes.

## Skill routing

When the user's request matches an available skill, ALWAYS invoke it using the Skill
tool as your FIRST action. Do NOT answer directly, do NOT use other tools first.
The skill has specialized workflows that produce better results than ad-hoc answers.

Key routing rules:
- Product ideas, "is this worth building", brainstorming → invoke office-hours
- Bugs, errors, "why is this broken", 500 errors → invoke investigate
- Ship, deploy, push, create PR → invoke ship
- QA, test the site, find bugs → invoke qa
- Code review, check my diff → invoke review
- Update docs after shipping → invoke document-release
- Weekly retro → invoke retro
- Design system, brand → invoke design-consultation
- Visual audit, design polish → invoke design-review
- Architecture review → invoke plan-eng-review
- Save progress, checkpoint, resume → invoke checkpoint
- Code quality, health check → invoke health
