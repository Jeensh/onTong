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
            # in-memory matching (rows ~80개 — 빠름) — 양방향 substring 매칭
            # token (사용자 입력) ⟷ label / alias / fqn 세 source 모두 비교.
            for tok in tokens:
                tok_l = tok.lower()
                best_match: tuple[Any, str, list[str], float] | None = None  # (row, why, aliases, score)
                for r in rows:
                    if r.fqn in seen_fqns:
                        continue
                    label = (r.label or "")
                    label_l = label.lower()
                    aliases: list[str] = []
                    try:
                        aliases = json.loads(r.aliases_json or "[]")
                    except Exception:
                        pass

                    score = 0.0
                    why = ""
                    # 정확 일치 (가장 강함)
                    if tok == label or tok_l == label_l:
                        score = 10.0; why = f"label exact: {label}"
                    elif any(tok == a or tok_l == a.lower() for a in aliases):
                        score = 9.5; why = f"alias exact: {tok}"
                    # token 이 label/alias 안에 포함 (예: "공장" → "확정통과공장코드")
                    elif tok in label or tok_l in label_l:
                        score = 7.0; why = f"label contains: {label}"
                    elif any(tok in a or tok_l in a.lower() for a in aliases):
                        score = 6.5; why = f"alias contains: {tok}"
                    # label/alias 가 token 안에 포함 (예: token="confirmedPlantCd" → alias "confirmedPlantCd")
                    elif len(label) >= 3 and (label in tok or label_l in tok_l):
                        score = 8.0; why = f"label substring of token"
                    elif any(len(a) >= 3 and (a in tok or a.lower() in tok_l) for a in aliases):
                        score = 7.5; why = f"alias substring of token"
                    # fqn 비교 (영문 ALL_CAPS 토큰이 fqn 의 일부와 매칭 — 예: CAST_SPEC ↔ term.scm.spec.cast_spec)
                    elif tok_l.replace("_", "") in (r.fqn or "").lower().replace("_", ""):
                        score = 6.0; why = f"fqn matches"
                    if score > 0 and (best_match is None or score > best_match[3]):
                        best_match = (r, why, aliases, score)
                if best_match is not None:
                    r, why, aliases, score = best_match
                    seen_fqns.add(r.fqn)
                    desc = (r.description or "").split("\n")[0]
                    if len(desc) > 200:
                        desc = desc[:200] + "..."
                    out.append(DetectedTerm(
                        token=tok, term_fqn=r.fqn, label=r.label,
                        definition=desc, aliases=aliases[:8],
                    ))
    except Exception as e:  # noqa: BLE001
        logger.warning("term lookup 실패: %s", e)
    return out


# 한국어 조사 — 명사 뒤에 자주 붙어 토큰화를 방해한다 (긴 것 먼저).
# longest-match 로 잘라내야 "포장단중을" → "포장단중", "포장단중에서" → "포장단중".
_KO_PARTICLES: tuple[str, ...] = (
    "에서는", "에서도", "으로는", "으로도", "에서", "으로",
    "에게", "까지", "부터", "보다", "처럼", "마다", "조차",
    "에는", "에도", "에",
    "와의", "과의", "와는", "과는", "와도", "과도", "와", "과",
    "이라고", "라고", "라는", "이라는",
    "을", "를", "이", "가", "은", "는", "의", "도", "만", "도", "께", "한",
)

