"""Anti-pattern catalog — 5 entries derived from Phase α lessons (ADR-005 §Defense Layer 2).

각 anti-pattern = "Recommendation Engine 의 LLM output 에서 검출되어야 할 패턴".
ADR-005 의 4-layer defense 중 Layer 2 (output validation) 의 자동 검사 source.

Source lessons:
    Lesson 1 (phase-alpha-known-divergence.md) — 5 mismatch
    Lesson 2 (phase-alpha-idiom-cards.md)      — over-categorization
    Lesson 3 (phase-alpha-manual-twin.md)      — silent drift (negative scale 등)
    Lesson 4 (phase-alpha-facade.md)           — facade over-fit
    Lesson 5 (phase-alpha-fixture.md)          — fixture metadata 부재

Public API:
    AntiPattern — dataclass (id + signal_pattern + rationale + severity + lesson_ref)
    AntiPatternHit — scan() 의 hit 결과
    AntiPatternScanner — scan() entry point
    DEFAULT_CATALOG — module-level singleton catalog
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

Severity = Literal["INFO", "WARN", "ERROR"]


@dataclass(frozen=True)
class AntiPattern:
    """Recommendation output 에서 검출되어야 할 anti-pattern."""
    id:             str
    title:          str
    lesson_ref:     str       # "L1" .. "L5"
    severity:       Severity
    signal_pattern: str       # regex (검색 대상: emitter output / LLM proposal)
    rationale:      str       # 사람 readable 설명
    remediation:    str = ""  # 어떻게 수정할지 hint


@dataclass(frozen=True)
class AntiPatternHit:
    pattern_id: str
    severity:   Severity
    match:      str
    position:   int
    lesson_ref: str
    rationale:  str = ""


# ─────────────────────────────────────────────────────────────────────────────
# Lesson 1 — 5 KNOWN_DIVERGENCE entries
# ─────────────────────────────────────────────────────────────────────────────

LESSON_1_KNOWN_DIVERGENCE: tuple[AntiPattern, ...] = (
    AntiPattern(
        id="phase_alpha_bigdecimal_class_vs_function",
        title="BigDecimal class call (idiom) vs bd() function (runtime)",
        lesson_ref="L1",
        severity="ERROR",
        signal_pattern=r"\bBigDecimal\s*\(",
        rationale=(
            "Phase α α1/α2 mismatch — α1 runtime exposes `bd()` factory function; "
            "α2 idiom cards used `BigDecimal(...)` class constructor → NameError at exec time."
        ),
        remediation="Use plugin contract's JavaBigDecimal class (core/contracts/base.py) or bd() function consistently.",
    ),
    AntiPattern(
        id="phase_alpha_mathcontext_namespace_vs_constants",
        title="MathContext.DECIMAL64 namespace vs module constants",
        lesson_ref="L1",
        severity="ERROR",
        signal_pattern=r"\bMathContext\s*\.",
        rationale=(
            "α1 runtime exposes DECIMAL64_PRECISION/DECIMAL64_ROUNDING as module constants; "
            "α2 cards referenced `MathContext.DECIMAL64` namespace → NameError."
        ),
        remediation="Reference DECIMAL64 (NamedTuple) from backend.sim_v2.core.contracts.base.",
    ),
    AntiPattern(
        id="phase_alpha_roundingmode_enum_vs_constants",
        title="RoundingMode enum vs ROUND_* module constants",
        lesson_ref="L1",
        severity="ERROR",
        signal_pattern=r"\bRoundingMode\s*\.",
        rationale=(
            "α1 used decimal.ROUND_FLOOR etc. constants; α2 used RoundingMode.FLOOR enum form → NameError."
        ),
        remediation="Use RoundingMode Enum from core.contracts.base (Java-mirror form).",
    ),
    AntiPattern(
        id="phase_alpha_sdconstants_namespace_vs_imports",
        title="SdConstants namespace vs module-level imports",
        lesson_ref="L1",
        severity="ERROR",
        signal_pattern=r"\bSdConstants\s*\.",
        rationale=(
            "α1 exposed POS_SM, POS_HR as module constants; α2 used SdConstants.POS_SM → NameError."
        ),
        remediation="Use system-specific namespace class via plugin contract.domain_namespace() lookup.",
    ),
    AntiPattern(
        id="phase_alpha_validationresult_missing_implementation",
        title="ValidationResult dataclass referenced but not implemented",
        lesson_ref="L1",
        severity="ERROR",
        signal_pattern=r"\bValidationResult\s*\.\s*(?:fail|ok|warn)",
        rationale=(
            "α2 cards referenced ValidationResult.fail(...) builder; α1 never implemented it → NameError."
        ),
        remediation="Declare ValidationResult in plugin contracts (e.g., plugins/v2_slab_design/contracts/validation.py).",
    ),
)


# ─────────────────────────────────────────────────────────────────────────────
# Lesson 2-5 — one entry each
# ─────────────────────────────────────────────────────────────────────────────

LESSON_2_OVER_CATEGORIZATION = AntiPattern(
    id="phase_alpha_emitter_over_categorization",
    title="Sub-slot proliferation that obscures plugin scope decisions",
    lesson_ref="L2",
    severity="WARN",
    # 27 cards 의 sub-slot 의 over-fit signal — e.g., body.persist 가 body.repository_save 의 sub
    signal_pattern=r"#\s+TODO:\s+specialize\s+(?:sub-slot|atomic)",
    rationale=(
        "Phase α 27 cards 중 21/27 가 slab-specific atomic — emitter sub-slot 의 over-categorization. "
        "Plugin scope decision (core vs plugin) 의 first-class artifact 부재."
    ),
    remediation="Promote system-agnostic part to core/synthesizer/emitters/; localize specifics to plugins/<sys>/atoms/.",
)

LESSON_3_SILENT_DRIFT = AntiPattern(
    id="phase_alpha_silent_negative_scale_reject",
    title="Hand-crafted twin silent drift — restrictive guard (negative scale rejected)",
    lesson_ref="L3",
    severity="WARN",
    # 사람이 짠 helper 의 silent NotImplementedError signal
    signal_pattern=r"raise\s+NotImplementedError\s*\(\s*[\"']negative\s+scale",
    rationale=(
        "anchor-gaps Gap E-3 — α1 bigdecimal.bd_set_scale 가 scale<0 을 silently reject. "
        "v2 codebase 미사용이라 silent. 다른 도메인 적용 시 발현."
    ),
    remediation="Implement Java negative scale semantics (1000-unit truncation) or document explicit limit.",
)

LESSON_4_FACADE_OVER_FIT = AntiPattern(
    id="phase_alpha_facade_over_fit",
    title="Facade approach over-fit to one system (reusability < 30% across systems)",
    lesson_ref="L4",
    severity="WARN",
    # Facade 가 single-system specifics 흡수 — slab-only constants in generic-named class
    signal_pattern=r"^\s*class\s+\w*Facade\b",
    rationale=(
        "Phase α 4 facade module (bigdecimal/exception/plant_cd/lookup) — 3-system stress test 시 "
        "재사용성 20-30% only. Generic Java contract base + plugin override pattern 필요."
    ),
    remediation="Inherit from core.contracts.base.JavaContract + override system-specific in plugin/.",
)

LESSON_5_FIXTURE_NO_METADATA = AntiPattern(
    id="phase_alpha_fixture_no_metadata",
    title="Fixture without tolerance / scenario_intent metadata",
    lesson_ref="L5",
    severity="WARN",
    # Tolerance hardcode signal — Phase α scripts/section4_oracle_diff.py 의 abs_tol=1e-6 등
    signal_pattern=r"\babs_tol\s*=\s*1e-\d+|\brel_tol\s*=\s*1e-\d+",
    rationale=(
        "Phase α scripts/section4_oracle_diff.py — abs_tol=1e-6 / rel_tol=1e-9 hardcode. "
        "Per-fixture metadata.toml 의 per-action override 부재. 21-step cumulative drift 의 silent risk."
    ),
    remediation="Define tolerance in fixtures/<id>/metadata.toml under [tolerance] (default + per-action override).",
)


# ─────────────────────────────────────────────────────────────────────────────
# Default catalog — 9 entries total (5 L1 + 4 L2-L5)
# ─────────────────────────────────────────────────────────────────────────────

DEFAULT_CATALOG: tuple[AntiPattern, ...] = (
    *LESSON_1_KNOWN_DIVERGENCE,
    LESSON_2_OVER_CATEGORIZATION,
    LESSON_3_SILENT_DRIFT,
    LESSON_4_FACADE_OVER_FIT,
    LESSON_5_FIXTURE_NO_METADATA,
)


class AntiPatternScanner:
    """Scan source / proposal text for anti-pattern hits."""

    def __init__(self, catalog: tuple[AntiPattern, ...] | None = None) -> None:
        self._catalog = catalog or DEFAULT_CATALOG
        self._compiled = [
            (ap, re.compile(ap.signal_pattern, re.MULTILINE))
            for ap in self._catalog
        ]

    @property
    def catalog(self) -> tuple[AntiPattern, ...]:
        return self._catalog

    def scan(self, source: str) -> list[AntiPatternHit]:
        hits: list[AntiPatternHit] = []
        for ap, pattern in self._compiled:
            for match in pattern.finditer(source):
                hits.append(AntiPatternHit(
                    pattern_id=ap.id,
                    severity=ap.severity,
                    match=match.group(0),
                    position=match.start(),
                    lesson_ref=ap.lesson_ref,
                    rationale=ap.rationale,
                ))
        return hits

    def has_errors(self, source: str) -> bool:
        return any(h.severity == "ERROR" for h in self.scan(source))


__all__ = [
    "AntiPattern",
    "AntiPatternHit",
    "AntiPatternScanner",
    "DEFAULT_CATALOG",
    "LESSON_1_KNOWN_DIVERGENCE",
    "LESSON_2_OVER_CATEGORIZATION",
    "LESSON_3_SILENT_DRIFT",
    "LESSON_4_FACADE_OVER_FIT",
    "LESSON_5_FIXTURE_NO_METADATA",
    "Severity",
]
