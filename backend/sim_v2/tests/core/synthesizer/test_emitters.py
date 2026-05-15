"""Generic emitter framework test — ADR-006 + ADR-013."""
from __future__ import annotations

import pytest

from backend.sim_v2.core.synthesizer.emitters.base import (
    EmitContext,
    EmitOutput,
    Emitter,
)
from backend.sim_v2.core.synthesizer.emitters.body_branch import BodyBranchEmitter
from backend.sim_v2.core.synthesizer.emitters.body_compute import BodyComputeEmitter
from backend.sim_v2.core.synthesizer.emitters.body_entity_construction import (
    BodyEntityConstructionEmitter,
)
from backend.sim_v2.core.synthesizer.emitters.body_loop import BodyLoopEmitter
from backend.sim_v2.core.synthesizer.emitters.body_repository_call import (
    BodyRepositoryCallEmitter,
)
from backend.sim_v2.core.synthesizer.emitters.body_return import BodyReturnEmitter
from backend.sim_v2.core.synthesizer.emitters.body_service_lookup import (
    BodyServiceLookupEmitter,
)
from backend.sim_v2.core.synthesizer.emitters.body_set_output import BodySetOutputEmitter
from backend.sim_v2.core.synthesizer.emitters.registry import (
    EmitterRegistry,
    SignatureLockedEmitter,
    get_default_registry,
    reset_default_registry,
)


@pytest.fixture(autouse=True)
def fresh_registry():
    """매 test 후 default registry 초기화 (isolation)."""
    yield
    reset_default_registry()


# ─────────────────────────────────────────────────────────────────────────────
# 8 core emitter — target_slots + emit() shape
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("emitter_cls, expected_slots", [
    (BodyComputeEmitter,            ("body.compute",)),
    (BodySetOutputEmitter,          ("body.set_output",)),
    (BodyReturnEmitter,             ("body.return", "body.return_aggregate")),
    (BodyBranchEmitter,             ("body.branch", "body.fallback", "body.fallback_strategy")),
    (BodyLoopEmitter,               ("body.loop", "body.iterate_orders", "body.loop_init")),
    (BodyServiceLookupEmitter,      ("body.service_lookup",)),
    (BodyRepositoryCallEmitter,     ("body.repository_call",)),
    (BodyEntityConstructionEmitter, (
        "body.entity_construction",
        "body.snapshot_serialization",
        "body.slab_null_marker",
        "body.error_code_propagation",
    )),
])
def test_core_emitter_declares_target_slots(emitter_cls, expected_slots):
    emitter = emitter_cls()
    assert emitter.target_slots == expected_slots
    assert emitter.name.startswith("core.")


def test_body_compute_emits_expression():
    e = BodyComputeEmitter()
    out = e.emit(EmitContext(
        target_slot="body.compute",
        anchor_metadata={"expression": "a + b", "result_var": "sum"},
    ))
    assert isinstance(out, EmitOutput)
    assert "sum = a + b" in out.python_source


def test_body_branch_with_else():
    e = BodyBranchEmitter()
    out = e.emit(EmitContext(
        target_slot="body.branch",
        anchor_metadata={
            "condition": "x > 0",
            "then_body": "y = 1",
            "else_body": "y = -1",
        },
    ))
    assert "if x > 0" in out.python_source
    assert "else:" in out.python_source
    assert "y = -1" in out.python_source


def test_body_loop_emits_for():
    e = BodyLoopEmitter()
    out = e.emit(EmitContext(
        target_slot="body.iterate_orders",
        anchor_metadata={"iter_var": "order", "iterable": "orders", "body": "process(order)"},
    ))
    assert "for order in orders" in out.python_source


# ─────────────────────────────────────────────────────────────────────────────
# Registry — register / lookup / fallback
# ─────────────────────────────────────────────────────────────────────────────


def test_registry_register_and_lookup():
    reg = EmitterRegistry()
    reg.register(BodyComputeEmitter())
    found = reg.get_for_target_slot("body.compute")
    assert isinstance(found, BodyComputeEmitter)
    assert reg.get_by_name("core.body_compute") is found


