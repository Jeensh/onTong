# Agentic Workflow — Standard Preset
# 적합: 1~2주, 중규모 기능 개발, API 개발, UI 리뉴얼

---

# 📋 Step Completion Protocol

Each step is NOT done until ALL of the following are completed in order:

1. **Code implementation** — all tasks in the step
2. **Verification** — run tests or manual checks
3. **`toClaude/demo_guide.md`** — append new demo scenarios
4. **`toClaude/TODO.md`** — mark completed tasks `[x]`
5. **Stop and report** — present results to user

Code complete ≠ Step complete.

---

# 🔀 Ad-hoc Change Protocol

When the user requests ANY change mid-session, you MUST update ALL relevant documents in the SAME turn:

1. **`toClaude/TODO.md`** — add new task rows with `[x]` if done, `[ ]` if pending
2. **`toClaude/CHANGES.md`** — log the change
3. **`toClaude/demo_guide.md`** — add/update test scenarios if user-facing

Code change without document sync = incomplete work.

---

# 🔄 Session Start Protocol

At the start of every new session:

1. **Read `toClaude/CHANGES.md`** — check for unprocessed `[ ]` items
2. **Process pending changes FIRST** — before resuming normal work
3. Mark processed items `[x]` and reflect in TODO.md
4. Read `toClaude/TODO.md` and resume from the next incomplete step

Never skip step 1.

---

# 📁 Single Source of Truth

- `TODO.md` is the ONLY file where task status (`[x]`) is tracked.
- `demo_guide.md` is for user-facing test scenarios only.
