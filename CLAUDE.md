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

# 📋 Step Completion Protocol (Strict)

Each step is NOT done until ALL of the following are completed in order. Do NOT skip any item. Do NOT wait for the user to remind you.

1. **Code implementation** — all tasks in the step
2. **Verification** — run CHECKLIST.md tests for the step (automated where possible)
3. **`toClaude/log/step{N}_summary.md`** — write step summary, then move to `toClaude/archive/`
4. **`toClaude/demo_guide.md`** — append new demo scenarios + troubleshooting
5. **`toClaude/TODO.md`** — mark completed tasks `[x]`
6. **Memory `project_status.md`** — update current status and next step
7. **Stop and report** — present checklist review results to user

Code complete ≠ Step complete. All 7 items above = Step complete.

---

# 🔀 Ad-hoc Change Protocol (Strict)

When the user requests ANY change mid-session (bug fix, new feature, UI tweak, label change, etc.), you MUST update ALL relevant documents in the SAME turn as the code change. Do NOT wait until the end of the step.

1. **`toClaude/TODO.md`** — add new task rows with `[x]` if already done, or `[ ]` if pending
2. **`toClaude/CHANGES.md`** — log the change with `[x]` (done) or `[ ]` (deferred)
3. **`toClaude/demo_guide.md`** — add/update test scenarios if the change is user-facing
4. **Memory `project_status.md`** — update current status if significant

Code change without document sync = incomplete work. Never let docs drift from code.

---

# 🔄 Session Start Protocol (Strict)

At the start of every new session (e.g., "하던 일 이어서 하자"), ALWAYS:

1. **Read `toClaude/CHANGES.md`** — check for unprocessed `[ ]` items
2. **Process pending changes FIRST** — before resuming normal work
3. After processing, mark items `[x]` and reflect in TODO.md / master_plan.md as needed
4. Then read `toClaude/TODO.md` and resume from the next incomplete step

Never skip step 1. The user may have added requirements between sessions.

---

# 🧪 Smart TDD Rule (Backend)

For any NEW backend logic, API endpoint, or Agent tool:

1. **Read** the relevant section in `CHECKLIST.md` (testing manual)
2. **Write an automated test script** (e.g., `tests/test_step_1e.py`) BEFORE writing app code
3. **Write the app code**
4. **Run the test script** — only mark `[x]` in `TODO.md` when ALL PASS

**Exception:** Simple UI/CSS-only changes do not require TDD scripts.

---

# 📁 Archive Rule

- Do NOT read past step summaries (`toClaude/archive/*.md`) unless explicitly asked.
- `TODO.md` is the ONLY file where task status (`[x]`) is tracked (Single Source of Truth).
- `CHECKLIST.md` is a testing manual only — no checkboxes.