# 도메인 합성어 사전 — ontology alias 외에 사용자가 자주 쓰는 표현을 보강.
# 이 사전 + DB alias 를 합쳐 longest-match 로 텍스트를 분절한다.
_DOMAIN_LEXICON_EXTRA: tuple[str, ...] = (
    # 단중 계열
    "포장단중", "포장단중상한", "포장단중하한", "포장단중상하한",
    "주문단중", "고객단중", "슬랩단중", "슬래브단중", "slab단중", "Slab단중", "압연단중",
    "최소단중", "최대단중", "초기단중", "기준단중",
    "1차무게", "2차무게", "1차단중", "2차단중",
    # 폭/길이/두께 계열
    "슬랩두께", "슬래브두께", "slab두께", "Slab두께", "목표폭", "열연목표폭", "주문폭",
    "최대폭", "최소폭", "폭하한", "폭상한", "길이하한", "길이상한",
    "두께값", "폭값", "길이값",
    # Slab 표기 변형
    "슬랩", "슬래브", "slab", "Slab",
    "슬랩 분할수", "슬래브 분할수", "Slab 분할수",
    "슬랩 매수", "슬래브 매수", "Slab 매수",
    "슬랩 단중", "슬래브 단중", "Slab 단중",
    "슬랩 두께", "슬래브 두께", "Slab 두께",
    "슬랩 폭", "슬래브 폭", "Slab 폭",
    "슬랩 길이", "슬래브 길이", "Slab 길이",
    # 설계 / 대기량 / 수율
    "설계대기량", "설계대기", "배치대기", "공정수율", "누적수율",
    "누적실수율", "공정실수율",
    # 분할
    "최대분할수", "분할수", "분할갯수", "슬랩매수", "slab매수",
    # 엣징
    "엣징그룹", "엣징보정", "엣징cap", "엣징상한", "엣징하한",
    # 코드 류
    "확정통과공장코드", "확정통과공장", "열연공장코드", "열연공장",
    "고객사코드", "강종코드", "품종코드", "공정코드", "제강코드", "연주코드",
    # 기타 자주 등장
    "기준데이터", "기준값", "주문데이터", "변경전후", "상하한",
)


def _load_korean_lexicon() -> list[str]:
    """ontology DB 의 한국어 label/alias + 도메인 합성어 사전을 합쳐 길이 내림차순 list 반환.

    longest-match 토크나이저 용. process-level 한 번만 로드.
    """
    cached = getattr(_load_korean_lexicon, "_cache", None)
    if cached is not None:
        return cached
    import re, json
    words: set[str] = set(_DOMAIN_LEXICON_EXTRA)
    try:
        from sqlalchemy import select
        from backend.modeling.domain_layer.orm import BusinessTermRow
        with session_scope() as s:
            rows = s.execute(select(BusinessTermRow)).scalars().all()
            for r in rows:
                for w in [r.label] + json.loads(r.aliases_json or "[]"):
                    if not w:
                        continue
                    w = w.strip()
                    # 한글 2자+ 또는 한글+영문/숫자 혼합 (예: "slab단중") 만 사전화.
                    # 순수 영문은 별도 regex 가 잡으므로 제외.
                    if len(w) >= 2 and re.search(r"[가-힣]", w):
                        words.add(w)
    except Exception as e:
        logger.warning("ontology 사전 로드 실패 (사전 fallback): %s", e)
    sorted_words = sorted(words, key=lambda x: (-len(x), x))
    _load_korean_lexicon._cache = sorted_words  # type: ignore[attr-defined]
    return sorted_words


def _strip_particle(chunk: str) -> str:
    """한국어 chunk 끝의 조사를 longest-match 로 제거."""
    for p in _KO_PARTICLES:
        if chunk.endswith(p) and len(chunk) > len(p):
            return chunk[: -len(p)]
    return chunk


def _lexicon_longest_match(chunk: str, lex: list[str]) -> list[str]:
    """chunk 안에서 사전 단어를 longest-match 로 추출 (포지션을 jump).

    예) "포장단중상한과" → 조사 "과" 제거 → "포장단중상한"
        → 사전 longest-match → ["포장단중상한"] (또는 사전에 따라 ["포장단중", "상한"]).
    """
    if not chunk:
        return []
    found: list[str] = []
    i = 0
    n = len(chunk)
    while i < n:
        matched = False
        # 가장 긴 단어부터 — sorted 사전이지만 슬라이딩 비교는 길이별로
        # 효율 위해 chunk 의 i.. 위치에서 가능한 최대 길이부터 줄여가며 사전 검사.
        for L in range(min(20, n - i), 1, -1):  # 최대 20글자, 최소 2글자
            cand = chunk[i:i + L]
            if cand in lex:
                found.append(cand)
                i += L
                matched = True
                break
        if not matched:
            i += 1
    return found


