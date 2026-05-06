"""C4-2/4 store CRUD + VerificationLevel state machine tests."""
from __future__ import annotations

import os
import tempfile

import pytest

from backend.modeling.mapping_layer import (
    Action, ActionEffect, ActionEffectOp, ActionKind, ActionParam,
    AnchorBinding, DispatchSource, Realization, RealizationScope,
    TypeRealization, VerificationLevel,
)
from backend.modeling.mapping_layer.schema import ActionOutput
from backend.modeling.mapping_layer.store import MappingLayerStore
from backend.modeling.mapping_layer.verification import (
    can_simulate, compute_verification_level,
)


@pytest.fixture
def fresh_db(monkeypatch):
    from backend.modeling.code_layer.orm import CodeTypeRow  # noqa: F401
    from backend.modeling.domain_layer.orm import BusinessTermRow  # noqa: F401
    from backend.modeling.mapping_layer.orm import ActionRow  # noqa: F401
    from backend.modeling.persistence.database import (
        Base, get_engine, reset_engine_for_tests,
    )
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    monkeypatch.setenv("ONTONG_DB_PATH", path)
    reset_engine_for_tests()
    Base.metadata.create_all(bind=get_engine())
    yield path
    reset_engine_for_tests()
    try:
        os.unlink(path)
    except FileNotFoundError:
        pass


def _make_action(realizations=None, params_confirmed=False):
    return Action(
        fqn="action.scm.order_validate", label="주문 검증",
        kind=ActionKind.PURE_FUNCTION, is_abstract=True,
        declared_on_term="t.order",
        params=[ActionParam(name="주문", type="object_ref",
            object_ref_term="t.order", confirmed=params_confirmed)],
        output=ActionOutput(type="object_ref", object_ref_term="t.result"),
        realizations=realizations or [],
    )


class TestActionStore:
    def test_action_with_realizations_roundtrip(self, fresh_db):
        store = MappingLayerStore()
        a = _make_action(realizations=[
            Realization(code_method_fqn="com.scm.RushOrder.validate",
                applies_to_code_type_fqn="com.scm.RushOrder",
                is_override=True, dispatch_source=DispatchSource.SINGLE_IMPL,
                scope=RealizationScope.PRIMARY),
            Realization(code_method_fqn="com.scm.StandardOrder.validate",
                applies_to_code_type_fqn="com.scm.StandardOrder",
                is_override=True, dispatch_source=DispatchSource.SINGLE_IMPL,
                scope=RealizationScope.PRIMARY),
        ])
        store.upsert_action("scm", a)
        got = store.get_action("action.scm.order_validate")
        assert got is not None
        assert len(got.realizations) == 2
        types = {r.applies_to_code_type_fqn for r in got.realizations}
        assert types == {"com.scm.RushOrder", "com.scm.StandardOrder"}

    def test_action_idempotent_upsert(self, fresh_db):
        store = MappingLayerStore()
        a = _make_action()
        store.upsert_action("scm", a)
        store.upsert_action("scm", a)
        actions = store.list_actions(repo_id="scm")
        assert len(actions) == 1

    def test_anchor_binding_query(self, fresh_db):
        store = MappingLayerStore()
        store.upsert_action("scm", _make_action())
        ab = AnchorBinding(id="ab" + "0" * 14, anchor_locator="literal:200.0",
            code_method_fqn="com.scm.RushOrder.validate",
            target_action_fqn="action.scm.order_validate",
            target_slot="params[0]<RushOrder>.spec.diameter.range[1]",
            confidence=1.0, source="literal_match")
        store.upsert_anchor_bindings("scm", [ab])
        abs_for_action = store.get_anchor_bindings_for_action("action.scm.order_validate")
        assert len(abs_for_action) == 1
        abs_for_method = store.get_anchor_bindings_for_method("com.scm.RushOrder.validate")
        assert len(abs_for_method) == 1

    def test_type_realization_query(self, fresh_db):
        store = MappingLayerStore()
        store.upsert_type_realizations("scm", [
            TypeRealization(code_type_fqn="com.scm.RushOrder", term_fqn="t.rush",
                source="name_match", confirmed=True),
        ])
        got = store.get_term_for_code_type("com.scm.RushOrder")
        assert got is not None
        assert got.term_fqn == "t.rush"

    def test_verification_min_filter(self, fresh_db):
        store = MappingLayerStore()
        a1 = _make_action()  # UNMAPPED
        a2 = _make_action().model_copy(update={
            "fqn": "action.scm.x", "verification_level": VerificationLevel.SIGNATURE_LOCKED,
        })
        store.upsert_action("scm", a1)
        store.upsert_action("scm", a2)
        all_ = store.list_actions(repo_id="scm")
        assert len(all_) == 2
        sig_or_higher = store.list_actions(repo_id="scm", verification_min=VerificationLevel.SIGNATURE_LOCKED)
        assert len(sig_or_higher) == 1
        assert sig_or_higher[0].fqn == "action.scm.x"

    def test_delete_repo_cascade(self, fresh_db):
        store = MappingLayerStore()
        store.upsert_action("scm", _make_action(realizations=[
            Realization(code_method_fqn="m", dispatch_source=DispatchSource.SINGLE_IMPL),
        ]))
        store.upsert_anchor_bindings("scm", [
            AnchorBinding(id="z" * 16, anchor_locator="x", code_method_fqn="m",
                target_action_fqn="action.scm.order_validate", target_slot="params[0]"),
        ])
        n = store.delete_repo("scm")
        assert n >= 3  # action + realization + anchor


