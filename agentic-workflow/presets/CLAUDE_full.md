# Agentic Workflow — Full Preset
# 적합: 2주 이상, 복잡한 시스템 구축, 장기 프로젝트

---

# 📋 Step Completion Protocol (Strict)

Each step is NOT done until ALL of the following are completed in order. Do NOT skip any item.

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

When the user requests ANY change mid-session (bug fix, new feature, UI tweak, etc.), you MUST update ALL relevant documents in the SAME turn as the code change:

1. **`toClaude/TODO.md`** — add new task rows with `[x]` if done, `[ ]` if pending
2. **`toClaude/CHANGES.md`** — log the change with `[x]` (done) or `[ ]` (deferred)
3. **`toClaude/demo_guide.md`** — add/update test scenarios if user-facing
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

For any NEW backend logic, API endpoint, or tool:

1. **Read** the relevant section in `CHECKLIST.md` (testing manual)
2. **Write an automated test script** BEFORE writing app code
3. **Write the app code**
4. **Run the test script** — only mark `[x]` in `TODO.md` when ALL PASS

**Exception:** Simple UI/CSS-only changes do not require TDD scripts.

---

# 📁 Archive Rule

- Do NOT read past step summaries (`toClaude/archive/*.md`) unless explicitly asked.
- `TODO.md` is the ONLY file where task status (`[x]`) is tracked (Single Source of Truth).
- `CHECKLIST.md` is a testing manual only — no checkboxes.

---

# 💡 Demo-Feedback Cycle

After completing each step:
1. Provide demo scenarios in `demo_guide.md`
2. User tests and provides feedback
3. Capture feedback in `CHANGES.md`
4. Next step begins by processing captured feedback

This cycle is the primary quality mechanism. Never skip user verification.
