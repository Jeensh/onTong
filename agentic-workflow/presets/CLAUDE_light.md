# Agentic Workflow — Light Preset
# 적합: 1~2일, 버그픽스, 소규모 기능 추가, 리팩터링

---

# 📋 Task Tracking

- `toClaude/TODO.md` is the Single Source of Truth for task status.
- Mark completed tasks with `[x]` immediately after finishing.
- When the user requests additional changes, add new rows to TODO.md in the SAME turn.

---

# 🔄 Session Start

At the start of every new session:

1. Read `toClaude/TODO.md`
2. Resume from the next incomplete `[ ]` task

---

# ✅ Completion Rule

A task is complete when:
1. Code is implemented
2. Basic verification passes (run the code, check for errors)
3. TODO.md is updated with `[x]`
4. Report the result to the user
