"""Phase 1 — 누적 실수율 (Java ProductivityService 미러).

활성 공정의 실수율 곱. 미매칭 시 default 0.95.
"""

from __future__ import annotations

from decimal import Decimal

from ..domain import PROC_CODES, SDOrder
from ..repository import ProductivityStdRepo


def cumulative_productivity(
    order: SDOrder,
    repo: ProductivityStdRepo,
) -> Decimal:
    """confirmedPlantCd 활성 위치별로 lookup_or_default → 곱.

    Java 동작과 1:1 일치:
    - 8자리 미만 confirmedPlantCd → DEFAULT_PRODUCTIVITY (보수)
    - ' ' 위치는 skip
    - else lookup_or_default(공정 약어)
    """
    confirmed = order.confirmedPlantCd
    if confirmed is None or len(confirmed) < 8:
        return ProductivityStdRepo.DEFAULT_PRODUCTIVITY

    product = Decimal(1)
    for i in range(8):
        if confirmed[i] == " ":
            continue
        p = repo.lookup_or_default(
            order.cmpCd, order.orgCd, PROC_CODES[i],
            order.gradeCd, order.productTypeCd, order.customerCd,
        )
        product = product * p
    return product
