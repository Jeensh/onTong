"""Extract metadata filters from user queries for ChromaDB pre-filtering."""

from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

# Domain keyword mappings (query term → ChromaDB metadata value)
DOMAIN_KEYWORDS: dict[str, list[str]] = {
    "SCM": ["SCM", "scm", "공급망", "공급체인", "supply chain"],
    "QC": ["QC", "qc", "품질", "검사", "품질관리", "quality"],
    "생산": ["생산", "제조", "공정", "라인", "production"],
    "물류": ["물류", "배송", "운송", "운반", "logistics"],
    "영업": ["영업", "판매", "고객", "sales"],
    "회계": ["회계", "재무", "정산", "경비", "비용", "finance"],
    "IT": ["IT", "시스템", "서버", "인프라", "개발", "보안"],
    "HR": ["HR", "인사", "채용", "교육", "OJT", "온보딩", "입사", "퇴사", "조직"],
}

# Process keyword mappings
PROCESS_KEYWORDS: dict[str, list[str]] = {
    "주문처리": ["주문", "발주", "오더", "order"],
    "입고": ["입고", "수령", "입하"],
    "출고": ["출고", "출하", "납품"],
    "검수": ["검수", "검사", "검증", "inspection"],
    "재고관리": ["재고", "재고관리", "inventory", "stock"],
    "배송": ["배송", "택배", "운송", "delivery"],
    "정산": ["정산", "결제", "결산", "settlement"],
}


def extract_metadata_filter(query: str) -> dict | None:
    """Extract ChromaDB where filter from query keywords.

    Returns a ChromaDB-compatible where clause like:
        {"domain": "SCM"}
        {"process": "재고관리"}
        {"$and": [{"domain": "IT"}, {"process": "주문처리"}]}
    Or None if no filter is extracted.
    """
    query_lower = query.lower()
    matched_domain: str | None = None
    matched_process: str | None = None

    # Check domain keywords
    for domain, keywords in DOMAIN_KEYWORDS.items():
        for kw in keywords:
            if kw.lower() in query_lower:
                matched_domain = domain
                break
        if matched_domain:
            break

    # Check process keywords
    for process, keywords in PROCESS_KEYWORDS.items():
        for kw in keywords:
            if kw.lower() in query_lower:
                matched_process = process
                break
        if matched_process:
            break

    if matched_domain and matched_process:
        result = {"$and": [{"domain": matched_domain}, {"process": matched_process}]}
        logger.info(f"Filter extracted: domain={matched_domain}, process={matched_process}")
        return result
    elif matched_domain:
        logger.info(f"Filter extracted: domain={matched_domain}")
        return {"domain": matched_domain}
    elif matched_process:
        logger.info(f"Filter extracted: process={matched_process}")
        return {"process": matched_process}

    return None
