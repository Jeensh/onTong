# W77 + W78 · Korean Term Resolver — alias 위의 hybrid tier 검색

> **중요한 관계:** W77 은 ontology 의 `business_terms.aliases_json` 컬럼을
> **대체하지 않습니다**. 그 alias 데이터를 **fully exploit 하는 검색 layer**
> 입니다 (보완 개념).
>
> **What:** ontology 에 이미 등록된 alias + label + description + fqn 4 차원을
> 통합 token index 로 구축. modeling 의 기본 search 가 *한 컬럼만* 보던 부분을
> *모든 컬럼* 으로 확장. 그 위에 **W78 hybrid tier** 로 transliteration / fuzzy /
> LLM assist 까지 단계적으로 적용.
>
> **Why for Section 3:** Section 3 보고서 §2.4 의 "엣징" → 0 hit 의 직접 원인이
> *aliases 가 존재해도 search 가 그것을 못 활용한 것*. W77 은 aliases 의 값을
> 첫 번째 priority source 로 사용. W78 은 그 후속 — alias 가 한쪽 표기만
> 있거나, 사용자가 오타를 내거나, 비표준 음역 ("에징") 으로 입력해도 close.

## 0. W77 ↔ ontology aliases 의 관계

```
┌─────────────────────────────────────────────────────────────────────────┐
│ business_terms (ontology DB) — 원래 있던 데이터                            │
│   fqn      = "term.scm.shared.edging_group_cd"                            │
│   label    = "엣징그룹코드"                                                │
│   aliases  = ["엣징그룹코드", "edgingGroupCd"]   ← 이미 한↔영 양쪽 등록    │
│   description = "..."                                                      │
└─────────────────────────────────────────────────────────────────────────┘
                              │
                              │  W77 이 4 컬럼 모두 token 화해서 index
                              ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ KoreanTermResolver (sim_v2 search layer) — W77 추가 자산                   │
│   token index:                                                             │
│     "엣징"        → {term.scm.shared.edging_group_cd}    ← label 매칭     │
│     "그룹"        → {term.scm.shared.edging_group_cd, ...}                │
│     "edging"      → {term.scm.shared.edging_group_cd, ...} ← alias 매칭   │
│     "group"       → {term.scm.shared.edging_group_cd, ...}                │
│   score 가중치: label_exact + alias_exact + fqn_exact + description_exact │
└─────────────────────────────────────────────────────────────────────────┘
```

**핵심 메시지:**
- ontology 가 한국어 label + 영문 alias 양쪽을 *데이터 source* 로 이미 가지고 있음
- 기존 modeling search 가 그 데이터를 *충분히 활용 못한 것* 이 §2.4 실패의 원인
- W77 은 alias 등을 *완전히 활용* 하는 새 검색 알고리즘 — 보완 layer
- alias 가 잘 등록된 term 일수록 W77 의 매칭 품질도 높음

## 1. Import

```python
from backend.sim_v2.core.search.korean_term_resolver import (
    KoreanTermResolver,         # 메인 resolver
    TermRecord,                 # 입력 데이터 모델
    TermSearchHit,              # 결과 (term + score + matched fields)
    tokenize,                   # 한국어/영문 mixed tokenizer
)
```

## 2. 핵심 매칭 알고리즘 (4 차원 통합 token index)

```
business_terms row → 4 차원으로 tokenize:
    ① label             ("엣징그룹코드")        → ["엣징그룹코드"]
    ② aliases (각각)     ("edgingGroupCd")     → ["edging", "group", "cd"]
    ③ description       (산문)                → tokens
    ④ fqn               ("term.scm.shared...") → tokens

    + 보강:
    • label / alias 의 raw lowercased full string
    • token-level prefix matching (한국어 합성어)
```

## 3. 메인 API

```python
from backend.sim_v2.core.search.korean_term_resolver import KoreanTermResolver

# 1) 빌드 — repo 별 한 번
resolver = KoreanTermResolver.from_session(session, "slab-design-real-v2")
# len(resolver) == 43  (v2 의 business_term 수)

# 2) 검색 (기본: Tier 1 + Tier 2 활성)
hits = resolver.resolve("엣징", top_n=5, min_score=0.5)
# → [
#     TermSearchHit(
#       term=TermRecord(fqn='term.scm.shared.edging_group_cd',
#                       label='엣징그룹코드',
#                       aliases=('엣징그룹코드', 'edgingGroupCd'),
#                       ...),
#       score=6.0,
#       matched_tokens=('엣징',),
#       matched_fields=('aliases', 'label'),
#     ),
#     ...
# ]
```

