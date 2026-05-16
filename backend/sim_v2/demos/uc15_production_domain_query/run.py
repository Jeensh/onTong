"""UC15 — Production domain ↔ code query (W45).

The 6th step in the production-wiring storyline:

    UC10  inspect            (read production code)
    UC11  translate          (code → Python, 100%)
    UC12  schema onboard     (JPA → SchemaModel)
    UC13  cross-layer        (persist + query)
    UC14  drift detect       (snapshot diff)
    UC15  domain ↔ code  ← here

Production already carries authoring artifacts (`business_terms`, `actions`,
`anchor_bindings`) — Section 2's modeling pipeline produced them. UC15 binds
those into queryable cross-layer primitives:

    find_actions_for_business_term(term_fqn)
    find_actions_for_method(method_fqn)
    find_anchor_bindings_for_action(action_fqn)

Demo for each repo: count terms / actions / bindings, then sample one of each
query primitive on real production FQNs.

Run from repo root:
    .venv/bin/python -m backend.sim_v2.demos.uc15_production_domain_query.run
"""
from __future__ import annotations

import sys
from collections import defaultdict
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from backend.sim_v2.core.ontology.domain_layer.production_domain_loader import (
    ActionView,
    AnchorBindingView,
    BusinessTermView,
    load_actions,
    load_anchor_bindings,
    load_business_terms,
)
from backend.sim_v2.demos.uc10_production_inspector.run import (
    PRODUCTION_DB_PATH,
    open_readonly_session,
)


DEFAULT_REPOS: tuple[str, ...] = (
    "synthetic-5k",
    "slab-design-real-v2",
    "slab-design-real",
)


# ─────────────────────────────────────────────────────────────────────────────
# Query primitives — exposed for tests
# ─────────────────────────────────────────────────────────────────────────────


def find_actions_for_business_term(
    actions: list[ActionView], term_fqn: str,
) -> list[ActionView]:
    """All actions declared on the given BusinessTerm FQN."""
    return [a for a in actions if a.declared_on_term == term_fqn]


def find_actions_for_method(
    actions: list[ActionView], method_fqn: str,
) -> list[ActionView]:
    """All actions whose description references the given code method FQN.

    Uses the parsed `code_method_fqn` field populated by the loader.
    """
    return [a for a in actions if a.code_method_fqn == method_fqn]


def find_anchor_bindings_for_action(
    bindings: list[AnchorBindingView], action_fqn: str,
) -> list[AnchorBindingView]:
    return [b for b in bindings if b.target_action_fqn == action_fqn]


# ─────────────────────────────────────────────────────────────────────────────
# Report
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class DomainQueryReport:
    repo_id:                  str
    term_count:               int
    action_count:             int
    actions_with_method_fqn:  int
    binding_count:            int
    sample_term:              BusinessTermView | None = None
    sample_action:            ActionView | None = None
    sample_method_fqn:        str | None = None
    actions_for_sample_term:  int = 0
    actions_for_sample_meth:  int = 0
    bindings_for_sample_act:  int = 0


def survey_repo(session: Session, repo_id: str) -> DomainQueryReport:
    terms = load_business_terms(session, repo_id)
    actions = load_actions(session, repo_id)
    bindings = load_anchor_bindings(session, repo_id)

    actions_with_fqn = sum(1 for a in actions if a.code_method_fqn)

    sample_term: BusinessTermView | None = None
    sample_action: ActionView | None = None
    sample_method_fqn: str | None = None
    actions_for_sample_term = 0
    actions_for_sample_meth = 0
    bindings_for_sample_act = 0

    # Pick the first term that *some* action declares on — yields a non-empty
    # answer for the "term → actions" query
    by_term: dict[str, int] = defaultdict(int)
    for a in actions:
        if a.declared_on_term:
            by_term[a.declared_on_term] += 1
    if by_term:
        most_common_term = max(by_term, key=by_term.get)  # type: ignore[arg-type]
        sample_term = next((t for t in terms if t.fqn == most_common_term), None)
        actions_for_sample_term = by_term[most_common_term]

    # Pick the first action with a parsed method FQN — yields a non-empty
    # answer for the "method → actions" query
    sample_action = next((a for a in actions if a.code_method_fqn), None)
    if sample_action and sample_action.code_method_fqn:
        sample_method_fqn = sample_action.code_method_fqn
        actions_for_sample_meth = len(find_actions_for_method(actions, sample_method_fqn))
        bindings_for_sample_act = len(find_anchor_bindings_for_action(bindings, sample_action.fqn))

    return DomainQueryReport(
        repo_id=repo_id,
        term_count=len(terms),
        action_count=len(actions),
        actions_with_method_fqn=actions_with_fqn,
        binding_count=len(bindings),
        sample_term=sample_term,
        sample_action=sample_action,
        sample_method_fqn=sample_method_fqn,
        actions_for_sample_term=actions_for_sample_term,
        actions_for_sample_meth=actions_for_sample_meth,
        bindings_for_sample_act=bindings_for_sample_act,
    )


# ─────────────────────────────────────────────────────────────────────────────
# CLI entry point
# ─────────────────────────────────────────────────────────────────────────────


def _banner(text_line: str) -> None:
    print("─" * 78)
    print(text_line)
    print("─" * 78)


def main(repos: tuple[str, ...] = DEFAULT_REPOS) -> int:
    print("=" * 78)
    print("UC15 — Production domain ↔ code query (W45)")
    print("=" * 78)
    print()

    session = open_readonly_session()
    if session is None:
        print(f"  {PRODUCTION_DB_PATH} not found — skipping (CI / fresh checkout)")
        return 0

    try:
        totals = {"term": 0, "action": 0, "with_fqn": 0, "binding": 0}
        for repo_id in repos:
            report = survey_repo(session, repo_id)
            _banner(f"Repo: {report.repo_id}")
            print(f"  Business terms : {report.term_count}")
            print(f"  Actions        : {report.action_count} "
                  f"(with parsed method FQN: {report.actions_with_method_fqn})")
            print(f"  Anchor binds   : {report.binding_count}")
            if report.sample_term:
                short = report.sample_term.fqn
                if len(short) > 40:
                    short = short[:38] + "…"
                print(f"  Query 1 (term → actions):")
                print(f"    term         {short} ({report.sample_term.label})")
                print(f"    → actions    {report.actions_for_sample_term}")
            if report.sample_method_fqn:
                short = report.sample_method_fqn
                if len(short) > 60:
                    short = "…" + short[-58:]
                print(f"  Query 2 (method → actions):")
                print(f"    method       {short}")
                print(f"    → actions    {report.actions_for_sample_meth}")
            if report.sample_action:
                short_action = report.sample_action.fqn
                if len(short_action) > 40:
                    short_action = short_action[:38] + "…"
                print(f"  Query 3 (action → bindings):")
                print(f"    action       {short_action}")
                print(f"    → bindings   {report.bindings_for_sample_act}")
            print()

            totals["term"]     += report.term_count
            totals["action"]   += report.action_count
            totals["with_fqn"] += report.actions_with_method_fqn
            totals["binding"]  += report.binding_count

        _banner("Aggregate (all repos)")
        print(f"  Terms                       : {totals['term']}")
        print(f"  Actions                     : {totals['action']}")
        print(f"  Actions with parsed method  : {totals['with_fqn']}")
        print(f"  Anchor bindings             : {totals['binding']}")
        print()
        print("✓ Domain ↔ code cross-layer queries operational on real production data")
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    sys.exit(main())
