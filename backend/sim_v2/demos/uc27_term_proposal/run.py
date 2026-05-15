"""UC27 — LLM term proposal applied to UC24 PROPOSE_NEW_TERM steps (W61).

This is the **Recommendation Engine's first production application** —
the second engine of the Two-Engine framework finally meets real findings
surfaced by the Verification Engine.

Pipeline:
    UC23/W56-W57  detect return-type drift                   (deterministic)
    UC24/W58      classify into 5 RemediationKind            (deterministic)
                  → PROPOSE_NEW_TERM steps for unmapped classes
    UC27/W61      LLM converts each into a concrete proposal (this demo)

The demo wires a `FakeStructuredProvider` with curated responses for the
two production class names that surfaced in UC24 (ProductCategory, BatchResult)
— so the demo is hermetic, deterministic, and runnable in CI. The same
`TermProposer` swap-in-place accepts real Claude/OpenAI/Gemini providers when
caller opts into `live=True`.

Run from repo root:
    .venv/bin/python -m backend.sim_v2.demos.uc27_term_proposal.run
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from dataclasses import dataclass

from sqlalchemy.orm import Session

from backend.sim_v2.core.ontology.domain_layer.production_domain_loader import (
    load_actions,
)
from backend.sim_v2.core.recommendation.providers.base import (
    LLMProvider,
    LLMRequest,
    LLMResponse,
)
from backend.sim_v2.core.recommendation.term_proposer import (
    TermProposalResult,
    TermProposer,
    existing_terms_for_grounding,
)
from backend.sim_v2.core.verification.return_type_remediation import (
    TermClassIndex,
    generate_return_type_remediation,
)
from backend.sim_v2.core.verification.return_type_verifier import (
    verify_action_return_types,
)
from backend.sim_v2.demos.uc10_production_inspector.run import (
    PRODUCTION_DB_PATH,
    open_readonly_session,
)


# ─────────────────────────────────────────────────────────────────────────────
# Curated LLM responses — keyed by the target class string the prompt carries.
# Production-quality strings; in real operation these would be live LLM output.
# ─────────────────────────────────────────────────────────────────────────────


_CANNED_RESPONSES: dict[str, str] = {
    "ProductCategory": json.dumps({
        "fqn":         "term.scm.product.product_category",
        "label":       "제품 카테고리",
        "description": (
            "제품의 분류 카테고리 (예: 일반 / 특수 / 시험재). "
            "SdProductClassifier 가 SDOrderEntity 의 productCd 를 기준으로 부여."
        ),
        "aliases":     ["ProductCategory", "ProdCategory", "제품분류"],
        "domain":      "scm",
        "kind":        "enum",
        "confidence":  0.92,
        "needs_review": False,
    }, ensure_ascii=False),

    "BatchResult": json.dumps({
        "fqn":         "term.scm.driver.batch_result",
        "label":       "배치 실행 결과",
        "description": (
            "SdDriver.batchDesign 호출의 결과 집합. 처리된 주문 수, "
            "성공 / 실패 카운트, 오류 메시지 리스트 포함."
        ),
        "aliases":     ["BatchResult", "SdDriver.BatchResult", "배치결과"],
        "domain":      "scm",
        "kind":        "composite",
        "confidence":  0.85,
        "needs_review": False,
    }, ensure_ascii=False),
}


class CannedJSONProvider:
    """LLMProvider that returns curated JSON responses keyed by class substring.

    Production replacement: pass any of the live providers (ClaudeProvider,
    OpenAIProvider, GeminiProvider) constructed with `live=True`.
    """
    name = "uc27-canned"

    def __init__(self, responses: dict[str, str]) -> None:
        self._responses = responses

    def complete(self, request: LLMRequest,
                 model: str | None = None) -> LLMResponse:
        for needle, payload in self._responses.items():
            if needle in request.user:
                return LLMResponse(
                    text=payload, provider="uc27-canned", model="curated-v1",
                    input_tokens=len(request.user) // 4, output_tokens=128,
                    stop_reason="end_turn",
                )
        # Fall through — no curated answer; return empty so proposer flags it
        return LLMResponse(
            text="", provider="uc27-canned", model="curated-v1",
        )

    def validate(self) -> bool:
        return True


# ─────────────────────────────────────────────────────────────────────────────
# Per-repo pipeline
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class RepoTermProposals:
    repo_id:    str
    results:    tuple[TermProposalResult, ...]

    @property
    def validated(self) -> int:
        return sum(1 for r in self.results
                   if r.proposal is not None and not r.proposal.needs_review)

    @property
    def needs_review(self) -> int:
        return sum(1 for r in self.results
                   if r.proposal is not None and r.proposal.needs_review)

    @property
    def failed(self) -> int:
        return sum(1 for r in self.results if r.proposal is None)


def propose_terms_for_repo(
    session: Session, repo_id: str,
    provider: LLMProvider | None = None,
) -> RepoTermProposals:
    actions = load_actions(session, repo_id)
    verifs = verify_action_return_types(session, actions)
    index = TermClassIndex.build(session, repo_id)
    remediation = generate_return_type_remediation(verifs, term_index=index)

    propose_steps = [s for s in remediation.steps if s.kind == "PROPOSE_NEW_TERM"]
    if not propose_steps:
        return RepoTermProposals(repo_id=repo_id, results=())

    grounding = existing_terms_for_grounding(
        session, repo_id, domain="scm", limit=10,
    )
    proposer = TermProposer(provider or CannedJSONProvider(_CANNED_RESPONSES))

    results: list[TermProposalResult] = []
    seen_classes: set[str] = set()
    for step in propose_steps:
        target = step.proposed_class or ""
        if not target or target in seen_classes:
            continue
        seen_classes.add(target)
        result = proposer.propose(
            target,
            method_fqn=step.code_method_fqn,
            domain="scm",
            existing_terms=grounding,
        )
        results.append(result)
    return RepoTermProposals(repo_id=repo_id, results=tuple(results))


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────


DEFAULT_REPOS: tuple[str, ...] = (
    "slab-design-real",
    "slab-design-real-v2",
)


def _banner(line: str) -> None:
    print("─" * 78)
    print(line)
    print("─" * 78)


def _print_result(r: TermProposalResult) -> None:
    if r.proposal is None:
        print(f"  ✗ [REJECTED ] target_class=?")
        for e in r.validation_errors:
            print(f"      error: {e}")
        return

    p = r.proposal
    marker = "⚠" if p.needs_review else "✓"
    label_tag = "needs_review" if p.needs_review else "validated"
    print(f"  {marker} [{label_tag:13s}] {p.target_class}")
    print(f"      fqn         : {p.fqn}")
    print(f"      label       : {p.label}")
    print(f"      domain/kind : {p.domain} / {p.kind}")
    print(f"      aliases     : {list(p.aliases)}")
    print(f"      confidence  : {p.confidence:.2f}")
    if r.duplicate_of:
        print(f"      duplicate_of: {r.duplicate_of}")
    print(f"      description : {p.description[:90]}{'…' if len(p.description) > 90 else ''}")


def main(repos: tuple[str, ...] = DEFAULT_REPOS) -> int:
    print("=" * 78)
    print("UC27 — LLM-based term proposal (W61)")
    print("Two-Engine Recommendation Engine applied to UC24 PROPOSE_NEW_TERM steps")
    print("=" * 78)
    print()

    session = open_readonly_session()
    if session is None:
        print(f"  {PRODUCTION_DB_PATH} not found — skipping (CI / fresh checkout)")
        return 0

    try:
        for repo_id in repos:
            r = propose_terms_for_repo(session, repo_id)
            _banner(f"Repo: {r.repo_id}")
            print(f"  Total proposals : {len(r.results)}")
            print(f"  Validated       : {r.validated}")
            print(f"  Needs review    : {r.needs_review}")
            print(f"  Rejected        : {r.failed}")
            print()
            if r.results:
                _banner("Proposals (LLM output → 4-layer-defended structured term)")
                for result in r.results:
                    _print_result(result)
                    print()
        _banner("✓ Recommendation Engine wired to Verification findings")
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    sys.exit(main())
