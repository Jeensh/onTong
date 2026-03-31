# 🚀 onTong - Knowledge-Fused Multi-Agent Platform (Agentic OS) for SCM

## 1. Context & Ultimate Goal

Your **core mission** is to build a **Planner-type Autonomous Reasoning AI Agent (Agentic OS)** for the manufacturing SCM domain. It solves the "black-box debugging hell" in cross-team MSA environments and bridges the knowledge gap between field operators and IT.

* **The Solution (The 3 Brains):** 1. **Business Brain:** Business rules and runbooks stored in a **Local Markdown Wiki**.
  2. **Code Brain:** Legacy Java/Spring runtime dependencies and AST tracked via the **Bloop** local search engine.
  3. **The Router Brain:** A central orchestrator that controls everything.

---

## 2. Tech Stack & Architecture Philosophy

You must respect the existing `gstack`, but you have the flexibility to propose the best AI framework for this job. **Simplicity and modularity are key.**

| Layer | Framework Guideline | Purpose & Reason |
|---|---|---|
| **AI Framework** | **Your Choice** (e.g., PydanticAI, LangChain, native OpenAI/Ollama clients, etc.) | Propose the simplest, most effective framework for Tool-use and Multi-Agent Orchestration. Structured I/O (like Pydantic models) is highly preferred to prevent parsing errors. |
| **Code Analyzer** | **Bloop** | Local AST parser tool. Use Bloop's API to trace deep Spring `@Autowired` dependency trees. |
| Backend | Python + FastAPI | Exposes Agent API and handles the Main Router. |
| Frontend | Next.js + TypeScript | 3-Pane UI layout (Tree Nav + Markdown Editor + AI Copilot chat). |

### The Orchestrator & Plugin System
Design a **"Tool/Agent Registry Plugin Architecture"**. The Main Router should analyze the user's natural language intent and route the task to the appropriate sub-agent (e.g., `WIKI_QA`, `SIMULATION`, `DEBUG_TRACE`). The architecture must allow adding new sub-agents with minimal code changes.

---

## 3. Core Sub-Agents (The Planner Roles)

Our agents execute Tools (Act) and validate hypotheses.

### 🧑‍💻 Agent A: Simulator & Optimizer (Future Prediction)
* **ReAct Loop:** Reads rules from the Wiki -> Executes a Python Simulator Tool -> Autonomously adjusts parameters if an error (e.g., DG320) occurs -> Returns the optimal result.

### 🧑‍💻 Agent B: Tracer & Debugger (Past Tracing)
* **Cross-checking:** Parses Git Commit history -> Calls **Bloop API Tool** to traverse Spring dependencies -> Executes validation queries on databases to pinpoint data mismatch boundaries.

---

## 4. 🛑 STRICT RULES for Claude Code Execution

1. **Structured Data First:** Even if you don't use a specific framework, ALL communications between Frontend, Backend, Router, and Sub-agents MUST use strictly typed schemas (e.g., Pydantic `BaseModel`). No raw text parsing for internal logic.
2. **Human-in-the-loop:** When an agent attempts an action that mutates state (e.g., `Write` to a local Wiki `.md` file), the backend must return a state requiring the UI to prompt the user with `[Accept / Reject]` buttons.
3. **Phased Implementation:** DO NOT build Agent A and Agent B right now. For **Phase 1**, focus 100% on building the **3-Pane UI** and the **Main Router with a Dummy Mock Tool** to prove the backbone routing works. Keep the architecture as simple as possible.