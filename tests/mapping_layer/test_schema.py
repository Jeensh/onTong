"""C4-1 mapping schema invariant tests."""
from __future__ import annotations

import pytest

from backend.modeling.mapping_layer import (
    Action, ActionEffect, ActionEffectOp, ActionKind, ActionParam,
    AnchorBinding, DispatchSource, Realization, RealizationScope,
    TypeRealization, VerificationLevel,
)
from backend.modeling.mapping_layer.schema import ActionOutput


class TestActionInvariants:
    def test_pure_function_no_effects(self):
        with pytest.raises(ValueError, match="pure_function but has"):
            Action(fqn="a", label="A", kind=ActionKind.PURE_FUNCTION,
                effects=[ActionEffect(op=ActionEffectOp.MUTATE, target_term="t.x")])

    def test_workflow_no_realizations(self):
        with pytest.raises(ValueError, match="workflow cannot have direct realizations"):
            Action(fqn="a", label="A", kind=ActionKind.WORKFLOW,
                realizations=[Realization(code_method_fqn="m",
                    dispatch_source=DispatchSource.SINGLE_IMPL)])

    def test_default_unmapped(self):
        a = Action(fqn="a", label="A", kind=ActionKind.PURE_FUNCTION)
        assert a.verification_level == VerificationLevel.UNMAPPED


class TestActionParamInvariants:
    def test_object_ref_requires_term(self):
        with pytest.raises(ValueError, match="requires object_ref_term"):
            ActionParam(name="x", type="object_ref")

    def test_term_without_ref_type_blocked(self):
        with pytest.raises(ValueError, match="object_ref_term set but type"):
            ActionParam(name="x", type="float", object_ref_term="t.x")

    def test_range_invariants(self):
        with pytest.raises(ValueError, match=r"\[min,max\]"):
            ActionParam(name="x", type="float", range=[1.0])
        with pytest.raises(ValueError, match=r"range\[min\]>max"):
            ActionParam(name="x", type="float", range=[2.0, 1.0])


class TestRealizationDispatch:
    def test_dispatch_source_enum(self):
        r = Realization(code_method_fqn="m", dispatch_source=DispatchSource.SINGLE_IMPL)
        assert r.dispatch_source == DispatchSource.SINGLE_IMPL

    def test_subtype_filter_optional(self):
        r = Realization(code_method_fqn="m", dispatch_source=DispatchSource.ANNOTATION)
        assert r.applies_to_code_type_fqn is None  # base


class TestAnchorBinding:
    def test_path_with_subtype_cast(self):
        ab = AnchorBinding(id="a"*16, anchor_locator="literal:200.0",
            code_method_fqn="m", target_action_fqn="a", confidence=1.0,
            target_slot="params[0]<RushOrder>.spec.diameter.range[1]")
        assert "<RushOrder>" in ab.target_slot
