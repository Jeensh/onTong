"""Agent 3 (위치 파악) 쿼리.

Intent ``explain`` 핸들러. 자연어 키워드 → Term 매칭 → 연결된 Step / Method /
Class / Table 위치를 반환한다.

자연어 → 키워드 추출 우선순위:
1. parameters["keyword"]/[ "query"] 명시값
2. Gemini LLM (GEMINI_API_KEY 등록 시) — 자연어 의도 파악
3. split + stopwords (deterministic fallback)

Agent 1/2의 결정적 영역은 LLM을 사용하지 않는다. Agent 3는 자연어 입력
파싱이 핵심이라 LLM이 가장 효과적인 부분만 적용. 호출 실패/타임아웃 시
즉시 split fallback으로 떨어져 가용성 보장.
"""

from __future__ import annotations

import logging
import os

from ..client import OntologyClient, get_client
from backend.shared.contracts.ontology import (
    OntologyRequest,
    OntologyResponse,
    Status,
)

logger = logging.getLogger(__name__)

DEFAULT_SCOPE = ["source", "table", "process"]

# Gemini 모델 — 무료 tier로 충분. 환경변수로 override 가능.
DEFAULT_GEMINI_MODEL = os.environ.get(
    "GEMINI_MODEL", "gemini/gemini-2.5-flash"
)
LLM_TIMEOUT_SECONDS = float(os.environ.get("LOCATOR_LLM_TIMEOUT", "8"))

_LLM_PROMPT = (
    "다음 한국어 업무 질문에서 그래프 검색에 쓸 핵심 키워드만 콤마로 나열하시오.\n"
    "- 조사/접속어/의문사 제거\n"
    "- SC코드(SC070 등), 영문 용어(Edging 등), 한국어 명사 위주\n"
    "- 키워드 외 다른 텍스트 출력 금지\n\n"
    "예시:\n"
    "  질문: \"Edging 로직 어디 있어?\"\n"
    "  응답: Edging\n"
    "  질문: \"SC070 기준값을 어디서 체크해?\"\n"
    "  응답: SC070, 기준값\n"
    "  질문: \"분할수랑 실수율 계산하는 곳 알려줘\"\n"
    "  응답: 분할수, 실수율\n\n"
    "질문: \"{q}\"\n"
    "응답:"
)


