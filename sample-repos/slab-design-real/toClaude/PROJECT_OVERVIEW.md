# PROJECT_OVERVIEW

## What this codebase is

`slab-design` is a **deliberately built demo** of a Korean steel-manufacturing SCM legacy system. It implements a 21-step slab design algorithm with intentional drama DNA — the kinds of patterns a legacy modernization tool needs to identify and analyze.

It is a **fixture for a hackathon demo**, not real production code.

## Why it exists

Anthropic 사내 해커톤 ('25) 출품작:

> **Legacy Modernization Tool** combining:
> - 온톨로지 매핑 (cross-table same-concept detection)
> - 영향도 분석 (rule-change impact tracing)
> - 샌드박스 시뮬레이션 (generated variants comparison)

The tool needs a "victim" codebase to analyze in the demo video. `slab-design` is that victim.

The hackathon tool is ~60% complete. This codebase is ~100% complete (algorithm wise — see scope below).

## What's implemented vs. not

### ✅ Implemented

- **All 12 tables** as JPA entities + JPOs + composite PKs (회사·소)
  - 4 ORDER tables (Os/Om/Qd/Chemical)
  - 4 spec tables (CastSpec, HrSpec, EdgingGroup, EdgingSpec)
  - 4 rule masters (CustomerStd, HrMinWgt, HrMaxWgt, ProductivityStd)
  - 1 result + 1 history (SlabResult, SlabDesignHist)
- **21-step algorithm** end-to-end (`SdDesigner`):
  - Phase 1: 5-stage validation (DG001–005), product classification, working-field hydration
  - Phase 2: steps 1–7 (one-shot), 8–15 (A-a 분할 fallback loop), 16–19 (final ranges), 20 (save), 21 (history)
- **Reflection-based JPO ↔ Entity mapping** (`SDOrderLogic`) — drama DNA
- **One REST endpoint** (`POST /api/sd/working/batch`)
- **DG error code system** — 5 validation (DG001–005) + 9 algorithm (DG101–109)
- **Cumulative productivity calculation** across active processes (8-char `confirmedPlantCd`)
- **2D sheet lookup** for HR_MIN_WGT / HR_MAX_WGT
- **EDGING `*` wildcard fallback** for spec lookup
- **12-digit zero-padded slab number sequence**
- **Maven multi-module build**: `mvnw compile` → BUILD SUCCESS

### 🚫 Not implemented (by design)

- **No DB** — Oracle is compile-time dialect only
- **No tests** — Maven `package` skips tests (none exist)
- **No Kafka** — listed in spec but not wired
- **No real runtime** — endpoint will throw on actual call (no DB connection)
- **Step 14** (제품단중 최대화 모드) — explicitly skipped per user direction

The hackathon tool generates simulation harness code, so runtime fidelity is not required for the demo.

## Domain in 60 seconds

| Concept | Meaning |
|---------|---------|
| 슬랩 (slab) | Intermediate steel; output of 제강(SM) → input to 열연(HR) |
| 주문 (order) | Customer order; can produce 1-N slabs |
| 8 공정 | SM, HR, HRF, CR, ANL1, ANL2, GAL, CRF (production chain) |
| confirmedPlantCd | 8-char string per order; one char = plant for that process; `' '` = inactive |
| 실수율 (productivity) | Process yield. Cumulative = product of yields of active processes |
| 단중 (unit weight) | Weight per slab piece (kg) |
| EDGING | Slab→strip width transform rule, with wildcard `*` fallback |
| 회사·소 | Composite primary-key prefix on every table (`cmpCd`+`orgCd`) |

## How to demo this

The drama DNA shines in 5 picked scenarios — see [`scenarios.md`](scenarios.md). For video:

1. **#1 비표준 컬럼명** — same concept, 3 different column names across tables
2. **#3 우선순위 룰** — DG001–005 short-circuit ordering matters
3. **#5 누적 실수율** — change one productivity value → impact across all 8 processes
4. **#8 A-a 루프** — A-step fail → a-step fallback → re-enter A
5. **#10 원본/조정** — `_1` suffix duplication on SLAB_RESULT

## Module layering

```
boot ──depends-on──▶ facade ──depends-on──▶ feature ──depends-on──▶ store
                                                                     │
                                                              JPO + Entity + Repo
```

`feature` knows nothing about HTTP. `facade` knows nothing about JPA. `store` is pure data.

## Repo layout summary

```
slab-design/
├── CLAUDE.md                 ← Read first if you're Claude Code
├── README.md                 ← Build/run
├── pom.xml                   ← parent POM
├── mvnw.cmd / mvnw           ← Maven Wrapper
├── slab-design-boot/         ← Spring Boot 진입점
├── slab-design-facade/       ← REST API
├── slab-design-feature/      ← 알고리즘 + 비즈니스 로직
│   └── src/main/java/com/example/slabdesign/feature/sd/
│       ├── designer/         ← SdDesigner (orchestrator)
│       ├── driver/           ← SdDriver (batch flow)
│       └── process/
│           ├── working/      ← action/, service/, wrapper/
│           ├── std/          ← std service lookups
│           └── history/      ← hist 적재
├── slab-design-store/        ← JPA, JPO, Entity, Repo
└── toClaude/                 ← Documentation for Claude Code
```