## 3.5. W78 hybrid tier API — typo + 비표준 음역 close

`resolve()` 의 옵션으로 4 단계 tier 를 켜고 끌 수 있다. 비용이 큰 tier 는
*상위 tier 가 0 hit 일 때만* 호출.

```python
from backend.sim_v2.core.search.korean_term_resolver import (
    KoreanTermResolver,
    LLMAssistCallable,
)

# Section 3 의 chat agent 가 가지고 있는 LLM 을 callback 으로
def section3_llm(query: str) -> list[str]:
    # 실제로는 GPT/Claude 가 "에징" 같은 비표준 음역을 ["edging"] 으로 추론
    return [...]  # tokens / phrases

hits = resolver.resolve(
    "에징",                    # 비표준 음역 (정적 table 에 없음)
    top_n=5,
    use_transliteration=True,  # Tier 2 — static 한↔영 table (기본 ON)
    use_fuzzy=True,            # Tier 3 — difflib 오타 보정 (기본 ON)
    llm_assist=section3_llm,   # Tier 4 — LLM 추론 (기본 None)
)
# → Tier 2/3 fail → Tier 4 가 "에징" → "edging" 추론 → EDGING그룹 매칭
```

### Tier 별 동작 요약

| Tier | 무엇을 하는가 | 언제 발동 | 비용 |
| --- | --- | --- | --- |
| **T1** | token 단계 exact / substring / prefix | 항상 (1 패스) | O(query×terms) |
| **T2** | 한↔영 static table 확장 | `use_transliteration=True` (기본) — 1 패스에 통합 | O(1) per token |
| **T3** | difflib edit-distance fallback | `use_fuzzy=True` 이고 T1+T2 가 **0 hit** | O(query×all_tokens) |
| **T4** | caller-supplied LLM callback | `llm_assist=callable` 이고 T1~T3 이 **0 hit** | LLM 호출 1회 |

### Tier 별 production 실측 (UC42)

| 시나리오 | Query | T1 | T2 | T3 | T4 |
| --- | --- | --- | --- | --- | --- |
| 영문 정확 | `EdgingGroup` | ✓ | ✓ | ✓ | ✓ |
| 한국어 정확 | `엣징그룹코드` | ✓ | ✓ | ✓ | ✓ |
| 한국어→영문 alias | `엣징` (영문-only term 포함) | partial | ✓ | ✓ | ✓ |
| 영문 typo | `edgign` | ✗ | ✗ | ✓ | ✓ |
| 비표준 음역 | `에징` (table 에 없음) | ✗ | ✗ | ✗ | ✓ |

→ **각 tier 가 *상위 단계가 못 풀던 새 케이스* 를 추가로 close**.

### Static transliteration table 확장

새 도메인 단어를 runtime 에 추가하려면:

```python
from backend.sim_v2.core.search.transliteration import register_transliteration

register_transliteration("주조", "casting")
register_transliteration("열연", "hot_rolling")
# 이후 resolver.resolve("주조") → Tier 2 가 "casting" 토큰까지 자동 매칭
```

## 4. UC41 production 실측 (v2)

10 test query → **9 / 10 (90%) 가 ≥1 hit 도달**:

| Query | hit_count | Top result | Score |
| --- | --- | --- | --- |
| `엣징` | 1 | 엣징그룹코드 | 6.0 |
| `단중` | 0 | (v2 DB 에 해당 term 없음 — 데이터 변경됨) | — |
| `실수율` | 1 | 실수율표준 | 3.5 |
| `주문` | 3 | 주문번호 / 주문 / 주문스펙 | 6.0 |
| `에러코드` | 1 | 에러코드 (정확 매칭) | 3.5 |
| `검증결과` | 1 | 검증결과 (정확 매칭) | 3.5 |
| `EDGING` (영문) | 3 | EDGING그룹 / EDGING스펙 / 엣징그룹코드 | 10.0 |
| `edging` (소문자) | 3 | 위와 동일 (case-insensitive) | 10.0 |
| `ValidationResult` | 2 | 검증결과 (한국어 label) | 12.5 |
| `Productivity` | 2 | 실수율표준 | 6.5 |

