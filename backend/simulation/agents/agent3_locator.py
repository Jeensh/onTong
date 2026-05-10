"""Agent 3 — 비즈니스 용어 → 소스/테이블/프로세스 위치 + 코드 미리보기.

Phase 3 재작성:
- ontology_client (explain intent) — Section 2가 매칭된 위치 식별
- 각 source_location에 대해 slab-design Java 파일에서 ±N줄 snippet 첨부
- ontology가 미응답이어도 fallback: 키워드 → 사전 매핑된 demo locations 반환
- A2 핸드오프 힌트: 첫 매칭의 step_id를 응답에 포함 → 프론트에서 "이 step 시뮬" 버튼이 사용
"""

from __future__ import annotations

import logging
import os
import uuid
from typing import Literal, Optional

from pydantic import BaseModel, Field

from backend.shared.contracts.ontology import Intent, OntologyRequest, Status

from ..client.ontology_client import get_ontology_client

logger = logging.getLogger(__name__)

DEFAULT_SCOPE = ["source", "table", "process"]


# ─── 입력 / 출력 ────────────────────────────────────────────────────


class Agent3Request(BaseModel):
    natural_language_query: str
    search_scope: list[Literal["source", "table", "process"]] = Field(
        default_factory=lambda: list(DEFAULT_SCOPE)
    )
    preview_lines: int = 20  # ±10줄 (총 ~20줄)
    include_preview: bool = True


class SourceLocation(BaseModel):
    file_path: str
    class_name: Optional[str] = None
    method_name: Optional[str] = None
    line: Optional[int] = None
    preview: Optional[str] = None  # 코드 snippet
    step_id: Optional[str] = None  # sandbox에서 시뮬 가능한 step (handoff 힌트)


class Agent3Result(BaseModel):
    request_id: str
    status: Literal["success", "partial", "need_more_info", "unsupported", "error"]
    summary: str = ""
    matched_terms: list[dict] = Field(default_factory=list)
    process_locations: list[dict] = Field(default_factory=list)
    source_locations: list[SourceLocation] = Field(default_factory=list)
    data_locations: list[dict] = Field(default_factory=list)
    related_terms: list[dict] = Field(default_factory=list)
    extraction_method: Literal["explicit", "llm", "split", "none"] = "none"
    extracted_keywords: list[str] = Field(default_factory=list)
    ontology_trace: Optional[dict] = None
    raw_message: Optional[str] = None
    handoff_step_id: Optional[str] = None  # Phase 3 신규 — A2로 넘길 step


# ─── slab-design demo 키워드 매핑 (ontology 미가용 시 fallback) ─────


_SLAB_DESIGN_ROOT = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "sample-repos", "slab-design"
)


def _slab_path(rel: str) -> str:
    return os.path.normpath(os.path.join(_SLAB_DESIGN_ROOT, rel))


