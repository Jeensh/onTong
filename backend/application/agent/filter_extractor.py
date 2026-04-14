"""Extract metadata filters from user queries for ChromaDB pre-filtering."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


def _get_templates_file() -> Path:
    from backend.core.config import settings
    return Path(settings.wiki_dir) / ".ontong" / "metadata_templates.json"

# Fallback keywords (used when template file is not available)
_FALLBACK_DOMAIN_KEYWORDS: dict[str, list[str]] = {
    "SCM": ["SCM", "scm", "공급망", "공급체인", "supply chain", "주문", "발주", "물류", "배송"],
    "ERP": ["ERP", "erp", "마스터데이터", "모듈", "인터페이스"],
    "MES": ["MES", "mes", "생산", "제조", "공정", "라인", "설비"],
    "인프라": ["인프라", "서버", "네트워크", "보안", "모니터링", "IT"],
    "기획": ["기획", "예산", "프로젝트", "KPI", "전략"],
    "재무": ["재무", "회계", "결산", "세무", "원가", "정산", "경비"],
    "인사": ["인사", "채용", "교육", "평가", "급여", "HR", "온보딩"],
}

_FALLBACK_PROCESS_KEYWORDS: dict[str, list[str]] = {
    "주문": ["주문", "발주", "오더", "order"],
    "품질": ["품질", "검수", "검사", "불량", "QC"],
    "물류": ["물류", "배송", "출하", "운송"],
    "생산계획": ["생산계획", "생산 계획", "생산일정"],
    "설비보전": ["설비", "보전", "점검", "maintenance"],
}


def _load_keywords_from_templates() -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    """Load domain and process keywords from metadata_templates.json.

    Returns (domain_keywords, process_keywords) dicts mapping
    metadata value → list of query keywords that should match it.
    """
    templates_file = _get_templates_file()
    if not templates_file.exists():
        return _FALLBACK_DOMAIN_KEYWORDS, _FALLBACK_PROCESS_KEYWORDS

    try:
        data = json.loads(templates_file.read_text(encoding="utf-8"))
        dp: dict[str, list[str]] = data.get("domain_processes", {})

        domain_keywords: dict[str, list[str]] = {}
        process_keywords: dict[str, list[str]] = {}

        for domain, processes in dp.items():
            # Domain keyword: the domain name itself (+ lowercase)
            kws = [domain, domain.lower()]
            # Add all process names under this domain as domain hints
            for proc in processes:
                kws.append(proc)
            domain_keywords[domain] = list(dict.fromkeys(kws))  # dedupe, preserve order

            # Each process gets its own keyword entry
            for proc in processes:
                process_keywords[proc] = [proc, proc.lower()]

        # Merge fallback keywords for richer matching
        for domain, fallback_kws in _FALLBACK_DOMAIN_KEYWORDS.items():
            if domain in domain_keywords:
                existing = set(domain_keywords[domain])
                for kw in fallback_kws:
                    if kw not in existing:
                        domain_keywords[domain].append(kw)

        return domain_keywords, process_keywords

    except Exception as e:
        logger.warning(f"Failed to load templates for filter extraction: {e}")
        return _FALLBACK_DOMAIN_KEYWORDS, _FALLBACK_PROCESS_KEYWORDS


def extract_metadata_filter(query: str) -> dict | None:
    """Extract ChromaDB where filter from query keywords.

    Returns a ChromaDB-compatible where clause like:
        {"domain": "SCM"}
        {"process": "재고관리"}
        {"$and": [{"domain": "IT"}, {"process": "주문처리"}]}
    Or None if no filter is extracted.
    """
    domain_keywords, process_keywords = _load_keywords_from_templates()

    query_lower = query.lower()
    matched_domain: str | None = None
    matched_process: str | None = None

    # Check domain keywords
    for domain, keywords in domain_keywords.items():
        for kw in keywords:
            if kw.lower() in query_lower:
                matched_domain = domain
                break
        if matched_domain:
            break

    # Check process keywords
    for process, keywords in process_keywords.items():
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


# ── Path filter extraction (L2: Path-Aware RAG) ─────────────────────

def extract_path_filter(query: str) -> dict | None:
    """Extract path_depth_1 filter from query keywords.

    Uses the same domain vocabulary as extract_metadata_filter() but targets
    the path_depth_1 ChromaDB metadata field. This narrows the ANN search
    space at enterprise scale (500k docs → single folder).

    Returns a ChromaDB-compatible where clause like {"path_depth_1": "인프라"}
    or None if no path hint is found.
    """
    if os.environ.get("ONTONG_PATH_FILTER_ENABLED", "true").lower() != "true":
        return None

    domain_keywords, _ = _load_keywords_from_templates()
    query_lower = query.lower()

    for domain, keywords in domain_keywords.items():
        for kw in keywords:
            if kw.lower() in query_lower:
                logger.info(f"Path filter extracted: path_depth_1={domain}")
                return {"path_depth_1": domain}

    return None


# ── Tag extraction (B1) ──────────────────────────────────────────────

# Cosine distance threshold for tag<->query semantic match.
# Calibrated for OpenAI text-embedding-3-small on short Korean strings:
# very-close 0.0~0.40, related 0.40~0.55, weak 0.55~0.70.
QUERY_TAG_DIST_THRESHOLD = 0.55


def extract_query_tags(query: str, top_k: int = 5) -> list[str]:
    """Find existing system tags that semantically match the user query.

    Returns up to `top_k` existing tag names whose embedding is within
    QUERY_TAG_DIST_THRESHOLD of the query embedding. Used by RAG retrieval
    to (a) boost-rerank documents whose tags intersect, and (b) provide a
    tag-only fallback when domain/process filtering returns zero results.

    Returns [] if the tag registry is unavailable.
    """
    try:
        from backend.application.metadata.tag_registry import tag_registry
    except Exception:
        return []
    if not tag_registry.is_connected:
        return []
    try:
        results = tag_registry.find_similar(query, top_k=top_k)
    except Exception as e:
        logger.warning(f"extract_query_tags failed: {e}")
        return []
    matched: list[str] = []
    for r in results:
        if r.get("distance", 1.0) < QUERY_TAG_DIST_THRESHOLD:
            matched.append(r["tag"])
    if matched:
        logger.info(f"Query tags extracted: {matched}")
    return matched
