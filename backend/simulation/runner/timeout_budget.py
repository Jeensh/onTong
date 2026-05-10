"""TimeoutBudget (spec 05 §4.7) — 전체 run timeout 을 dispatch loop 에 분배.

정책:
- RunOptions.timeout_sec 가 전체 run 의 budget
- 분배: total / estimated_steps + 빠른 dispatch 가 남기면 늦은 dispatch 가 흡수
- 임의 dispatch 가 fair-share × 2 를 넘으면 강제 timeout
- budget_remaining() 이 0 이하면 TimeoutError raise
"""

from __future__ import annotations

import time

from backend.shared.contracts.simulation import RunPlan


class TimeoutBudget:
    """전체 run 의 timeout 을 dispatch frame 별로 분배."""

    def __init__(self, total_sec: float, plan: RunPlan):
        self._total = total_sec
        self._deadline = time.monotonic() + total_sec
        self._reserved_per_dispatch = total_sec / max(plan.estimated_steps or 1, 1)

    def for_dispatch(self) -> float:
        """다음 dispatch 의 budget — dynamic 흡수.

        Returns:
            예상 budget (sec). 항상 budget_remaining() 이하 + fair-share × 2 이하.

        Raises:
            TimeoutError: 전체 budget 소진
        """
        remaining = self._deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError(
                f"total run budget exhausted ({self._total}s) — dispatch 중단"
            )
        return min(remaining, self._reserved_per_dispatch * 2)

    def budget_remaining(self) -> float:
        """남은 budget (sec). 음수 가능 (이미 초과)."""
        return self._deadline - time.monotonic()

    def is_exhausted(self) -> bool:
        """budget 초과 여부."""
        return self.budget_remaining() <= 0


__all__ = ["TimeoutBudget"]
