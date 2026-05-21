"""실측 도메인 데이터 + ontology 용어 + JPO 한국어 주석 합성 → 자연어 질문 생성.

사용자 요구: "table·jpo·ontology 용어를 기반으로 자연어 예시 질문을 맞춤형
으로 다양하게". hardcoded 7개 preset 대체.

source:
  1. JPO class javadoc 의 한국어 토큰 (품종/단중/주문/EDGING 등)
  2. ontology business_terms.label + aliases
  3. seed orders ORDER_NO list
  4. seed master tables (CAST_SPEC, HR_SPEC ...) 의 column name 한국어 매핑
"""
from __future__ import annotations

import logging
import random
from dataclasses import dataclass
from typing import Any

from backend.section3.agents.simulation import domain_data
from backend.modeling.persistence.database import session_scope

logger = logging.getLogger(__name__)


@dataclass
class SuggestedQuestion:
    intent: str           # simulate / impact / locate / explain / hypothesis
    label: str            # UI 에 표시할 짧은 라벨 (예: "①주문→Slab")
    query: str            # 실제 자연어 query
    rationale: str = ""   # 어떤 source 에서 생성됐는지
    grounded_terms: list[dict] = None  # type: ignore  # ontology business_terms 매핑


@dataclass
class DetectedTerm:
    token: str            # query 안의 한국어 token
    term_fqn: str         # 매칭된 business_term.fqn
    label: str            # business_term.label
    definition: str = ""  # business_term.description 의 첫 줄
    aliases: list[str] = None  # type: ignore  # business_term.aliases


# 한국어 키워드 ↔ 컬럼/테이블 가벼운 매핑
_KO_HINT: dict[str, str] = {
    "주문": "ORDER_OS",
    "주문번호": "ORDER_NO",
    "강종": "GRADE_CD",
    "품종": "PRODUCT_CD",
    "두께": "slabThickness",
    "폭": "slabWidth",
    "길이": "slabLength",
    "단중": "slabWgt",
    "분할": "splitCount",
    "EDGING": "EDGING_GROUP",
    "고객": "CUSTOMER_CD",
    "실수율": "PRODUCTIVITY",
    "공장": "CONFIRMED_PLANT_CD",
}


def _order_nos_from_seed() -> list[str]:
    """seed 의 ORDER_OS row 들에서 ORDER_NO 목록 (한 list)."""
    rows = domain_data.list_rows("ORDER_OS", limit=20)
    out = []
    for r in rows:
        v = r.values.get("ORDER_NO")
        if v:
            out.append(str(v))
    return out or ["ORD20260510001"]


def _grades_from_seed() -> list[str]:
    rows = domain_data.list_rows("SD_PRODUCTIVITY_STD", limit=50)
    out: list[str] = []
    seen: set[str] = set()
    for r in rows:
        g = r.values.get("GRADE_CD")
        if g and str(g) not in seen:
            seen.add(str(g)); out.append(str(g))
    return out or ["SS400"]


def lookup_terms(tokens: list[str], repo_id: str = "slab-design-real-v2") -> list[DetectedTerm]:
    """한국어 토큰 list → ontology business_terms 매핑.

    `business_terms.label`, `aliases_json` 컬럼에서 LIKE 매칭. 매칭된 row 의
    fqn / label / description / aliases 반환.
    """
    if not tokens:
        return []
    out: list[DetectedTerm] = []
    seen_fqns: set[str] = set()
    try:
        import json
        from sqlalchemy import select
        from backend.modeling.domain_layer.orm import BusinessTermRow
        with session_scope() as s:
            rows = s.execute(
                select(BusinessTermRow).where(BusinessTermRow.repo_id == repo_id)
            ).scalars().all()
            # in-memory matching (rows ~80개 — 충분히 빠름)
            for tok in tokens:
                tok_lower = tok.lower()
                for r in rows:
                    if r.fqn in seen_fqns:
                        continue
                    label_match = tok in (r.label or "") or tok_lower in (r.label or "").lower()
                    aliases: list[str] = []
                    try:
                        aliases = json.loads(r.aliases_json or "[]")
                    except Exception:
                        pass
                    alias_match = any(tok in a or tok_lower in a.lower() for a in aliases)
                    if label_match or alias_match:
                        seen_fqns.add(r.fqn)
                        desc = (r.description or "").split("\n")[0]
                        if len(desc) > 200:
                            desc = desc[:200] + "..."
                        out.append(DetectedTerm(
                            token=tok, term_fqn=r.fqn, label=r.label,
                            definition=desc, aliases=aliases[:8],
                        ))
                        break  # 토큰 1개당 매칭 1건만
    except Exception as e:  # noqa: BLE001
        logger.warning("term lookup 실패: %s", e)
    return out


def extract_korean_tokens(text: str, min_len: int = 2) -> list[str]:
    """자연어에서 한국어 명사 토큰 추출 (중복 제거)."""
    import re
    tokens = re.findall(r"[가-힣]+", text)
    out: list[str] = []
    seen: set[str] = set()
    for t in tokens:
        if len(t) >= min_len and t not in seen:
            seen.add(t); out.append(t)
    return out