_DEMO_KEYWORD_MAP: list[dict] = [
    # (keyword, file rel-path, class, method, step_id)
    {
        "keywords": ["단중상한", "secondWgtHigh", "포장단중 상한", "2차 단중 상한"],
        "file": "slab-design-feature/src/main/java/com/example/slabdesign/feature/sd/process/working/action/SdSecondWgtHighAction.java",
        "class": "SdSecondWgtHighAction",
        "method": "execute",
        "step_id": "slab_weight",  # 가까운 sandbox step
    },
    {
        "keywords": ["Slab 매수", "Slab 매수", "slabCount", "매수 산정", "slab count"],
        "file": "slab-design-feature/src/main/java/com/example/slabdesign/feature/sd/process/working/action/SdSlabCountAction.java",
        "class": "SdSlabCountAction",
        "method": "execute",
        "step_id": "slab_count",
    },
    {
        "keywords": ["분할수", "splitRange", "split range", "분할 범위"],
        "file": "slab-design-feature/src/main/java/com/example/slabdesign/feature/sd/process/working/action/SdSplitRangeAction.java",
        "class": "SdSplitRangeAction",
        "method": "execute",
        "step_id": "split_range",
    },
    {
        "keywords": ["Slab 두께", "Slab 두께", "slabThickness", "두께 산정", "step 1"],
        "file": "slab-design-feature/src/main/java/com/example/slabdesign/feature/sd/process/working/action/SdThicknessAction.java",
        "class": "SdThicknessAction",
        "method": "execute",
        "step_id": "thickness",
    },
    {
        "keywords": ["실수율", "productivity", "누적 실수율", "cumulative", "yield"],
        "file": "slab-design-feature/src/main/java/com/example/slabdesign/feature/sd/process/std/service/ProductivityService.java",
        "class": "ProductivityService",
        "method": "cumulativeProductivity",
        "step_id": "productivity",
    },
    {
        "keywords": ["검증", "validator", "DG001", "DG002", "DG003", "DG004", "DG005", "재고주문", "정합성"],
        "file": "slab-design-feature/src/main/java/com/example/slabdesign/feature/sd/process/working/action/SdOrderValidator.java",
        "class": "SdOrderValidator",
        "method": "validate",
        "step_id": "validator",
    },
    {
        "keywords": ["품종", "품명", "PRODUCT_TYPE_CD", "PRODUCT_NAME_CD", "PROD_KIND_CD"],
        "file": "slab-design-feature/src/main/java/com/example/slabdesign/feature/sd/process/working/action/SdThicknessAction.java",
        "class": "SdThicknessAction",
        "method": "execute",
        "step_id": "thickness",
    },
]


def _match_demo_keywords(query: str) -> list[dict]:
    """질의에 포함된 키워드 기반으로 매핑. 다중 매칭 가능."""
    q_lower = query.lower()
    matches = []
    for entry in _DEMO_KEYWORD_MAP:
        for kw in entry["keywords"]:
            if kw.lower() in q_lower:
                matches.append({**entry, "matched_keyword": kw})
                break
    return matches


# ─── 코드 snippet 추출 ──────────────────────────────────────────────


def _extract_snippet(file_path: str, target_method: Optional[str], lines_around: int = 10) -> tuple[Optional[str], Optional[int]]:
    """파일에서 method 선언이 있는 라인 ±N줄을 snippet으로 반환.

    Returns:
        (snippet_text, line_number)
    """
    try:
        with open(file_path, "r", encoding="utf-8") as fh:
            lines = fh.readlines()
    except (OSError, UnicodeDecodeError) as e:
        logger.warning("snippet read failed: %s — %s", file_path, e)
        return None, None

    line_no = None
    if target_method:
        # 단순 검색: "void <method>(" 또는 "<RetType> <method>("
        pattern_indicators = [f" {target_method}(", f"\t{target_method}("]
        for i, line in enumerate(lines):
            if any(ind in line for ind in pattern_indicators) and ("public" in line or "private" in line or "protected" in line or "static" in line or "void" in line or " " in line):
                # method declaration heuristic
                if "(" in line and ")" in line.rstrip():
                    line_no = i + 1
                    break
                if "(" in line:
                    line_no = i + 1
                    break

    if line_no is None:
        # fallback: 파일의 첫 method (public/protected/private 선언)
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith(("public ", "protected ", "private ")) and "(" in stripped:
                line_no = i + 1
                break

    if line_no is None:
        # 마지막 fallback: 파일 처음 30줄
        snippet = "".join(lines[:30])
        return snippet, 1

    start = max(0, line_no - 1 - lines_around)
    end = min(len(lines), line_no + lines_around)
    snippet = "".join(lines[start:end])
    return snippet, line_no


# ─── 메인 실행 ──────────────────────────────────────────────────────