class TestVerificationLevel:
    def test_unmapped_no_realizations(self):
        a = _make_action(realizations=[])
        assert compute_verification_level(a) == VerificationLevel.UNMAPPED

    def test_draft_param_unconfirmed(self):
        a = _make_action(params_confirmed=False, realizations=[
            Realization(code_method_fqn="m", dispatch_source=DispatchSource.SINGLE_IMPL,
                scope=RealizationScope.PRIMARY, confirmed=True),
        ])
        assert compute_verification_level(a) == VerificationLevel.DRAFT

    def test_signature_locked(self):
        a = _make_action(params_confirmed=True, realizations=[
            Realization(code_method_fqn="m", dispatch_source=DispatchSource.SINGLE_IMPL,
                scope=RealizationScope.PRIMARY, confirmed=True),
        ])
        assert compute_verification_level(a) == VerificationLevel.SIGNATURE_LOCKED

    def test_body_anchored(self):
        a = _make_action(params_confirmed=True, realizations=[
            Realization(code_method_fqn="m", dispatch_source=DispatchSource.SINGLE_IMPL,
                scope=RealizationScope.PRIMARY, confirmed=True),
        ])
        ab = AnchorBinding(id="a"*16, anchor_locator="x", code_method_fqn="m",
            target_action_fqn="a", target_slot="params[0]", confirmed=True)
        assert compute_verification_level(a, anchor_bindings=[ab]) == VerificationLevel.BODY_ANCHORED

    def test_sim_verified(self):
        a = _make_action(params_confirmed=True, realizations=[
            Realization(code_method_fqn="m", dispatch_source=DispatchSource.SINGLE_IMPL,
                scope=RealizationScope.PRIMARY, confirmed=True),
        ])
        ab = AnchorBinding(id="a"*16, anchor_locator="x", code_method_fqn="m",
            target_action_fqn="a", target_slot="params[0]", confirmed=True)
        assert compute_verification_level(a, anchor_bindings=[ab],
            sim_passed=True) == VerificationLevel.SIM_VERIFIED

    def test_pr_proven_overrides(self):
        a = _make_action(realizations=[])  # UNMAPPED
        assert compute_verification_level(a, pr_proven=True) == VerificationLevel.PR_PROVEN

    def test_can_simulate_gate(self):
        assert not can_simulate(VerificationLevel.UNMAPPED)
        assert not can_simulate(VerificationLevel.DRAFT)
        assert can_simulate(VerificationLevel.SIGNATURE_LOCKED)
        assert can_simulate(VerificationLevel.BODY_ANCHORED)
        assert can_simulate(VerificationLevel.SIM_VERIFIED)
        assert can_simulate(VerificationLevel.PR_PROVEN)
