"""RunPlanBuilder (spec 05 §1.2 + spec 04 §3.3) — modeling facade 기반 RunPlan 생성.

ChangeSpec.action_fqn 을 root 로 sub_actions 트리를 BFS recursive 펼침 + expected
BRs / anchors 합집합 + primary_input_type derive.

본 모듈이 spec_router 의 `_build_minimal_run_plan()` 1-frame echo 를 대체.
echo-stub 첫 iter 의 하드코딩 (`primary_input_type="scm.order.Order"`) 제거.

Section isolation ✅ — `_OntologyClientProtocol` duck-typed (modeling internal layer 미import).
"""

from __future__ import annotations

import logging
from typing import Any, Optional, Protocol

from backend.shared.contracts.simulation import RunPlan

logger = logging.getLogger(__name__)


# ─── 의존성 — modeling facade duck-typed Protocol ───────────────────


class _OntologyClientProtocol(Protocol):
    """RunPlanBuilder 가 의존하는 ontology facade 의 최소 인터페이스.

    실제 구현은 `backend.modeling.api.ontology_query.OntologyQueryClientImpl`.
    duck-typed — 4 메서드만 사용.
    """

    def get_action(self, fqn: str) -> Any: ...

    def get_anchor_bindings_for_action(self, action_fqn: str) -> list[Any]: ...

    def get_realizations_for_input_type(
        self, action_fqn: str, code_type_fqn: str
    ) -> list[Any]: ...

    def list_code_types(self, role: Optional[str] = None) -> list[Any]: ...


# ─── RunPlanBuilder ───────────────────────────────────────────────


class RunPlanBuilder:
    """ChangeSpec.action_fqn → RunPlan (modeling facade 호출).

    Steps (spec 05 §1.2 + §1.3):
      1. root action.sub_actions BFS — frame depth 와 함께 누적
      2. 각 frame 에서 primary_input_type derive (realization / param)
      3. expected_brs.direct = root.preconditions + postconditions
      4. expected_brs.transitive = sub action 의 BR fqn (minus direct)
      5. expected_anchors = ⋃ get_anchor_bindings_for_action(fqn).map(.id)
      6. estimated_steps = frame 수 + warnings 채움 (cycle / unknown / depth limit)
    """

    def __init__(self, ontology_client: _OntologyClientProtocol):
        self._ont = ontology_client

    def build(self, root_action_fqn: str, max_depth: int = 10) -> RunPlan:
        """RunPlan 생성. graceful failure — facade 예외 시 warning 누적."""
        warnings: list[str] = []
        frames: list[dict[str, Any]] = []
        anchors: set[str] = set()
        direct_brs: list[str] = []
        transitive_brs_set: set[str] = set()

        # BFS — (fqn, depth) 큐
        queue: list[tuple[str, int]] = [(root_action_fqn, 0)]
        visited: set[str] = set()
        is_root = True

        while queue:
            fqn, depth = queue.pop(0)
            if fqn in visited:
                logger.debug("RunPlanBuilder: skip visited %s", fqn)
                continue
            if depth > max_depth:
                warnings.append(
                    f"max_depth={max_depth} 초과 — {fqn} (depth={depth}) 이후 frame 제외"
                )
                continue
            visited.add(fqn)

            try:
                action = self._ont.get_action(fqn)
            except Exception as exc:
                warnings.append(f"ontology_client.get_action({fqn!r}) 실패: {exc}")
                logger.warning("RunPlanBuilder: get_action(%s) raised — %s", fqn, exc)
                action = None

            if action is None:
                warnings.append(f"action {fqn!r} not found in ontology")
                continue

            # frame 채우기
            frame: dict[str, Any] = {"action_fqn": fqn, "depth": depth}
            primary_type = self._derive_primary_input_type(action)
            if primary_type is not None:
                frame["primary_input_type"] = primary_type
            frames.append(frame)

            # BR 누적 (root 면 direct, 그 외 transitive)
            br_fqns = list(getattr(action, "preconditions", None) or []) + \
                      list(getattr(action, "postconditions", None) or [])
            if is_root:
                direct_brs = list(dict.fromkeys(br_fqns))  # dedup, 순서 유지
                is_root = False
            else:
                transitive_brs_set.update(br_fqns)

            # anchor 누적
            try:
                bindings = self._ont.get_anchor_bindings_for_action(fqn) or []
            except Exception as exc:
                warnings.append(f"ontology_client.get_anchor_bindings_for_action({fqn!r}) 실패: {exc}")
                bindings = []
            for b in bindings:
                anchor_id = getattr(b, "id", None) or getattr(b, "anchor_id", None)
                if anchor_id is not None:
                    anchors.add(anchor_id)

            # 자식 enqueue
            for sub_fqn in (getattr(action, "sub_actions", None) or []):
                if sub_fqn not in visited:
                    queue.append((sub_fqn, depth + 1))

        # transitive 에서 direct 제외
        transitive_brs = sorted(transitive_brs_set - set(direct_brs))

        return RunPlan(
            delegates_to_tree=frames,
            expected_brs={
                "direct": direct_brs,
                "transitive": transitive_brs,
            },
            expected_anchors=sorted(anchors),
            estimated_steps=len(frames),
            warnings=warnings,
        )

    # ─── 내부 — primary_input_type derive ──────────────────────────

    @staticmethod
    def _derive_primary_input_type(action: Any) -> Optional[str]:
        """spec 05 §4.6 build_slots 의 단순화:

        1. action.realizations 의 첫 번째 realization 의 applies_to_code_type_fqn
        2. (없으면) action.params[0].object_ref_term (object_ref 타입 슬롯)
        3. (없으면) None — orchestrator/sandbox 가 fallback 처리
        """
        realizations = list(getattr(action, "realizations", None) or [])
        for r in realizations:
            applies_to = getattr(r, "applies_to_code_type_fqn", None)
            if applies_to:
                return applies_to

        params = list(getattr(action, "params", None) or [])
        for p in params:
            ref = getattr(p, "object_ref_term", None)
            if ref:
                return ref

        return None


__all__ = ["RunPlanBuilder"]
