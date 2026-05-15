# sim_v2 — Two-Engine Plugin Framework

Section 4 verification 의 sim-redesign 결과. Phase α (`backend/modeling/sim_verify/`, archived via `phase-alpha-snapshot` git tag) 의 successor.

## 개요

System-agnostic plugin framework — Java source 의 deterministic Python twin 합성 + LLM-based recommendation 의 two-engine architecture.

```
sim_v2/
├── core/                          # Framework core (Tier 1, stable contract — ADR-013)
│   ├── synthesizer/               # Java AST → Python twin (ADR-001)
│   │   ├── emitters/              # 8 dispatch_kind generic emitter (ADR-006)
│   │   ├── dispatchers/           # Polymorphic dispatch + plugin extension registry
│   │   ├── annotations/           # Annotation processing (ADR-007)
│   │   ├── aop/                   # @Aspect weaving (ADR-008)
│   │   └── bytecode/              # CGLib pattern (ADR-009)
│   ├── verification/              # Deterministic verification (R3-R5)
│   ├── recommendation/            # LLM-based proposal (UC4-UC6)
│   │   ├── providers/             # LLM-agnostic abstraction (ADR-012)
│   │   ├── defenses/              # 4-layer defense (ADR-005)
│   │   └── anti_patterns/         # Anti-pattern catalog (Phase α lessons)
│   ├── integrator/                # Two-Engine substrate (ADR-003)
│   ├── ontology/                  # 5-layer ontology API
│   │   └── schema_layer/          # Schema Layer (ADR-004, 신규)
│   └── contracts/                 # Generic Java contract (Spring/JPA/TX/Numeric)
├── plugins/                       # Per-system plugin (Tier 2)
│   ├── v2-slab-design/            # onTong slab manufacturing (Phase α successor)
│   ├── broadleaf/                 # Broadleaf Commerce community v6.x
│   └── banking/                   # Banking loan origination (가상 system)
├── tests/                         # Test suites
└── demos/                         # UC1/UC2/UC3 풀 시연
```

## Documentation

Sprint plan, ADRs, sub-design, lessons:
- `toClaude/modeling/section4-verification/sim-redesign/spec.md` — framework spec
- `toClaude/modeling/section4-verification/sim-redesign/implementation-plan.md` — W1-W20 sprint task breakdown
- `toClaude/modeling/section4-verification/sim-redesign/ADR-001` ~ `ADR-013` (13 ADR)
- `toClaude/modeling/section4-verification/sim-redesign/lessons/phase-alpha-*.md` (5 lessons)
- `toClaude/modeling/section4-verification/sim-redesign/V2-MIGRATION.md` / `BROADLEAF-ONBOARDING.md` / `BANKING-DESIGN.md`

## Status

Implementation phase 시작 (2026-05-13). Track A (v2 verification) + Track B (framework generalization) 병행. 16-20w sprint over 6-12 month.

## Phase α 의 archive

Phase α 산출물 (4 runtime substrate, 27 idiom cards, 5 fixture, oracle differ, gap report) 는 git tag `phase-alpha-snapshot` 에 보존:

```bash
git show phase-alpha-snapshot:backend/modeling/sim_verify/runtime/bigdecimal.py
git show phase-alpha-snapshot:toClaude/modeling/section4-verification/idioms/README.md
```

폐기 결정: ADR-010 (D2 확정). Phase α 의 학습은 `sim-redesign/lessons/phase-alpha-*.md` 5 lesson 으로 추출.