def extract_korean_tokens(text: str, min_len: int = 2) -> list[str]:
    """자연어에서 한국어/영문 토큰 추출 (camelCase · snake_case · ALL_CAPS 포함).

    토큰화 전략 (2026-05-25 고도화):
      1. 한국어 chunk ("[가-힣]+") 추출
      2. 각 chunk 의 끝 조사 (을·를·이·가·은·는·의·도·에·에서·으로·과·와 등) 제거
      3. 조사 제거된 chunk 자체 (전체) + ontology 사전 + 도메인 합성어 사전으로
         longest-match 분절 → 사전 단어들을 보존
      4. 4글자+ 이상이면 sliding window (2·3·4글자) 도 추가하여 부분 매칭 fallback 유지
      5. 영문 식별자 (camelCase · snake_case · ALL_CAPS) 보존

    예) "설계대기량과 포장단중 상하한 변경" →
        ["설계대기량", "포장단중", "상하한", "변경",
         (sliding) "설계", "계대", "대기", "기량", "포장", "장단", "단중", ...]
    """
    import re
    out: list[str] = []
    seen: set[str] = set()
    lex = _load_korean_lexicon()

    def _push(t: str) -> None:
        if t and len(t) >= min_len and t not in seen and len(t) <= 40:
            seen.add(t); out.append(t)

    # 1) 한국어 chunk
    for raw in re.findall(r"[가-힣A-Za-z0-9]+", text):
        if not re.search(r"[가-힣]", raw):
            continue  # 순수 영문/숫자는 2) 에서 처리
        # 1-a) 조사 제거
        stem = _strip_particle(raw)
        # 1-b) 사전 longest-match (조사 제거된 stem 으로)
        for m in _lexicon_longest_match(stem, lex):
            _push(m)
        # 1-c) 전체 chunk (원본 + 조사 제거 stem) 도 후보로
        _push(raw)
        _push(stem)
        # 1-d) 4글자+ sliding window — 사전 미커버 합성어 fallback
        if len(stem) >= 4:
            for L in (2, 3):
                for i in range(len(stem) - L + 1):
                    _push(stem[i:i + L])

    # 2) 영문 식별자
    for t in re.findall(r"[A-Za-z][A-Za-z0-9_]+", text):
        if len(t) >= min_len and len(t) <= 40:
            _push(t)
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

    # ──────────────────────────────────────────────────────────────────
    # 2026-05-25 사용자 요구: 모든 예시 질문에서 실제 ORDER 데이터 의존 제거
    #   ORDER 4 테이블이 비워졌으므로 (02_orders.sql), 모든 질문은
    #   "가상 주문을 합성해서" 라는 형태로 표현.
    #   각 의도가 21-step walkthrough 카드로 결과 노출되도록 키워드 정렬.
    # ──────────────────────────────────────────────────────────────────

    # ───────────────── simulate (가상 주문 → Slab 설계) ─────────────────
    out.append(SuggestedQuestion(
        intent="simulate",
        label="①COIL 가상 주문 시뮬",
        query="품종 COIL 가상 주문 1건을 합성해서 21단계 slab 설계 결과를 보여줘",
        rationale="가상 주문 합성 + 21-step 전 흐름",
    ))
    out.append(SuggestedQuestion(
        intent="simulate",
        label="①FS 강종별 시뮬",
        query="강종 SS400 + 품종 FS 가상 주문으로 slab 두께·폭·길이가 어떻게 결정되는지 보여줘",
        rationale="시뮬 흐름 — 두께·폭·길이 결정 step 1·2·3",
    ))

    # ───────────────── impact (기준/로직 변경 영향) ─────────────────
    out.append(SuggestedQuestion(
        intent="impact",
        label="②연주설비 slab두께",
        query="연주설비사양기준에서 slab두께를 변경하면 어떻게 돼?",
        rationale="CAST_SPEC slabThickness 영향도",
    ))
    out.append(SuggestedQuestion(
        intent="impact",
        label="②Edging 능력 상하한",
        query="Edging 기준의 능력 상한, 하한을 변경했을때 어떤 영향이 발생해?",
        rationale="EDGING_GROUP 변경 시 binding 설비 식별",
    ))
    out.append(SuggestedQuestion(
        intent="impact",
        label="②포장단중·설계대기량 최적",
        query="설계대기량과 주문의 포장단중 상하한을 변경했을때, slab설계 결과 단중에 어떤 영향을 줘?",
        rationale="DESIGN_PEND_QTY + ORDER_WGT_LOW/HIGH sweep",
    ))
    out.append(SuggestedQuestion(
        intent="impact",
        label="②HR 단중 한계 변경",
        query="HR_MAX_WGT 압연 최대 단중을 5% 올리면 slab 결과가 어떻게 달라져?",
        rationale="HR_MAX_WGT 변경 → step 6 영향",
    ))

    # ───────────────── locate (코드 위치 찾기) ─────────────────
    out.append(SuggestedQuestion(
        intent="locate",
        label="③단중 계산 위치",
        query="slab 단중 계산하는 로직은 어디에 있어?",
        rationale="slabWgt 계산 — step 4·5·6 매핑",
    ))
    out.append(SuggestedQuestion(
        intent="locate",
        label="③분할수 결정 위치",
        query="slab 분할수를 결정하는 로직은 어느 단계에서 일어나?",
        rationale="step 7 (최대분할) + step 8 (A-a 루프)",
    ))
    out.append(SuggestedQuestion(
        intent="locate",
        label="③목표 폭 결정 위치",
        query="slab 목표 폭을 10mm 단위로 정하는 곳은 어디?",
        rationale="step 18 SdTargetWidthAction",
    ))

    # ───────────────── explain (자연어 설명) ─────────────────
    out.append(SuggestedQuestion(
        intent="explain",
        label="④단중 영향 변수 (최대화)",
        query="slab 설계 단중에 영향을 주는 변수가 어떤 것들이 있어?",
        rationale="단중 최대화 — 입력 변수 catalog + 제약",
    ))
    out.append(SuggestedQuestion(
        intent="explain",
        label="④확정통과공장코드?",
        query="확정통과공장코드가 뭐야?",
        rationale="ontology atomic term 직접 답변",
    ))
    out.append(SuggestedQuestion(
        intent="explain",
        label="④slab 단중 관련 항목",
        query="slab 단중과 관련된 항목은 어떤게 있어?",
        rationale="관련 term/action 네트워크",
    ))
    out.append(SuggestedQuestion(
        intent="explain",
        label="④A-a 루프 설명",
        query="slab 설계의 A-a 루프가 뭐고 분할수×매수를 어떻게 결정해?",
        rationale="step 8~15 phase2b 흐름 설명",
    ))
    out.append(SuggestedQuestion(
        intent="explain",
        label="④누적 실수율 의미",
        query="누적 실수율(productivity) 이 Slab 설계에 어떤 식으로 쓰여?",
        rationale="phase1 ProductivityService — 환산 핵심",
    ))

    # ───────────────── hypothesis (신규 X 추가 — 가상) ─────────────────
    out.append(SuggestedQuestion(
        intent="hypothesis",
        label="⑤신규 고객사 기준",
        query="신규 고객사 기준을 추가하고, 그 고객사의 가상 주문이 들어오면 어떻게 처리돼?",
        rationale="CUSTOMER_STD 추가 + 가상 주문",
    ))
    out.append(SuggestedQuestion(
        intent="hypothesis",
        label="⑤신규 품종 추가",
        query="신규 품종 PLATE 후판을 추가하고 가상 주문 1건 합성해서 slab 결과를 보면?",
        rationale="신규 PRODUCT_CD → 21-step 전 흐름",
    ))
    # 가설/sweep 류 — 신규 강종 추가 시나리오 대신 조건 sweep 으로 일반화
    out.append(SuggestedQuestion(
        intent="hypothesis",
        label="⑤설계대기량 sweep",
        query="주문의 설계대기량 상한 값을 10kg씩 10번 증가시킬 때마다 Slab 설계 단중값이 어떻게 변해?",
        rationale="조건 변화 → 결과 변화 sweep — generic dynamic explain",
    ))

    return out
