"""W53 — Framework-wide health report.

Single API that rolls up every verification gate the framework provides
(W41 translator + W47 action↔code + W49 idioms + W52 param signatures) into
one report. Useful for consumers who want a snapshot of cross-layer agreement
on a given repo.

Each gate contributes a `GateResult` carrying:
    name        — gate identifier
    applicable  — how many items the gate inspected
    verified    — how many passed
    rate        — verified / applicable (0.0 when applicable=0)
    findings    — short list of human-readable issues, capped for brevity

The aggregate `HealthReport` carries:
    gates           — per-gate results
    overall_rate    — average of per-gate rates over applicable gates
    is_healthy      — every applicable gate's rate ≥ HEALTH_THRESHOLD
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from backend.sim_v2.core.ontology.domain_layer.production_domain_loader import (
    load_actions,
)
from backend.sim_v2.core.synthesizer.java_translator import JavaToPythonTranslator
from backend.sim_v2.core.verification.action_method_verifier import verify_actions
from backend.sim_v2.core.verification.idiom_verifier import (
    DEFAULT_RULES as DEFAULT_IDIOM_RULES,
    verify_idioms,
)
from backend.sim_v2.core.verification.param_signature_verifier import (
    verify_action_param_signatures,
)
from backend.sim_v2.demos.uc11_production_translator.run import (
    fetch_methods,
    parse_method_declaration,
)


HEALTH_THRESHOLD: float = 0.80   # ratio per gate considered healthy
TRANSLATOR_SAMPLE_DEFAULT: int = 100


@dataclass(frozen=True)
class GateResult:
    name:        str
    applicable:  int = 0
    verified:    int = 0
    findings:    tuple[str, ...] = field(default_factory=tuple)

    @property
    def rate(self) -> float:
        return (self.verified / self.applicable) if self.applicable else 0.0

    @property
    def is_healthy(self) -> bool:
        if self.applicable == 0:
            return True   # nothing to check ⇒ vacuously healthy
        return self.rate >= HEALTH_THRESHOLD


@dataclass(frozen=True)
class HealthReport:
    repo_id:    str
    gates:      tuple[GateResult, ...]

    @property
    def overall_rate(self) -> float:
        applicable_rates = [g.rate for g in self.gates if g.applicable > 0]
        if not applicable_rates:
            return 0.0
        return sum(applicable_rates) / len(applicable_rates)

    @property
    def is_healthy(self) -> bool:
        return all(g.is_healthy for g in self.gates)


# ─────────────────────────────────────────────────────────────────────────────
# Per-gate evaluation
# ─────────────────────────────────────────────────────────────────────────────


def _gate_translator(
    session: Session, repo_id: str, sample_size: int,
) -> GateResult:
    methods = fetch_methods(session, repo_id, limit=sample_size)
    verified = 0
    findings: list[str] = []
    for m in methods:
        body = (m.get("body_text") or "").strip()
        if not body:
            continue
        try:
            node = parse_method_declaration(body)
        except Exception:
            findings.append(f"parse error: {m['fqn'][:60]}")
            continue
        if node is None:
            continue
        try:
            out = JavaToPythonTranslator().translate(node, indent=0)
        except Exception:
            findings.append(f"translator error: {m['fqn'][:60]}")
            continue
        if out.signature_locked:
            findings.append(f"locked: {m['fqn'][:60]}")
        else:
            verified += 1
    applicable = sum(1 for m in methods if (m.get("body_text") or "").strip())
    return GateResult(
        name="translator",
        applicable=applicable,
        verified=verified,
        findings=tuple(findings[:5]),
    )


def _gate_action_verification(session: Session, repo_id: str) -> GateResult:
    actions = load_actions(session, repo_id)
    if not actions:
        return GateResult(name="action_method_verification")
    verifications = verify_actions(session, actions)
    verified = sum(1 for v in verifications if v.status == "VERIFIED")
    counts = Counter(v.status for v in verifications)
    findings = tuple(
        f"{status}: {cnt}" for status, cnt in sorted(counts.items())
        if status != "VERIFIED"
    )[:5]
    return GateResult(
        name="action_method_verification",
        applicable=len(verifications),
        verified=verified,
        findings=findings,
    )


def _gate_param_signature(session: Session, repo_id: str) -> GateResult:
    actions = load_actions(session, repo_id)
    if not actions:
        return GateResult(name="param_signature")
    verifications = verify_action_param_signatures(session, actions)
    verified = sum(1 for v in verifications if v.status == "VERIFIED")
    findings: list[str] = []
    for v in verifications:
        if v.status in ("NAME_MISMATCH", "ARITY_MISMATCH"):
            findings.append(f"{v.status}: {v.action_fqn}")
    return GateResult(
        name="param_signature",
        applicable=len(verifications),
        verified=verified,
        findings=tuple(findings[:5]),
    )


def _gate_idiom_coverage(
    session: Session, repo_id: str, sample_size: int,
) -> GateResult:
    """Aggregate idiom-rule MATCH rate across the sampled methods.

    `applicable` is the *total* number of (rule, method) pairs where the Java
    pattern fired (across all rules). `verified` is the count of matches.
    """
    methods = fetch_methods(session, repo_id, limit=sample_size)
    total_applicable = 0
    total_match = 0
    findings: list[str] = []
    for m in methods:
        body = (m.get("body_text") or "").strip()
        if not body:
            continue
        try:
            node = parse_method_declaration(body)
        except Exception:
            continue
        if node is None:
            continue
        try:
            out = JavaToPythonTranslator().translate(node, indent=0)
        except Exception:
            continue
        if out.signature_locked:
            continue
        checks = verify_idioms(body, out.python_source, DEFAULT_IDIOM_RULES)
        for c in checks:
            if c.status == "MATCH":
                total_applicable += 1
                total_match += 1
            elif c.status == "VIOLATION":
                total_applicable += 1
                findings.append(f"{c.rule_name} violation in {m['fqn'][:50]}")
    return GateResult(
        name="idiom_coverage",
        applicable=total_applicable,
        verified=total_match,
        findings=tuple(findings[:5]),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────


def framework_health_check(
    session: Session,
    repo_id: str,
    *,
    translator_sample: int = TRANSLATOR_SAMPLE_DEFAULT,
    idiom_sample: int = TRANSLATOR_SAMPLE_DEFAULT,
) -> HealthReport:
    """Roll up every verification gate for `repo_id` into a single report."""
    gates = (
        _gate_translator(session, repo_id, translator_sample),
        _gate_action_verification(session, repo_id),
        _gate_param_signature(session, repo_id),
        _gate_idiom_coverage(session, repo_id, idiom_sample),
    )
    return HealthReport(repo_id=repo_id, gates=gates)


__all__ = [
    "GateResult",
    "HEALTH_THRESHOLD",
    "HealthReport",
    "framework_health_check",
]