async def _extract_with_llm(text: str) -> list[str]:
    """Gemini로 자연어 → 키워드 추출. 실패 시 빈 리스트."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return []
    try:
        from litellm import acompletion

        resp = await acompletion(
            model=DEFAULT_GEMINI_MODEL,
            messages=[{"role": "user", "content": _LLM_PROMPT.format(q=text)}],
            api_key=api_key,
            timeout=LLM_TIMEOUT_SECONDS,
            temperature=0.0,
        )
        content = (resp.choices[0].message.content or "").strip()
        # "키워드:" 같은 prefix 제거
        if ":" in content and len(content.split(":", 1)[0]) < 12:
            content = content.split(":", 1)[1].strip()
        keywords = [k.strip() for k in content.split(",") if k.strip()]
        # 너무 길면 자른다 (비정상 응답 방어)
        return [k for k in keywords if len(k) <= 40][:8]
    except Exception as exc:  # noqa: BLE001 — LLM 실패는 fallback으로 처리
        logger.warning("LLM keyword extraction failed (%s); falling back", exc)
        return []


def _extract_with_split(text: str) -> list[str]:
    """단순 토큰화 fallback. 한국어 명사/영문 토큰 보존, 의문사·연결어 제거."""
    tokens = [t.strip(" ?,.!:;") for t in text.split() if len(t.strip()) >= 2]
    stopwords = {
        "어디", "어디에", "어디서", "어디야",
        "있어", "있나", "있어요", "있나요",
        "체크", "위치", "알려줘", "알려주세요",
        "곳을", "곳이", "곳은", "곳도",
    }
    return [t for t in tokens if t and t not in stopwords]


async def _extract_keywords(
    natural_language: str | None, parameters: dict
) -> tuple[list[str], str]:
    """키워드 + 추출 방식 메타데이터. method ∈ {explicit, llm, split, none}."""
    explicit = parameters.get("keyword") or parameters.get("query")
    if isinstance(explicit, str) and explicit.strip():
        return [explicit.strip()], "explicit"
    if not natural_language:
        return [], "none"

    llm_keywords = await _extract_with_llm(natural_language)
    if llm_keywords:
        return llm_keywords, "llm"

    return _extract_with_split(natural_language), "split"


def _match_terms(client: OntologyClient, keywords: list[str]) -> list[dict]:
    if not keywords:
        return []
    rows = client.query(
        "MATCH (t:Term) "
        "WHERE ANY(kw IN $kws WHERE "
        "  t.korean_name CONTAINS kw OR "
        "  t.english_name CONTAINS kw OR "
        "  ANY(alias IN t.aliases WHERE alias CONTAINS kw)) "
        "RETURN t.id AS id, t.korean_name AS korean, t.english_name AS english, "
        "       t.category AS category, t.description AS description",
        kws=keywords,
    )
    return rows


def _process_locations(
    client: OntologyClient, term_ids: list[str]
) -> list[dict]:
    if not term_ids:
        return []
    rows = client.query(
        "MATCH (t:Term)-[r:REFERS_TO_PROCESS]->(s:Step) "
        "WHERE t.id IN $ids "
        "RETURN DISTINCT s.step_number AS step_number, "
        "       s.korean_name AS korean_name, "
        "       collect(DISTINCT r.role) AS roles "
        "ORDER BY step_number",
        ids=term_ids,
    )
    return rows


def _source_locations(
    client: OntologyClient, step_numbers: list[int]
) -> list[dict]:
    if not step_numbers:
        return []
    rows = client.query(
        "MATCH (m:Method)-[:CALCULATES]->(s:Step) "
        "WHERE s.step_number IN $nums "
        "OPTIONAL MATCH (c:Class)-[:CONTAINS]->(m) "
        "RETURN DISTINCT c.name AS class_name, m.name AS method_name, "
        "       c.file AS file_path, s.step_number AS step_number "
        "ORDER BY step_number, class_name, method_name",
        nums=step_numbers,
    )
    return rows


def _data_locations(
    client: OntologyClient, step_numbers: list[int]
) -> list[dict]:
    if not step_numbers:
        return []
    rows = client.query(
        "MATCH (s:Step)-[:USES_STANDARD]->(std:Standard)<-[:MAPS_TO_STANDARD]-(t:Table) "
        "WHERE s.step_number IN $nums "
        "RETURN DISTINCT t.name AS table_name, std.code AS standard_code, "
        "       t.schema_name AS schema_name "
        "ORDER BY table_name",
        nums=step_numbers,
    )
    return rows


def _related_terms(client: OntologyClient, term_ids: list[str]) -> list[dict]:
    if not term_ids:
        return []
    rows = client.query(
        "MATCH (t:Term)-[r:RELATED_TO|IS_A|SYNONYM_OF]->(rel:Term) "
        "WHERE t.id IN $ids "
        "RETURN DISTINCT rel.id AS id, rel.korean_name AS korean, "
        "       rel.english_name AS english, type(r) AS relation",
        ids=term_ids,
    )
    return rows


async def locate(req: OntologyRequest) -> OntologyResponse:
    """explain intent 핸들러."""
    keywords, method = await _extract_keywords(req.natural_language, req.parameters)
    scope = req.parameters.get("scope") or DEFAULT_SCOPE

    if not keywords:
        return OntologyResponse(
            request_id=req.request_id,
            status=Status.NEED_MORE_INFO,
            result={"message": "검색할 키워드가 필요합니다"},
        )

    client = get_client()
    matched = _match_terms(client, keywords)

    extraction_meta = {
        "extraction_method": method,
        "extracted_keywords": keywords,
    }

    if not matched:
        return OntologyResponse(
            request_id=req.request_id,
            status=Status.SUCCESS,
            confidence=0.3,
            result={
                "summary": f"키워드 {keywords}와 매칭되는 업무 용어를 찾지 못했습니다",
                "matched_terms": [],
                "process_locations": [],
                "source_locations": [],
                "data_locations": [],
                "related_terms": [],
                **extraction_meta,
            },
        )

    term_ids = [t["id"] for t in matched]
    process_loc = _process_locations(client, term_ids) if "process" in scope else []
    step_nums = [p["step_number"] for p in process_loc]
    source_loc = _source_locations(client, step_nums) if "source" in scope else []
    data_loc = _data_locations(client, step_nums) if "table" in scope else []
    related = _related_terms(client, term_ids)

    summary_parts = []
    if matched:
        summary_parts.append(f"용어 {len(matched)}개 매칭")
    if process_loc:
        summary_parts.append(f"Step {len(process_loc)}개")
    if source_loc:
        summary_parts.append(f"메서드 {len(source_loc)}개")
    if data_loc:
        summary_parts.append(f"테이블 {len(data_loc)}개")
    summary = " · ".join(summary_parts) if summary_parts else "결과 없음"

    # ── 그래프 + path edges 빌드 ────────────────────────────
    nodes: list[dict] = []
    edges: list[dict] = []
    path_keys: list[str] = []

    cypher = (
        "// Term 매칭 → REFERS_TO_PROCESS → Step → CALCULATES → Method\n"
        "MATCH (t:Term) WHERE t.korean_name CONTAINS ... OR english_name OR aliases\n"
        "MATCH (t)-[:REFERS_TO_PROCESS]->(s:Step)<-[:CALCULATES]-(m:Method)<-[:CONTAINS]-(c:Class)"
    )

    seed_ids: list[str] = []
    for t in matched:
        tid = f"term:{t['id']}"
        seed_ids.append(tid)
        nodes.append({"id": tid, "label": t["korean"], "group": "term"})

    for p in process_loc:
        sid = f"step:{p['step_number']}"
        if not any(n["id"] == sid for n in nodes):
            nodes.append(
                {"id": sid, "label": f"Step {p['step_number']}\n{p['korean_name']}", "group": "step"}
            )
        # term → step 엣지
        for tid in seed_ids:
            edges.append({"from": tid, "to": sid, "label": "REFERS_TO"})
            path_keys.append(f"{tid}->{sid}")

    for src in source_loc:
        mid = f"method:{src['class_name']}.{src['method_name']}"
        if not any(n["id"] == mid for n in nodes):
            nodes.append(
                {"id": mid, "label": f"{src['class_name']}\n.{src['method_name']}()", "group": "method"}
            )
        sid = f"step:{src['step_number']}"
        edges.append({"from": mid, "to": sid, "label": "CALCULATES"})
        path_keys.append(f"{mid}->{sid}")

    for d in data_loc:
        tid = f"table:{d['table_name']}"
        if not any(n["id"] == tid for n in nodes):
            nodes.append({"id": tid, "label": d["table_name"], "group": "table"})
        # Step ← Table (간접) — 중복 막기 위해 step_nums에 매칭되는 SC만
        if d.get("standard_code"):
            std_id = f"std:{d['standard_code']}"
            if not any(n["id"] == std_id for n in nodes):
                nodes.append({"id": std_id, "label": d["standard_code"], "group": "standard"})
            edges.append({"from": tid, "to": std_id, "label": "MAPS_TO_STANDARD"})

    for rel in related:
        rid = f"term:{rel['id']}"
        if not any(n["id"] == rid for n in nodes):
            nodes.append({"id": rid, "label": rel["korean"], "group": "term"})
        for tid in seed_ids:
            edges.append({"from": tid, "to": rid, "label": rel["relation"]})

    return OntologyResponse(
        request_id=req.request_id,
        status=Status.SUCCESS,
        confidence=0.9 if matched else 0.3,
        result={
            "summary": summary,
            "matched_terms": matched,
            "process_locations": process_loc,
            "source_locations": source_loc,
            "data_locations": data_loc,
            "related_terms": related,
            "ontology_trace": {
                "nodes": nodes,
                "edges": edges,
                "seed_ids": seed_ids,
                "path_edge_keys": path_keys,
                "cypher": cypher,
            },
            **extraction_meta,
        },
    )
