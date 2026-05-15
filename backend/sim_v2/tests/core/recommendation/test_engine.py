"""Recommendation Engine test — W5.3."""
from __future__ import annotations

from backend.sim_v2.core.recommendation.anti_patterns.catalog import AntiPatternScanner
from backend.sim_v2.core.recommendation.engine import (
    ProposalContext,
    RecommendationEngine,
)
from backend.sim_v2.core.recommendation.providers.base import LLMRequest, LLMResponse


class _StubProvider:
    """Test double — returns canned text."""
    name = "stub"

    def __init__(self, canned_text: str = "Proposal: add audit_log table."):
        self._text = canned_text
        self.calls: list[LLMRequest] = []

    def complete(self, request: LLMRequest, model: str | None = None) -> LLMResponse:
        self.calls.append(request)
        return LLMResponse(
            text=self._text,
            provider=self.name,
            model="stub-model",
            input_tokens=10,
            output_tokens=20,
        )

    def validate(self) -> bool:
        return True


# ─────────────────────────────────────────────────────────────────────────────
# propose
# ─────────────────────────────────────────────────────────────────────────────


def test_propose_returns_proposal_in_draft():
    eng = RecommendationEngine(provider=_StubProvider())
    result = eng.propose(ProposalContext(
        plugin="banking",
        proposal_type="schema_change",
        user_intent="Add audit_log table",
    ))
    assert result.proposal.state == "DRAFT"
    assert result.proposal.plugin == "banking"
    assert result.proposal.type == "schema_change"


def test_propose_attaches_raw_response():
    eng = RecommendationEngine(provider=_StubProvider("custom response"))
    result = eng.propose(ProposalContext(
        plugin="banking",
        proposal_type="schema_change",
        user_intent="x",
    ))
    assert result.raw_response == "custom response"
    assert result.provider_used == "stub"


def test_propose_includes_ontology_context():
    stub = _StubProvider()
    eng = RecommendationEngine(provider=stub)
    eng.propose(ProposalContext(
        plugin="banking",
        proposal_type="schema_change",
        user_intent="Add audit_log",
        ontology_context={
            "related_table": "application",
            "related_term": "loan.audit_event",
        },
    ))
    # Verify grounding context was included in the user prompt
    assert len(stub.calls) == 1
    user_prompt = stub.calls[0].user
    assert "related_table" in user_prompt
    assert "application" in user_prompt


def test_propose_validation_clean():
    eng = RecommendationEngine(provider=_StubProvider("Clean proposal text"))
    result = eng.propose(ProposalContext(
        plugin="banking", proposal_type="schema_change", user_intent="x",
    ))
    assert result.validation.has_errors is False
    assert "clean" in result.validation.summary


def test_propose_validation_flags_bigdecimal():
    eng = RecommendationEngine(
        provider=_StubProvider("x = BigDecimal('100').multiply(y)"),
    )
    result = eng.propose(ProposalContext(
        plugin="banking", proposal_type="code_change", user_intent="x",
    ))
    assert result.validation.has_errors is True
    assert any(
        h.pattern_id == "phase_alpha_bigdecimal_class_vs_function"
        for h in result.validation.hits
    )


def test_propose_validation_flags_multiple():
    bad = (
        "x = BigDecimal('100').multiply(y, MathContext.DECIMAL64).setScale(2, RoundingMode.HALF_EVEN)\n"
        "if cd == SdConstants.POS_SM:\n"
        "    raise ValidationResult.fail('x', 'E', 'm')"
    )
    eng = RecommendationEngine(provider=_StubProvider(bad))
    result = eng.propose(ProposalContext(
        plugin="banking", proposal_type="code_change", user_intent="x",
    ))
    pattern_ids = {h.pattern_id for h in result.validation.hits}
    # All 5 L1 KNOWN_DIVERGENCE patterns detected
    assert pattern_ids >= {
        "phase_alpha_bigdecimal_class_vs_function",
        "phase_alpha_mathcontext_namespace_vs_constants",
        "phase_alpha_roundingmode_enum_vs_constants",
        "phase_alpha_sdconstants_namespace_vs_imports",
        "phase_alpha_validationresult_missing_implementation",
    }


def test_propose_payload_attached_to_correct_diff_slot():
    eng = RecommendationEngine(provider=_StubProvider("payload-text"))
    schema_result = eng.propose(ProposalContext(
        plugin="banking", proposal_type="schema_change", user_intent="x",
    ))
    assert schema_result.proposal.schema_diff is not None
    assert schema_result.proposal.code_diff is None
    assert schema_result.proposal.ontology_diff is None

    code_result = eng.propose(ProposalContext(
        plugin="banking", proposal_type="code_change", user_intent="x",
    ))
    assert code_result.proposal.code_diff is not None
    assert code_result.proposal.schema_diff is None


# ─────────────────────────────────────────────────────────────────────────────
# refine — Integrator's Protocol implementation
# ─────────────────────────────────────────────────────────────────────────────


def test_refine_updates_proposal():
    eng = RecommendationEngine(provider=_StubProvider("refined payload"))
    initial = eng.propose(ProposalContext(
        plugin="banking", proposal_type="schema_change", user_intent="initial",
    ))
    refined = eng.refine(initial.proposal, hints={"reason": "user prefers different scale"})
    assert refined.schema_diff is not None
    assert refined.schema_diff.get("refined_llm_output") == "refined payload"


def test_engine_uses_custom_scanner():
    """Provide alternative AntiPatternScanner — verify the engine uses it."""
    from backend.sim_v2.core.recommendation.anti_patterns.catalog import (
        AntiPattern,
    )

    custom = AntiPatternScanner(catalog=(
        AntiPattern(
            id="custom.test",
            title="Custom marker",
            lesson_ref="L1",
            severity="ERROR",
            signal_pattern=r"CUSTOM_BAD",
            rationale="test",
        ),
    ))
    eng = RecommendationEngine(
        provider=_StubProvider("output contains CUSTOM_BAD here"),
        scanner=custom,
    )
    result = eng.propose(ProposalContext(
        plugin="b", proposal_type="schema_change", user_intent="x",
    ))
    assert result.validation.has_errors
    assert any(h.pattern_id == "custom.test" for h in result.validation.hits)