async def execute_agent3(req: Agent3Request) -> Agent3Result:
    request_id = str(uuid.uuid4())

    # 1) ontology — best-effort
    ontology_payload = await _query_ontology(req, request_id)
    matched_terms = ontology_payload.get("matched_terms", [])
    process_locations = ontology_payload.get("process_locations", [])
    source_locs_raw: list[dict] = ontology_payload.get("source_locations", [])
    data_locations = ontology_payload.get("data_locations", [])
    related_terms = ontology_payload.get("related_terms", [])
    extraction_method = ontology_payload.get("extraction_method", "none")
    extracted_keywords = ontology_payload.get("extracted_keywords", [])

    # 2) ontology가 비어있으면 demo keyword fallback
    if not source_locs_raw:
        demo_matches = _match_demo_keywords(req.natural_language_query)
        for m in demo_matches:
            source_locs_raw.append({
                "file_path": _slab_path(m["file"]),
                "class_name": m["class"],
                "method_name": m["method"],
                "step_id": m["step_id"],
            })
            extracted_keywords.append(m["matched_keyword"])
        if demo_matches and extraction_method == "none":
            extraction_method = "split"

    # 3) source preview 첨부
    source_locations: list[SourceLocation] = []
    for loc in source_locs_raw:
        sl = SourceLocation(
            file_path=loc.get("file_path", ""),
            class_name=loc.get("class_name"),
            method_name=loc.get("method_name"),
            line=loc.get("line"),
            step_id=loc.get("step_id"),
        )
        if req.include_preview and sl.file_path:
            snippet, line_no = _extract_snippet(
                sl.file_path,
                sl.method_name,
                lines_around=max(5, req.preview_lines // 2),
            )
            if snippet:
                sl.preview = snippet
                if line_no and not sl.line:
                    sl.line = line_no
        source_locations.append(sl)

    # 4) handoff step_id (첫 매칭)
    handoff_step_id = next(
        (s.step_id for s in source_locations if s.step_id),
        None,
    )

    # 5) status
    if not source_locations and not matched_terms and not process_locations:
        status = "unsupported"
        summary = f"'{req.natural_language_query}' 매칭된 위치 없음"
    elif source_locations:
        status = "success"
        summary = f"{len(source_locations)}개 source 위치 + {len(matched_terms)}개 용어 매칭"
    else:
        status = "partial"
        summary = f"{len(matched_terms)}개 용어 매칭 (소스 위치 없음)"

    return Agent3Result(
        request_id=request_id,
        status=status,
        summary=summary,
        matched_terms=matched_terms,
        process_locations=process_locations,
        source_locations=source_locations,
        data_locations=data_locations,
        related_terms=related_terms,
        extraction_method=extraction_method,
        extracted_keywords=extracted_keywords,
        ontology_trace=ontology_payload.get("ontology_trace"),
        raw_message=ontology_payload.get("raw_message"),
        handoff_step_id=handoff_step_id,
    )


async def _query_ontology(req: Agent3Request, request_id: str) -> dict:
    """Section 2 ontology — graceful fallback.

    SIMULATION_SKIP_ONTOLOGY=1 (기본) → 즉시 fallback. Neo4j 미가용 환경 회피.
    """
    import asyncio
    import os
    if os.getenv("SIMULATION_SKIP_ONTOLOGY", "1") == "1":
        return {"unavailable": True, "raw_message": "ontology skipped"}
    try:
        client = get_ontology_client()
        ont_req = OntologyRequest(
            request_id=request_id,
            intent=Intent.EXPLAIN,
            natural_language=req.natural_language_query,
            parameters={"scope": req.search_scope},
        )
        resp = await asyncio.wait_for(client.query(ont_req), timeout=3.0)
    except (asyncio.TimeoutError, Exception) as exc:
        logger.info("ontology query unavailable: %s", exc)
        return {"unavailable": True, "raw_message": str(exc)}

    if resp.status in (Status.UNSUPPORTED, Status.ERROR, Status.NEED_MORE_INFO):
        return {
            "raw_message": (resp.result or {}).get("message") if resp.result else None,
        }

    data = resp.result or {}
    return {
        "matched_terms": data.get("matched_terms", []),
        "process_locations": data.get("process_locations", []),
        "source_locations": data.get("source_locations", []),
        "data_locations": data.get("data_locations", []),
        "related_terms": data.get("related_terms", []),
        "extraction_method": data.get("extraction_method", "none"),
        "extracted_keywords": data.get("extracted_keywords", []),
        "ontology_trace": data.get("ontology_trace"),
    }
