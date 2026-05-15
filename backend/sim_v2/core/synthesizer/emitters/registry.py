"""EmitterRegistry — target_slot → Emitter lookup.

ADR-013 §2 의 registry pattern. Tier 1 (core) emitter 가 default 로 등록되고,
Tier 2 (plugin) 가 register_emitter() 로 override / extend.

Default behavior — unknown target_slot:
    SignatureLockedEmitter 가 반환. ADR-013 §3 의 SIGNATURE_LOCKED default.
"""
from __future__ import annotations

from .base import EmitContext, EmitOutput, Emitter


class SignatureLockedEmitter(Emitter):
    """SIGNATURE_LOCKED default — ADR-013 §3.

    Unknown target_slot 발견 시 fallback emit. signature_locked=True 로
    contract validator 에게 알림.
    """
    name = "core.signature_locked"
    target_slots = ()  # supports anything via fallback

    def supports(self, target_slot: str) -> bool:
        return True  # any unmatched target_slot

    def emit(self, context: EmitContext) -> EmitOutput:
        slot = context.target_slot
        plugin = context.plugin_name or "<unknown>"
        return EmitOutput(
            python_source=(
                f"# UNCLEAR: target_slot = {slot!r} not handled by any registered emitter.\n"
                f"# SIGNATURE_LOCKED. Add backend/sim_v2/plugins/{plugin}/emitters/ extension\n"
                f"# or check core/synthesizer/emitters/ for missing dispatch_kind support.\n"
                f"raise NotImplementedError({slot!r} + ': SIGNATURE_LOCKED')"
            ),
            notes=(f"SIGNATURE_LOCKED: target_slot={slot!r}, plugin={plugin!r}",),
            signature_locked=True,
        )


class EmitterRegistry:
    """target_slot → Emitter lookup. Plugin extensions register here.

    Conflict policy: explicit name conflict raises ValueError.
    Plugin namespace prefix convention (ADR-013 §5): e.g., `banking.drools_kbase_lookup`.
    """

    def __init__(self) -> None:
        self._by_name:        dict[str, Emitter] = {}
        self._by_target_slot: dict[str, Emitter] = {}
        self._fallback: Emitter = SignatureLockedEmitter()

    def register(self, emitter: Emitter, *, override: bool = False) -> None:
        if not emitter.name:
            raise ValueError(f"Emitter {emitter.__class__.__name__} must define .name")
        if emitter.name in self._by_name and not override:
            raise ValueError(f"Emitter name conflict: {emitter.name!r} already registered")
        self._by_name[emitter.name] = emitter
        for slot in emitter.target_slots:
            if slot in self._by_target_slot and not override:
                raise ValueError(
                    f"target_slot conflict: {slot!r} already handled by "
                    f"{self._by_target_slot[slot].name!r}"
                )
            self._by_target_slot[slot] = emitter

    def unregister(self, name: str) -> None:
        emitter = self._by_name.pop(name, None)
        if emitter is None:
            return
        for slot in emitter.target_slots:
            self._by_target_slot.pop(slot, None)

    def get_by_name(self, name: str) -> Emitter | None:
        return self._by_name.get(name)

    def get_for_target_slot(self, target_slot: str) -> Emitter:
        """Return matching emitter, or SignatureLockedEmitter fallback."""
        return self._by_target_slot.get(target_slot, self._fallback)

    def emit(self, context: EmitContext) -> EmitOutput:
        return self.get_for_target_slot(context.target_slot).emit(context)

    def all_emitter_names(self) -> list[str]:
        return sorted(self._by_name.keys())

    def all_target_slots(self) -> list[str]:
        return sorted(self._by_target_slot.keys())

    def count(self) -> int:
        return len(self._by_name)


# ─────────────────────────────────────────────────────────────────────────────
# Module-level default registry — Tier 1 default emitter 등록
# ─────────────────────────────────────────────────────────────────────────────

_DEFAULT_REGISTRY: EmitterRegistry | None = None


def get_default_registry() -> EmitterRegistry:
    """Returns the global default registry (lazy init).

    Tier 1 core emitter 가 import 시점에 register_default_emitters() 로 등록.
    Plugin loader (ADR-013) 가 plugin extension 으로 추가 등록.
    """
    global _DEFAULT_REGISTRY
    if _DEFAULT_REGISTRY is None:
        _DEFAULT_REGISTRY = EmitterRegistry()
        _register_core_emitters(_DEFAULT_REGISTRY)
    return _DEFAULT_REGISTRY


def reset_default_registry() -> None:
    """Test isolation — full reset."""
    global _DEFAULT_REGISTRY
    _DEFAULT_REGISTRY = None


def _register_core_emitters(registry: EmitterRegistry) -> None:
    """Tier 1 의 8 system-agnostic emitter (Lesson 2 §6.1)."""
    # Imports here to avoid circular import at module load time
    from .body_branch import BodyBranchEmitter
    from .body_compute import BodyComputeEmitter
    from .body_entity_construction import BodyEntityConstructionEmitter
    from .body_loop import BodyLoopEmitter
    from .body_repository_call import BodyRepositoryCallEmitter
    from .body_return import BodyReturnEmitter
    from .body_service_lookup import BodyServiceLookupEmitter
    from .body_set_output import BodySetOutputEmitter

    for cls in (
        BodyComputeEmitter,
        BodySetOutputEmitter,
        BodyReturnEmitter,
        BodyBranchEmitter,
        BodyLoopEmitter,
        BodyServiceLookupEmitter,
        BodyRepositoryCallEmitter,
        BodyEntityConstructionEmitter,
    ):
        registry.register(cls())


__all__ = [
    "EmitterRegistry",
    "SignatureLockedEmitter",
    "get_default_registry",
    "reset_default_registry",
]
