# slab-design

Demo legacy Java/Spring Boot codebase from a steel-manufacturing SCM domain (slab design — 제철 Slab 설계).

> **For Claude Code: see [`CLAUDE.md`](CLAUDE.md) first.** This is a fixture, not production code.

## What this is

A 4-module Maven project simulating a 21-step slab design algorithm with intentional "legacy mess" (non-standardized column names, deep nesting, commented-out code with author signatures, reflection-based DTO mapping). Built as the input fixture for a legacy-modernization tool demo.

## Stack

- Java 21
- Spring Boot 3.4
- Spring Data JPA (Oracle dialect — compile-time only)
- Maven (multi-module via Maven Wrapper)

## Modules

```
slab-design-boot/     ← Spring Boot main + application.yml
slab-design-facade/   ← REST controllers (@RestController)
slab-design-feature/  ← 비즈니스 로직 (designer, driver, action, service)
slab-design-store/    ← 영속성 (jpo, entity, repository, logic)
```

## Build

Requires JDK 21. Tested with Microsoft OpenJDK 21.

```powershell
$env:JAVA_HOME = "C:\Program Files\Microsoft\jdk-21.0.10.7-hotspot"
.\mvnw.cmd compile        # BUILD SUCCESS expected
.\mvnw.cmd package        # full build (no tests defined)
```

## Run (optional, for visual demo)

```powershell
.\mvnw.cmd -pl slab-design-boot spring-boot:run
```

The app starts but **has no database** — calling endpoints will fail at JPA layer. This is by design; the demo target is static analysis, not runtime.

One REST endpoint is wired for visual flow:

```
POST /api/sd/working/batch?cmpCd=K&orgCd=K01
```

## Documentation

| File | Purpose |
|------|---------|
| [`CLAUDE.md`](CLAUDE.md) | Instructions for Claude Code working in this repo |
| [`toClaude/PROJECT_OVERVIEW.md`](toClaude/PROJECT_OVERVIEW.md) | Why this exists, what to demo |
| [`toClaude/DRAMA_DNA.md`](toClaude/DRAMA_DNA.md) | Inventory of intentional legacy patterns |
| [`toClaude/ALGORITHM.md`](toClaude/ALGORITHM.md) | 21-step slab design algorithm |
| [`toClaude/scenarios.md`](toClaude/scenarios.md) | Demo scenarios for the hackathon video |
| [`toClaude/sd-tables.md`](toClaude/sd-tables.md) | Table/column definitions |
| [`toClaude/architect.md`](toClaude/architect.md) | Architecture rationale |
| [`toClaude/slab-design.md`](toClaude/slab-design.md) | Original spec / design notes |
