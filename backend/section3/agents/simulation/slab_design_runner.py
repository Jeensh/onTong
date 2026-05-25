"""slab_design_runner — slab-design-real_v2 의 Java Spring Boot 서버 호출.

simulate intent 가 "ORD..." 같은 주문번호를 언급하면, multiturn 의 단일 method
transpile + sandbox 대신 **Java 서버의 전체 21-step 알고리즘** 을 그대로
호출해 실제 slab 결과를 얻는다.

이건 IT 운영자 페르소나의 핵심 워크플로 — "이 주문 돌려보면 어떤 Slab이
나와?" 에 대한 직접적인 답.
"""
from __future__ import annotations

import logging
import os
import re
from typing import Any

import httpx

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = os.environ.get(
    "SLAB_DESIGN_BASE_URL", "http://127.0.0.1:8080",
)

ORDER_NO_RE = re.compile(r"\bORD\d{8,15}\b")


def extract_order_no(text: str) -> str | None:
    """자연어 query 에서 주문번호 추출 — ORD20260510001 형태."""
    m = ORDER_NO_RE.search(text or "")
    return m.group(0) if m else None


def is_full_design_intent(query: str) -> bool:
    """query 가 '전체 설계' 의도를 명확히 시사하는지."""
    if extract_order_no(query):
        return True
    keywords = ("주문번호", "주문 1건", "전체 설계", "21-step", "21 step", "single 설계")
    return any(k in query for k in keywords)


async def run_full_design(
    *, order_no: str, cmp_cd: str = "K", org_cd: str = "1",
    with_trace: bool = True, base_url: str = DEFAULT_BASE_URL,
    timeout_s: float = 30.0,
) -> dict[str, Any]:
    """Java :8080 의 /api/sd/working/single 호출 → 전체 Slab 설계 결과.

    Returns:
      {
        "ok": bool,
        "order_no": str,
        "base_url": str,
        "slab_results": list[dict],     # Slab 결과 (보통 1개)
        "trace": list[dict],            # 21-step 진행 trace
        "error_code": str | None,
        "error_message": str | None,
        "raw_status": int,
      }
    """
    url = f"{base_url}/api/sd/working/single"
    params = {"trace": "true"} if with_trace else {}
    body = {"cmpCd": cmp_cd, "orgCd": org_cd, "orderNo": order_no}
    try:
        async with httpx.AsyncClient(timeout=timeout_s, follow_redirects=True) as c:
            r = await c.post(url, params=params, json=body)
    except httpx.RequestError as e:
        logger.warning("slab-design API 연결 실패: %s", e)
        return {
            "ok": False, "order_no": order_no, "base_url": base_url,
            "slab_results": [], "trace": [],
            "error_code": "API_DOWN",
            "error_message": (
                f"slab-design 서버 ({base_url}) 에 연결 못 했어요. "
                f"`mvn -pl slab-design-boot spring-boot:run` 으로 띄워주세요. ({e})"
            ),
            "raw_status": 0,
        }
    if r.status_code >= 400:
        return {
            "ok": False, "order_no": order_no, "base_url": base_url,
            "slab_results": [], "trace": [],
            "error_code": f"HTTP_{r.status_code}",
            "error_message": (r.text or "")[:500],
            "raw_status": r.status_code,
        }
    j = r.json()
    return {
        "ok": True,
        "order_no": order_no,
        "base_url": base_url,
        "slab_results": j.get("slabResults") or [],
        "trace": j.get("trace") or [],
        "error_code": j.get("errorCode"),
        "error_message": j.get("errorMessage"),
        "raw_status": r.status_code,
    }
