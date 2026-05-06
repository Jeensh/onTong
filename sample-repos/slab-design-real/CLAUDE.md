# slab-design — Legacy Modernization Demo Codebase

## ⚠️ READ THIS FIRST

**This project is a fixture, not production code.** It exists to be analyzed, not improved.

It is a deliberately built demo of a legacy Java / Spring Boot system from a steel-manufacturing SCM domain (slab design). It serves as the **"victim" codebase** for a legacy modernization tool being demoed at a 사내 해커톤.

The hackathon tool does:
1. **온톨로지 매핑** — same domain concept across non-standardized columns/fields.
2. **영향도 분석** — trace impact of a domain rule change across modules.
3. **샌드박스 시뮬레이션** — generate code variants, run, compare.

This codebase is the input. **Do not "fix" the legacy mess.** It is intentional drama DNA.

## What this means for you (Claude Code)

When working in this repo:

| ✅ Do | ❌ Don't |
|------|---------|
| Preserve the messy column names (e.g., `PRODUCT_TYPE_CD` vs `PRODUCT_NAME_CD` vs `PRODUCT_KIND_CD` for the same concept) | Standardize names "to clean up" |
| Keep commented-out code with author + date signatures | Delete commented-out blocks |
| Keep `@author 김XX (2017-08-21)` style comments | Modernize javadoc |
| Keep deep-nested if/switch (4+ levels) | Refactor to early-return / strategy patterns |
| Keep magic numbers (e.g., `999999.999`, `0.95` defaults) | Extract to config |
| Keep duplicate logic across modules | DRY it up |
| Keep H/한 mixed naming and comments | English-ify everything |
| Keep reflection-based JPO ↔ Entity mapping in `SDOrderLogic` | "Modernize" to MapStruct/manual mapping |

If asked to add a feature, follow existing patterns (including the messy ones). If asked to demonstrate something for the hackathon, see `toClaude/scenarios.md`.

## Project structure

4-module Maven multi-module:

```
slab-design/
├── slab-design-boot/      # Spring Boot 진입점, application.yml
├── slab-design-facade/    # REST API (@RestController)
├── slab-design-feature/   # 비즈니스 로직 (designer, driver, action, service)
└── slab-design-store/     # JPA/MyBatis (jpo, entity, repository, logic)
```

Stack:
- Java 21 + Spring Boot 3.4
- Spring Data JPA (Oracle dialect for compile-time only — no actual DB)
- Maven Wrapper (`./mvnw.cmd`)

## What's actually demo-able

This is a **static artifact** — it builds (`mvnw compile` → BUILD SUCCESS) and the static analysis works. There is **no runtime** (no Oracle, no Kafka, no real data). The hackathon tool generates simulation code and runs it against this codebase's models, so runtime fidelity is not required.

**One REST endpoint exists** for visual demo only (won't actually return data without a DB):
- `POST /api/sd/working/batch?cmpCd=K&orgCd=K01` — entry to the 21-step slab design algorithm

## Where to look first

| You want to understand... | Start here |
|--------------------------|------------|
| What this is for | `toClaude/PROJECT_OVERVIEW.md` |
| The 21-step algorithm | `toClaude/ALGORITHM.md` + `slab-design-feature/.../designer/SdDesigner.java` |
| Drama DNA seeds (the "mess") | `toClaude/DRAMA_DNA.md` |
| Demo scenarios for the video | `toClaude/scenarios.md` |
| Table definitions | `toClaude/sd-tables.md` |
| Architecture rationale | `toClaude/architect.md` |
| Build/run instructions | `README.md` |

## Build

```bash
$env:JAVA_HOME = "C:\Program Files\Microsoft\jdk-21.0.10.7-hotspot"
.\mvnw.cmd compile         # BUILD SUCCESS expected
.\mvnw.cmd package          # full build (skips tests — none exist)
```

## Domain glossary

For the steel-manufacturing terms used throughout the code:

| Term | Meaning |
|------|---------|
| 슬랩 (slab) | Intermediate steel product — output of 제강(SM) → input to 열연(HR) |
| 주문 (order) | Customer order; one order can produce multiple slabs |
| 강종 (grade) | Steel chemistry grade |
| 품종/품명 (product) | Product category (intentionally messy: 3 different field names) |
| 실수율 (productivity / yield) | Process yield (output/input ratio); cumulative across processes |
| 단중 (unit weight) | Weight per piece (kg) |
| 포장단중 (packaging weight) | Customer's packaging unit weight constraint |
| 8 공정 | SM, HR, HRF, CR, ANL1, ANL2, GAL, CRF — production process chain |
| confirmedPlantCd | 8-char string; each char = plant code for that process; `' '` = inactive |
| 회사·소 | Company-org composite key on every table |
| EDGING | Slab-to-strip width transformation rule with `*` wildcard fallback |

## When in doubt

If the user asks "should I refactor X?" the answer is almost always **no** — refactoring removes drama DNA. If the user asks the hackathon tool to do something, that's different — generated code is fine to be clean.
