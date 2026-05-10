"""AtomicOverridePatcher (spec 04 §1.2 4-rule 알고리즘).

ChangeSpec.atomic_overrides 의 path/value 쌍을 RunInputs.slots / fixture 에
실제로 patch — 더 이상 RunInputs.overrides 에 dump 만 하지 않음.

4 Rules (spec 04 §1.2):
- Rule 1: path 에 '<...>' 가 있으면 → Action input/output 슬롯 path
          예: "scm.workflow.X.inputs[0]<scm.order.Order>.width"
- Rule 2: path 가 atomic_fqn 단일 토큰 → fixture/lookups 의 모든 row 에 broadcast
          예: "scm.shared.atomic.capabilityMultiplier" = 1.05
- Rule 3: path 가 'composite_fqn.slot' → composite 내 atomic
          (echo-stub iter 미구현 — composite 식별이 ontology 의존, deferred)
- Rule 4: path 인식 안 되면 → ValueError

본 모듈은 modeling internal layer 직접 import 0건 (Section isolation).
"""

from __future__ import annotations

import logging
import re
from typing import Any

from backend.shared.contracts.simulation import RunInputs, TypedValue

logger = logging.getLogger(__name__)


# ─── Rule 1 path 정규식 ─────────────────────────────────────────────


# {action_fqn}.inputs[N]<{type_fqn}>.{atom_path}
# group: prefix, index, type, atom_path
_RULE1_RE = re.compile(
    r"^(?P<prefix>[^<\[]+)\.inputs\[(?P<index>\d+)\]"
    r"<(?P<type>[^>]+)>"
    r"\.(?P<atom>.+)$"
)


# ─── AtomicOverridePatcher ───────────────────────────────────────────


