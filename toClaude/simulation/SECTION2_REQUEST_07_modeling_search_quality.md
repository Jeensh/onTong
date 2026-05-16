# Section 2 (Modeling) 측 요청 — ⑦ `term/search` 의 hit rate / alias 매칭 강화

> **요청자**: Section 3 (Simulation) 팀
> **수신**: Section 2 (Modeling) 개발자
> **우선순위**: 🟢 **선택** (legacy `/api/ontology/search` 로 우회 중)
> **발견 일자**: 2026-05-12 (Ontology API 전수 호출 감사)
> **예상 작업 비용**: S — Cypher CONTAINS / `aliases` 배열 매칭 추가

---

## 한 줄 요약

> **`/api/modeling/ontology/term/search?q=...` 는 한국어/영문/약어/aliases 매칭이 약해 0 hit
> 가 너무 잦다. legacy `/api/ontology/search` 와 동등한 풍부도로 끌어올려 달라.**

---

## 실측

```bash
$ curl '/api/modeling/ontology/term/search?q=실수율'
[]                    # 빈 응답

$ curl '/api/modeling/ontology/term/search?q=edging'
[]                    # 빈 응답

# 반면 legacy 는 풍부
$ curl '/api/ontology/search?q=실수율&limit=10'
[ {..term..}, {..action..}, {..code_method..} ]   # 다종 hit

# explain 의 키워드 매칭은 한국어 잘 됨 (graph 에 19 Term 만 있음에도)
$ curl -X POST /api/modeling/ontology/query -d '{"intent":"explain","natural_language":"실수율이 뭐야"}'
# → matched_terms: [ { korean:"실수율", english:"YieldRate", category:"concept" } ]  ✅
```

→ explain 안에는 정확 매칭 + 부분 매칭이 다 있는데, 같은 ontology DB 의 `term/search` GET 은 빈 응답.

---

## 요청

### 7.1 `term/search` 의 매칭 정책 정렬

explain 의 keyword matching 과 같은 단계 + 가중치 적용:

1. **exact match** on `korean`, `english`, `aliases[]`, `fqn`
2. **prefix match** on 위 4 필드
3. **CONTAINS** on `description`, `korean`
4. **trigram / fuzzy** (선택) — `productivity` → `prod...`

Cypher 예:

```cypher
MATCH (t:Term)
WHERE
  t.korean = $q OR t.english = $q
  OR any(a IN t.aliases WHERE a = $q)
  OR t.korean CONTAINS $q OR t.english CONTAINS $q
  OR any(a IN t.aliases WHERE a CONTAINS $q)
  OR t.description CONTAINS $q
RETURN t
ORDER BY
  CASE
    WHEN t.korean = $q OR t.english = $q THEN 1
    WHEN any(a IN t.aliases WHERE a = $q) THEN 2
    WHEN t.korean STARTS WITH $q OR t.english STARTS WITH $q THEN 3
    ELSE 4
  END
LIMIT $limit
```

### 7.2 다국어 cross-match

`q="실수율"` → english `YieldRate` 도 hit / `q="yield"` → korean `실수율` 도 hit.

### 7.3 응답 shape 보강 (선택)

```jsonc
{
  "items": [
    {
      "id": "term_yield_rate",
      "fqn": "term.scm.product.productivity_std",
      "korean": "실수율",
      "english": "YieldRate",
      "aliases": ["productivity", "수율"],
      "category": "concept",
      "description": "주문량 대비 실제 생산 가능 비율",
      "match_field": "korean",   // ★ 어디서 hit 했는지
      "match_kind":  "exact",    // exact | prefix | contains | alias
      "score": 1.0
    }
  ]
}
```

---

## Acceptance Criteria

- [ ] `?q=실수율` → 19 Term 중 매칭되는 것 반환 (현재 0)
- [ ] `?q=YieldRate` → 같은 term 반환 (한↔영)
- [ ] `?q=edging` → aliases / category 에 'edging' 있는 term 들
- [ ] empty `q` → `400` 또는 `{items:[]}` (현재는 422 — OK)
- [ ] response time < 100 ms (Term 19 개라 자명)

---

## Section 3 에서의 활용처

| Section 3 자산                                       | 변경 후 동작                                                                              |
| ---------------------------------------------------- | ----------------------------------------------------------------------------------------- |
| `BridgeChatPanel` 자동완성 (term-search)             | 사용자가 "실수" 입력 시 즉시 후보 제안. 현재 빈 응답.                                       |
| `CodeImpactPanel` / `DataImpactPanel` 의 id 추천      | id 입력란 옆 자동완성 ← term/search 결과로 채움.                                            |
| `DashboardPanel` 의 quick search box                  | 정확한 hit/miss 비율 표시 (search index 건강도)                                            |

---

## 우회 (현재 Section 3)

- `ModelingClient.search()` 가 legacy `/api/ontology/search` 를 fallback 호출. legacy 는 다종 (term/action/code) 가 섞여 나오기 때문에 term 만 필터링하는 후처리 필요.

---

## 메타

- **요청 ID**: SECTION2-REQ-07
- **요청 일자**: 2026-05-12
- **선행 작업**: 없음
- **연관 요청**: ③ explain alias / partial match (`SECTION2_REQUESTS.md` ③) 와 통합 가능
