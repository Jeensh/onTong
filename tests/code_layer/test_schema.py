"""C2-1 schema invariant tests."""
from __future__ import annotations

import pytest

from backend.modeling.code_layer import (
    CallAnalysisSource,
    CallCandidate,
    CallSite,
    CodeField,
    CodeMethod,
    CodeMethodAnchor,
    CodeMethodParam,
    CodeType,
    CodeTypeKind,
    CodeTypeRole,
    MethodRole,
)


class TestCodeTypeInvariants:
    def test_interface_auto_abstract(self):
        """interface 는 자동으로 is_abstract=True."""
        t = CodeType(
            fqn="com.scm.Trackable",
            simple_name="Trackable",
            kind=CodeTypeKind.INTERFACE,
        )
        assert t.is_abstract is True

    def test_enum_cannot_be_abstract(self):
        with pytest.raises(ValueError, match="enum.*cannot be abstract"):
            CodeType(
                fqn="com.scm.Status",
                simple_name="Status",
                kind=CodeTypeKind.ENUM,
                is_abstract=True,
            )

    def test_interface_cannot_extends_class(self):
        with pytest.raises(ValueError, match="interface.*cannot have 'extends'"):
            CodeType(
                fqn="com.scm.Trackable",
                simple_name="Trackable",
                kind=CodeTypeKind.INTERFACE,
                extends="com.scm.SomeClass",
            )

    def test_class_with_extends_implements(self):
        t = CodeType(
            fqn="com.scm.RushOrder",
            simple_name="RushOrder",
            package="com.scm",
            kind=CodeTypeKind.CLASS,
            extends="com.scm.Order",
            implements=["com.scm.Trackable", "com.scm.Auditable"],
        )
        assert t.extends == "com.scm.Order"
        assert "com.scm.Trackable" in t.implements


class TestCodeMethod:
    def test_anchors_preserved(self):
        m = CodeMethod(
            fqn="com.scm.RushOrder.validate",
            name="validate",
            parent_type_fqn="com.scm.RushOrder",
            anchors=[
                CodeMethodAnchor(
                    method_fqn="com.scm.RushOrder.validate",
                    kind="literal",
                    locator="literal:200.0",
                    line=15,
                ),
            ],
        )
        assert len(m.anchors) == 1
        assert m.anchors[0].locator == "literal:200.0"

    def test_default_role_unknown(self):
        m = CodeMethod(
            fqn="X.foo", name="foo", parent_type_fqn="X",
        )
        assert m.role == MethodRole.UNKNOWN


class TestCallSite:
    def test_high_confidence_single_impl(self):
        cs = CallSite(
            id="a" * 16,
            caller_method_fqn="com.scm.S.process",
            callee_simple_name="validate",
            callee_receiver_static_type="Validator",
            possible_runtime_types=[
                CallCandidate(code_type_fqn="com.scm.StandardValidator", score=1.0, reason="유일 impl"),
            ],
            confidence=1.0,
            analysis_source=CallAnalysisSource.SINGLE_IMPL,
        )
        assert cs.confidence == 1.0
        assert cs.needs_user_confirm is False
        assert len(cs.possible_runtime_types) == 1

    def test_ambiguous_needs_confirm(self):
        cs = CallSite(
            id="b" * 16,
            caller_method_fqn="com.scm.S.process",
            callee_simple_name="validate",
            callee_receiver_static_type="Order",
            possible_runtime_types=[
                CallCandidate(code_type_fqn="com.scm.StandardOrder", score=0.5, reason="후보"),
                CallCandidate(code_type_fqn="com.scm.RushOrder", score=0.5, reason="후보"),
            ],
            confidence=0.0,
            analysis_source=CallAnalysisSource.STATIC_UNRESOLVED,
            needs_user_confirm=True,
        )
        assert cs.needs_user_confirm is True
        assert len(cs.possible_runtime_types) == 2