class AtomicOverridePatcher:
    """spec 04 §1.2 의 4-rule 을 RunInputs 에 적용.

    Stateless — 같은 인스턴스를 여러 run 에 재사용 가능.
    apply() 가 RunInputs 의 model_copy 로 변경분 반환 (immutable Pydantic 정합).
    """

    def apply(
        self,
        run_inputs: RunInputs,
        overrides: dict[str, Any],
        action_fqn: str,
    ) -> tuple[RunInputs, list[str]]:
        """RunInputs + overrides → patched RunInputs + warnings.

        Args:
            run_inputs: 원본 RunInputs (orchestrator 의 _build_run_inputs 결과)
            overrides: ChangeSpec.atomic_overrides
            action_fqn: 컨텍스트 (디버그 로그 용)

        Returns:
            (updated RunInputs, warnings)

        Raises:
            ValueError: 4-rule 모두 매칭 안 되는 path
        """
        warnings: list[str] = []

        # 작업할 slots dict 사본 (Pydantic frozen 회피)
        slots: dict[str, TypedValue] = dict(run_inputs.slots)
        fixture = run_inputs.fixture

        for path, value in overrides.items():
            rule = self._classify_rule(path)
            if rule == 1:
                self._apply_rule1(path, value, slots, warnings)
            elif rule == 2:
                self._apply_rule2(path, value, fixture, warnings)
            elif rule == 3:
                # composite_fqn.slot — echo-stub iter 미구현
                warnings.append(
                    f"rule 3 (composite.slot) 은 미구현 — path={path!r} skip"
                )
            else:
                raise ValueError(f"invalid path: {path!r}")

        # 새 RunInputs (slots 만 변경. fixture 는 mutable — in-place patch)
        return (
            run_inputs.model_copy(update={
                "slots": slots,
                "overrides": dict(overrides),  # 원본 dict 보존
            }),
            warnings,
        )

    # ─── 내부 — rule 분류 ───────────────────────────────────────

    @staticmethod
    def _classify_rule(path: str) -> int:
        if not path:
            return 4
        if "<" in path and ">" in path and ".inputs[" in path:
            return 1
        if "<" in path or "[" in path:
            return 4  # 잘못된 형태
        if "." in path:
            # 'composite_fqn.slot' vs 'atomic_fqn' 구분 — 둘 다 . 포함 가능
            # echo-stub: 단순화 — '.atomic.' 토큰 있으면 atomic (rule 2), 그 외 composite (rule 3)
            # spec 의 atomic naming 관행: scm.shared.atomic.<name>
            if ".atomic." in path:
                return 2
            return 3
        return 4

    # ─── Rule 1 — slot path with '<...>' ────────────────────────

    @staticmethod
    def _apply_rule1(
        path: str,
        value: Any,
        slots: dict[str, TypedValue],
        warnings: list[str],
    ) -> None:
        m = _RULE1_RE.match(path)
        if not m:
            warnings.append(f"rule 1 regex 미매칭 — path={path!r} skip")
            return

        slot_index = int(m.group("index"))
        type_fqn = m.group("type")
        atom_path = m.group("atom")  # "field" 또는 "spec.diameter"

        # 슬롯 식별 — echo-stub: index=0 → primary slot 우선
        # primary_input_slot 이 있으면 그것, 그 외 첫 slot
        target_name: str | None = None
        if slot_index == 0:
            # primary slot 또는 첫 slot
            if "primary" in slots:
                target_name = "primary"
            elif slots:
                target_name = next(iter(slots))
        else:
            # index > 0 — 현재 echo-stub 은 1 slot 만 — warning
            warnings.append(
                f"slot index={slot_index} 매칭 안 됨 — 현재 builds 는 primary 1개만. path={path!r}"
            )
            return

        if target_name is None:
            warnings.append(f"slot 0 도 비어있음 — path={path!r} skip")
            return

        # 타입 체크 (mismatch 도 patch 는 시도)
        slot = slots[target_name]
        if slot.type_ != type_fqn:
            warnings.append(
                f"type mismatch: slot {target_name!r}._type={slot.type_!r}, override path type={type_fqn!r}"
            )

        # value 가 dict 가 아니면 dict 로 시작
        existing_value = slot.value if isinstance(slot.value, dict) else {}
        new_value = dict(existing_value)
        _set_nested_path(new_value, atom_path.split("."), value)

        slots[target_name] = TypedValue(_type=slot.type_, value=new_value)
        logger.debug("rule 1 patched: slot[%s].%s = %r", target_name, atom_path, value)

    # ─── Rule 2 — atomic_fqn broadcast to fixture ────────────────

    @staticmethod
    def _apply_rule2(
        path: str,
        value: Any,
        fixture: Any,
        warnings: list[str],
    ) -> None:
        if fixture is None:
            warnings.append(
                f"rule 2 broadcast 불가 — RunInputs.fixture=None (atomic={path!r})"
            )
            return

        # fixture 가 broadcast 인터페이스 보유 여부 (duck-typed)
        list_rows = getattr(fixture, "list_rows", None)
        get_atomic_for_column = getattr(fixture, "get_atomic_for_column", None)

        if list_rows is None or get_atomic_for_column is None:
            warnings.append(
                f"rule 2 broadcast 불가 — fixture 가 list_rows/get_atomic_for_column 미보유 "
                f"(atomic={path!r})"
            )
            return

        # 모든 row 의 columns 검사 — atomic_fqn 매핑된 column 에 patch
        patched_count = 0
        for row_key, row_columns in list_rows():
            for col_name in list(row_columns.keys()):
                atom_fqn = get_atomic_for_column(col_name)
                if atom_fqn == path:
                    row_columns[col_name] = value
                    patched_count += 1

        warnings.append(
            f"rule 2 broadcast: atomic={path!r} → {patched_count} row patched"
        )


# ─── 헬퍼 — nested dict path setter ─────────────────────────────────


def _set_nested_path(d: dict, path_parts: list[str], value: Any) -> None:
    """dict d 의 nested path 에 value 설정. 중간 단계 dict 자동 생성."""
    cur = d
    for p in path_parts[:-1]:
        nxt = cur.get(p)
        if not isinstance(nxt, dict):
            nxt = {}
            cur[p] = nxt
        cur = nxt
    cur[path_parts[-1]] = value


__all__ = ["AtomicOverridePatcher"]
