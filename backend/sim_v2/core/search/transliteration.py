"""W78 — Korean ↔ English transliteration table.

Section 3 보고서 §2.4 의 시연 ③ ("엣징 사양 룩업 룰") 은 *같은 term 안에 한↔영
alias 가 양쪽 다 있을 때만* W77 으로 close. 한쪽만 있는 term (예: label 이
"EDGING그룹" 영문 표기인데 한국어 query "엣징") 은 cross-match 불가능.

이 모듈은 자주 쓰이는 한↔영 음역 매핑을 정적 table 로 제공.
`expand_transliteration("엣징")` → `{"엣징", "edging"}` 같이 token 을 확장하여
매칭 시도. 표가 작더라도 production 의 빈번한 keyword 를 우선 cover하면 됨.

새 매핑이 필요하면 `_KR_TO_EN` 에 단순히 추가. (Static — LLM 호출 없이도
대부분 cover 가능.)

Public API:
    - expand_transliteration(token) → set[str]   # 자기 자신 + 음역
    - register_transliteration(kr, en)            # 런타임 등록 (caller 가 추가)
"""
from __future__ import annotations


# 한국어 → 영문 후보 (1:N 가능)
_KR_TO_EN: dict[str, tuple[str, ...]] = {
    # SCM 도메인 자주 쓰이는 단어
    "엣징":     ("edging",),
    "에러":     ("error",),
    "코드":     ("code",),
    "검증":     ("validation", "verify"),
    "결과":     ("result",),
    "주문":     ("order",),
    "단중":     ("weight", "unit"),
    "실수율":   ("productivity",),
    "표준":     ("std", "standard"),
    "엔터티":   ("entity",),
    "엔티티":   ("entity",),
    "고객":     ("customer",),
    "사양":     ("spec", "specification"),
    "그룹":     ("group",),
    "스펙":     ("spec",),
    "번호":     ("no", "number"),
    "스펙":     ("spec",),
    "분석":     ("analysis",),
    "이력":     ("history",),
    "공정":     ("process",),
    "단계":     ("step",),
    "범위":     ("range",),
    "길이":     ("length",),
    "폭":       ("width",),
    "두께":     ("thickness",),
    "최대":     ("max", "maximum"),
    "최소":     ("min", "minimum"),
    "중량":     ("weight",),
    "밀도":     ("density",),
    "온도":     ("temperature",),
    "압력":     ("pressure",),
    "공장":     ("plant",),
    "라인":     ("line",),
    "설계":     ("design",),
    "슬랩":     ("slab",),
    "강종":     ("grade",),
    "제품":     ("product",),
    "구분":     ("kind", "type"),
    "회사":     ("company",),
    # 일반 단어
    "이름":     ("name",),
    "값":       ("value",),
    "목록":     ("list",),
    "지도":     ("map",),
    "집합":     ("set",),
    "키":       ("key",),
    "타입":     ("type",),
    "필드":     ("field",),
    "메서드":   ("method",),
    "메소드":   ("method",),
    "함수":     ("function", "func"),
}


# 자동 역매핑 (영문 → 한국어 후보)
_EN_TO_KR: dict[str, list[str]] = {}
for _kr, _en_tuple in _KR_TO_EN.items():
    for _en in _en_tuple:
        _EN_TO_KR.setdefault(_en, []).append(_kr)


def expand_transliteration(token: str) -> set[str]:
    """Return {token} plus any known transliterations (한↔영 양방향)."""
    if not token:
        return set()
    out: set[str] = {token}
    lower = token.lower()
    # 한→영
    if token in _KR_TO_EN:
        out.update(_KR_TO_EN[token])
    # 영→한 (lower-cased)
    if lower in _EN_TO_KR:
        out.update(_EN_TO_KR[lower])
    return out


def register_transliteration(kr: str, en: str) -> None:
    """Runtime 매핑 추가 (caller 가 도메인별 단어 보강 가능).

    예:
        register_transliteration("주조", "casting")
    """
    if not kr or not en:
        return
    existing = _KR_TO_EN.get(kr, ())
    if en not in existing:
        _KR_TO_EN[kr] = existing + (en,)
    _EN_TO_KR.setdefault(en.lower(), []).append(kr)


__all__ = [
    "expand_transliteration",
    "register_transliteration",
]