> **"단중" 0 hit 는 정답**: 현재 v2 DB 에 단중 term 이 존재하지 않음. 보고서 §2.6 시연 시점과 DB 가 달라진 것. resolver 잘못 아님.

## 5. Section 3 통합 시나리오

```python
# bridge_agent.py — chat 분기에서 자연어 → 후보 term FQN
from backend.sim_v2.core.search.korean_term_resolver import KoreanTermResolver

# resolver build (1 회, 또는 cache)
resolver = KoreanTermResolver.from_session(session, "slab-design-real-v2")

def handle_natural_query(user_text: str):
    # 1) 자연어 → keyword 추출 (LLM 또는 split)
    keywords = extract_keywords(user_text)
    # 2) 각 keyword 로 resolver 호출
    candidates: dict[str, float] = {}
    for kw in keywords:
        for hit in resolver.resolve(kw, top_n=3):
            candidates[hit.term.fqn] = max(
                candidates.get(hit.term.fqn, 0),
                hit.score,
            )
    # 3) 상위 후보를 사용자에게 surface
    return ranked_candidates(candidates)
```

## 6. Section 3 의 §2.4 실패 → close

Section 3 보고서 §2.4 시연 ③ "엣징 사양 룩업 룰 보여줘" 의 응답:

> `키워드 ['엣징', '사양', '룩업', '룰']와 매칭되는 업무 용어를 찾지 못했습니다 (conf 0.30)`

W77 resolver 의 같은 입력 결과:

```
'엣징' → 엣징그룹코드 / EDGING그룹 / EDGING스펙
'사양' → EDGING스펙, 슬랩스펙
```

→ Section 3 보고서가 "사용자 정보량 절반" 이라고 했던 평가를 *direct close*.

## 7. 한계 / 주의 — alias 등록 품질이 W77 의 ceiling

W77 은 *alias 데이터 위에서 동작* 하므로, ontology 의 `business_terms.aliases_json`
컬럼 등록 품질이 매칭 정확도의 ceiling.

| 시나리오 | 동작 |
| --- | --- |
| alias 가 한↔영 양쪽 등록 (`["엣징그룹코드", "edgingGroupCd"]`) | W77 이 가장 정확하게 cross-match — UC41 의 모든 hit case 가 이 패턴 |
| alias 가 한쪽만 (`["EdgingGroupEntity"]`, 한국어 alias 없음) | W77 이 label 의 한국어 substring 으로 보강 시도. label 도 영문이면 한국어 query 0 hit |
| alias 가 빈 배열 (`"[]"`) | description / fqn 만으로 검색 — 정확도 가장 낮음 |

**Best practice (Section 3 / Section 2 측 작업):** 새 term 등록 시 한국어 label
+ 영문 alias 둘 다 채우는 것이 W77 + 미래 검색 layer 의 baseline.

기타 한계 (W78 후 갱신):
- ~~한국어 ↔ 영문 표기 변환 table 없음~~ → **W78 Tier 2 static table 로 close** (`backend/sim_v2/core/search/transliteration.py`)
- ~~fuzzy edit-distance 없음~~ → **W78 Tier 3 difflib fallback 로 close**
- ~~비표준 음역 추론 없음~~ → **W78 Tier 4 LLM callback 로 close**
- **다중 keyword AND 조건 없음** — 모든 token 의 hit 점수 합산 (OR-style ranking). 필요 시 W79 candidate

## 8. 관련 파일

| 파일 | 역할 |
| --- | --- |
| `backend/sim_v2/core/search/korean_term_resolver.py` | 메인 resolver + 4 tier 통합 (~340 lines) |
| `backend/sim_v2/core/search/transliteration.py` | W78 Tier 2 한↔영 static table |
| `backend/sim_v2/tests/core/search/test_w77_korean_term_resolver.py` | 27 unit test (W77 baseline) |
| `backend/sim_v2/tests/core/search/test_w78_hybrid_tiers.py` | 14 unit test (W78 tier 별) |
| `backend/sim_v2/demos/uc41_korean_term_search/run.py` | W77 production demo (10 query, 9 hit) |
| `backend/sim_v2/demos/uc42_hybrid_korean_search/run.py` | W78 production demo (tier 별 close rate) |
