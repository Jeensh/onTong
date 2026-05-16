# Agent Shared Context — Sim-redesign Macro Exploration

You are one of 4 agents exploring a design problem in parallel for onTong's Section 4 simulation system redesign. Three other agents are exploring different perspectives simultaneously and don't see your work. Your output will be synthesized later by the main agent.

## Files to read first (in this order, briefly — each is short)

1. `toClaude/modeling/section4-verification/sim-redesign/SESSION-RESUME.md` — full handoff (Sections 1-5 critical: user requirements + Phase α state + initial candidate approaches)
2. `toClaude/modeling/section4-verification/sim-redesign/ADR-001-python-twin.md` — **CRITICAL** new constraint: Python = Java executable twin, no human edits, regenerable
3. `toClaude/modeling/section4-verification/anchor-gaps.md` — current ontology gaps (Gap A-F)
4. `~/.claude/projects/-Users-donghae-workspace-ai-onTong/memory/feedback_simulation_design.md` — no MVP / 풀 시연 필수 (CRITICAL)
5. `~/.claude/projects/-Users-donghae-workspace-ai-onTong/memory/project_decisions_v4_action.md` — v4 architecture (Code/Domain/Mapping/Simulation 4-layer)
6. Briefly: `backend/modeling/sim_verify/runtime/` — Phase α Python substrate (BigDecimal/AlgorithmException/etc.)
7. Concrete example to use in your worked example: `sample-repos/slab-design-real_v2/slab-design-feature/src/main/java/com/example/slabdesign/feature/sd/process/working/action/SdThicknessAction.java`
8. Reference data: `sqlite3 data/ontology.db` — tables: `actions`, `realizations`, `anchor_bindings`, `type_realizations`, `business_terms`, `business_rules`, `code_methods`, `code_types`
9. Idiom card examples: `toClaude/modeling/section4-verification/idioms/P01-body.compute.md`, `P02-body.set_output.md`

## DO NOT base on

`toClaude/modeling/section4-verification/sim-redesign/Q1-trace-granularity.html` — that was a sub-question superseded by ADR-001. Re-think from macro. (You may glance at it for context but don't accept its option framing.)

## User requirements (R1-R5)

- **R1**: Ontology/mapping is precondition for simulation. Section 2 산출물 (ontology DB) = ground truth, Section 4 consumes.
- **R2**: Simulator must self-aware of ontology gaps — "이 부분이 ...가 불명확함" 을 표면화하면서 코드 작성. 빈틈을 숨기지 말 것.
- **R3**: Python execution → same output as Java (bit-level).
- **R4**: Same processing process (코드 형태 무관, 처리 단계 시퀀스 일치).
- **R5**: Compare before/after Java source modifications (v2 vs v2').

## Critical constraints

- **Twin concept (ADR-001)**: Python = Java execution twin, regenerable, no human edits. Python exists solely because Spring/JPA/DB etc. make Java runtime hard to spin up.
- **No MVP**: 풀 시연 보장. No "MVP first, evolve later" proposals. Full design now.
- **B1**: 무한 토큰/서브에이전트 OK — depth over speed.

## Deliverable

Write a 1500-2000 word markdown design proposal to:
`/Users/donghae/workspace/ai/onTong/toClaude/modeling/section4-verification/sim-redesign/explorations/N-{perspective-name}.md`

The directory `explorations/` already exists.

### Required sections (use exactly these headers)

```markdown
# Perspective: {your perspective name}

## 1. Summary
(your design in 3 sentences)

## 2. Architecture
(components + data flow — ASCII diagram or table)

## 3. Synthesizer internals
(algorithm, what reads ontology, what produces Python — be code-grounded)

## 4. R1-R5 satisfaction
(table: requirement | mechanism | evidence/file)

## 5. Twin concept compliance
(how is Python regenerable, deterministic, free of human edits)

## 6. Concrete worked example — SdThicknessAction.execute()
Show step-by-step:
- Input ontology rows (actions, realizations, anchor_bindings for action.scm.thickness_실행 — 5 anchors: invalid_check L43, activation_check L47, body.service_lookup L52, body.service_lookup L57, body.set_output L70)
- Synthesis/translation steps
- Output Python code (full method)
- Expected runtime behavior

## 7. R2 gap surface
Where do these appear in Python output?
- Gap A: 2 abstract methods (action.scm.run, action.scm.슬랩설계_실행)
- Gap C: 14 unconfirmed type_realizations (auto, conf 0.5-0.7)
Show concrete Python output snippets for each gap type.

## 8. KNOWN_DIVERGENCE prevention
How does your design prevent α's 5종 mismatch?
- BigDecimal (class vs bd() factory)
- MathContext (enum vs DECIMAL64_* consts)
- RoundingMode (enum vs decimal.ROUND_*)
- SdConstants (namespace vs POS_SM constants)
- ValidationResult (dataclass vs none)

## 9. R5 workflow
Step-by-step: Java v2 modified → ontology re-derived → Python re-synthesized → run both → diff. Show the human-facing artifact at each step.

## 10. Failure modes
When does your design fail? What user-visible error?

## 11. Honest weaknesses
What your design doesn't handle well. Be specific.
```

### Style rules

- Be concrete and code-grounded. Cite file paths, line numbers, ontology table names.
- Use markdown code blocks for Java / Python / SQL / pseudocode.
- Defend your perspective strongly — the skeptic agent will challenge it separately. Avoid hedging.
- 1500-2000 words. Quality > volume.

## How others differ

You'll be compared against three other perspectives. Don't worry about being orthogonal — they handle different concerns. Just commit fully to your assigned perspective.

The 4 perspectives are:
1. **Automation purist / full synthesis** — synthesizer owns everything, no human in Python loop, prevents KNOWN_DIVERGENCE by-construction
2. **Minimal twin / literal translation** — AST walk Java → Python statement-by-statement, ontology is auxiliary
3. **Phase α reuse / incremental bridge** — maximally reuse existing cards/runtime/oracle, bridge gaps
4. **Skeptic / risk analysis** — catalog risks of twin concept itself and each of above 3

The skeptic doesn't propose a design; it produces a risk catalog. Others propose designs.
