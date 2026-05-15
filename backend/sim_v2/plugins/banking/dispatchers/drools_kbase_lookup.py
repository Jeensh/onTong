"""banking.drools_kbase_lookup dispatcher — ADR-006 + BANKING-DESIGN.md §5.

Drools KIE container 의 fireAllRules() → Python decision tree emit.

Strong assumption: rule LHS = simple equality / range / DSL primitive.
Complex backward chaining (truth maintenance, forward inference) is
SIGNATURE_LOCKED — caller must extract specific rule semantics for emit.
"""
from __future__ import annotations

from typing import Any

from backend.sim_v2.core.synthesizer.dispatchers.registry import (
    DispatchContext,
    DispatcherBase,
    DispatchOutput,
)


def _render_drools_rule_branches(rules: list[dict[str, Any]]) -> str:
    """Render parsed Drools rules as Python if-elif chain.

    `rules` = simplified rule structure:
        [{"name": "...", "lhs": "...", "rhs": "..."}, ...]
    """
    if not rules:
        return "# no Drools rules — default approve\ndecision = 'APPROVED'"

    parts: list[str] = []
    for idx, rule in enumerate(rules):
        keyword = "if" if idx == 0 else "elif"
        name = rule.get("name", f"rule_{idx}")
        lhs = rule.get("lhs", "False")
        rhs = rule.get("rhs", "pass")
        parts.append(f"{keyword} {lhs}:  # rule: {name}\n    {rhs}")
    parts.append("else:\n    decision = 'APPROVED'  # default — no rule matched")
    return "\n".join(parts)


class DroolsKbaseLookupDispatcher(DispatcherBase):
    """banking.drools_kbase_lookup — KIE session fireAllRules → Python decision tree."""
    name = "banking.drools_kbase_lookup"
    dispatch_kind = "banking.drools_kbase_lookup"

    def synthesize(self, context: DispatchContext) -> DispatchOutput:
        kbase_name = context.call_site.get("kbase_name", "")
        # rules pre-parsed by Section 2 Drools extractor (W6+, currently caller-provided)
        rules = context.call_site.get("rules", [])

        if not kbase_name:
            return DispatchOutput(
                python_source=(
                    "# UNCLEAR: banking.drools_kbase_lookup requires kbase_name.\n"
                    "# SIGNATURE_LOCKED."
                ),
                signature_locked=True,
                notes=("kbase_name missing in call_site metadata",),
            )

        branches = _render_drools_rule_branches(rules)
        python_source = (
            f"# Drools KIE container '{kbase_name}' simulated as Python decision tree\n"
            f"# Strong-assumption: rules with simple LHS expressions. Complex chaining not supported.\n"
            f"decision = None\n"
            f"{branches}"
        )

        return DispatchOutput(
            python_source=python_source,
            notes=(
                f"DroolsKbaseLookupDispatcher — kbase={kbase_name!r}, rules={len(rules)}",
            ),
        )


__all__ = ["DroolsKbaseLookupDispatcher"]