def test_registry_name_conflict():
    reg = EmitterRegistry()
    reg.register(BodyComputeEmitter())
    with pytest.raises(ValueError, match="name conflict"):
        reg.register(BodyComputeEmitter())


def test_registry_target_slot_conflict():
    reg = EmitterRegistry()
    reg.register(BodyComputeEmitter())

    class _Duplicate(Emitter):
        name = "other.body_compute"
        target_slots = ("body.compute",)
        def emit(self, ctx):
            return EmitOutput(python_source="")

    with pytest.raises(ValueError, match="target_slot conflict"):
        reg.register(_Duplicate())


def test_registry_override_allowed():
    reg = EmitterRegistry()
    reg.register(BodyComputeEmitter())

    class _Override(Emitter):
        name = "core.body_compute"
        target_slots = ("body.compute",)
        def emit(self, ctx):
            return EmitOutput(python_source="# overridden")

    reg.register(_Override(), override=True)
    out = reg.emit(EmitContext(target_slot="body.compute"))
    assert "overridden" in out.python_source


def test_unknown_target_slot_returns_signature_locked():
    reg = EmitterRegistry()
    reg.register(BodyComputeEmitter())
    out = reg.emit(EmitContext(target_slot="banking.drools_kbase_lookup", plugin_name="banking"))
    assert out.signature_locked is True
    assert "SIGNATURE_LOCKED" in out.python_source
    assert "banking.drools_kbase_lookup" in out.python_source
    assert "banking" in out.python_source  # plugin name hint


def test_signature_locked_for_empty_registry():
    reg = EmitterRegistry()
    out = reg.emit(EmitContext(target_slot="body.compute"))
    assert out.signature_locked is True


def test_unregister():
    reg = EmitterRegistry()
    reg.register(BodyComputeEmitter())
    assert reg.count() == 1
    reg.unregister("core.body_compute")
    assert reg.count() == 0
    out = reg.emit(EmitContext(target_slot="body.compute"))
    assert out.signature_locked is True


def test_signature_locked_emitter_alone():
    """SignatureLockedEmitter 가 standalone 으로 fallback emit."""
    e = SignatureLockedEmitter()
    out = e.emit(EmitContext(target_slot="banking.drools_kbase_lookup", plugin_name="banking"))
    assert out.signature_locked is True
    assert "banking.drools_kbase_lookup" in out.python_source


# ─────────────────────────────────────────────────────────────────────────────
# default registry — 8 emitter auto-registered
# ─────────────────────────────────────────────────────────────────────────────


def test_default_registry_has_eight_emitters():
    reg = get_default_registry()
    assert reg.count() == 8
    names = set(reg.all_emitter_names())
    expected = {
        "core.body_compute",
        "core.body_set_output",
        "core.body_return",
        "core.body_branch",
        "core.body_loop",
        "core.body_service_lookup",
        "core.body_repository_call",
        "core.body_entity_construction",
    }
    assert names == expected


def test_default_registry_target_slot_coverage():
    reg = get_default_registry()
    slots = set(reg.all_target_slots())
    # P04 (2), P07 (3), P08 (3), P18 (4) — total 2 + 3 + 3 + 4 = 12, plus 4 single = 16
    assert "body.compute" in slots
    assert "body.return_aggregate" in slots  # P04 의 sub-slot
    assert "body.snapshot_serialization" in slots  # P18 의 sub-slot
    assert len(slots) == 16


def test_default_registry_resolves_known_slot():
    reg = get_default_registry()
    out = reg.emit(EmitContext(
        target_slot="body.compute",
        anchor_metadata={"expression": "1 + 1"},
    ))
    assert out.signature_locked is False
    assert "1 + 1" in out.python_source


def test_default_registry_unknown_slot_signature_locked():
    reg = get_default_registry()
    out = reg.emit(EmitContext(
        target_slot="atomic.banking.drools_kbase_lookup",
        plugin_name="banking",
    ))
    assert out.signature_locked is True