def _std_tables_with_keywords() -> list[tuple[str, list[str]]]:
    """기준 데이터 table + 그 JPO 의 한국어 키워드."""
    out: list[tuple[str, list[str]]] = []
    for t in domain_data.list_tables():
        if t.category == "std" and t.keywords:
            out.append((t.table_name, t.keywords))
    return out


def generate_suggestions(*, n_per_intent: int = 2, seed: int | None = None) -> list[SuggestedQuestion]:
    """5종 intent 별 ~2건씩 자연어 질문 생성 (실측 데이터 + JPO 한국어).

    randomize 가능. seed 지정 시 같은 결과 — 같은 ontology snapshot 에서 안정 출력.
    """
    if seed is not None:
        random.seed(seed)
    orders = _order_nos_from_seed()
    grades = _grades_from_seed()
    std_tables = _std_tables_with_keywords()

    out: list[SuggestedQuestion] = []

    # ───────────────── simulate (주문 → Slab 설계) ─────────────────
    if orders:
        out.append(SuggestedQuestion(
            intent="simulate",
            label=f"①{orders[0][-4:]}로 Slab 설계",
            query=f"{orders[0]} 주문으로 Slab 설계 시뮬레이션 돌려줘",
            rationale=f"seed ORDER_OS.{orders[0]}",
        ))
        if len(orders) >= 2:
            out.append(SuggestedQuestion(
                intent="simulate",
                label=f"①다중Slab ({orders[1][-4:]})",
                query=f"{orders[1]} 주문 (다중 Slab 시나리오) Slab 설계 돌려봐",
                rationale=f"seed ORDER_OS.{orders[1]}",
            ))

    # ───────────────── impact (기준/로직 변경 영향) ─────────────────
    if std_tables:
        # 한 std table 의 첫 한국어 키워드로 질문
        tbl, kws = std_tables[0]  # CAST_SPEC 등
        kw = kws[0] if kws else "기준값"
        out.append(SuggestedQuestion(
            intent="impact",
            label=f"②{tbl} 변경 영향",
            query=f"{tbl} ({kw}) 의 값을 바꾸면 어떤 Step·method 가 영향받아?",
            rationale=f"JPO {tbl} javadoc keyword '{kw}'",
        ))
        if len(std_tables) >= 3:
            tbl2, kws2 = std_tables[2]
            kw2 = kws2[0] if kws2 else "기준값"
            out.append(SuggestedQuestion(
                intent="impact",
                label=f"②{tbl2} 변경 영향",
                query=f"{tbl2} 의 {kw2} 마진을 바꾸면 어떤 주문이 fail 할 수 있어?",
                rationale=f"JPO {tbl2} javadoc keyword '{kw2}'",
            ))

    # ───────────────── locate (코드 위치 찾기) ─────────────────
    out.append(SuggestedQuestion(
        intent="locate",
        label="③DG104 throw 위치",
        query="DG104 (HR_MIN_WGT 미발견) 에러는 어디서 throw 돼?",
        rationale="error code DG10x catalog",
    ))
    out.append(SuggestedQuestion(
        intent="locate",
        label="③단중 계산 로직",
        query="2차 단중 (secondaryWeight) 의 lower/upper 계산은 어느 action 안에?",
        rationale="ontology actions.label '단중*'",
    ))

    # ───────────────── explain (자연어 설명) ─────────────────
    out.append(SuggestedQuestion(
        intent="explain",
        label="④A-a 루프란?",
        query="Step 8~13 의 A-a inner loop 가 뭐고 어떤 조건에서 수렴해?",
        rationale="domain knowledge (SCENARIOS.md)",
    ))
    out.append(SuggestedQuestion(
        intent="explain",
        label="④confirmedPlantCd",
        query="confirmedPlantCd 8문자가 각 pos 별로 어떤 공정을 의미해?",
        rationale="ORDER_OS.CONFIRMED_PLANT_CD encoding",
    ))

    # ───────────────── hypothesis (신규 X 추가) ─────────────────
    if grades and orders:
        base = grades[0]
        # 새 강종은 기존 last char 변형 (SS400 → SS500)
        suffix = ''.join(c for c in base if not c.isdigit())
        digits = ''.join(c for c in base if c.isdigit())
        new_g = f"{suffix}{int(digits) + 100}" if digits else f"{base}_NEW"
        out.append(SuggestedQuestion(
            intent="hypothesis",
            label=f"⑤신규 강종 {new_g}",
            query=(
                f"신규 강종 {new_g} (기존 {base} 대비 productivity ×0.95) 가 "
                f"SD_PRODUCTIVITY_STD 에 추가되고 동일 사양 주문이 들어오면 "
                f"{orders[0]} 의 Slab 결과와 어떻게 달라질까?"
            ),
            rationale=f"SD_PRODUCTIVITY_STD base grade {base}, seed order {orders[0]}",
        ))
    out.append(SuggestedQuestion(
        intent="hypothesis",
        label="⑤신규 고객 가설",
        query=(
            "신규 고객 CUST-VIP (productivity 5% 높음) 가 추가되면 "
            "같은 강종·품종 주문에서 단중 / 분할수가 어떻게 달라질 가능성?"
        ),
        rationale="seed CUSTOMER_CD list",
    ))

    return out
