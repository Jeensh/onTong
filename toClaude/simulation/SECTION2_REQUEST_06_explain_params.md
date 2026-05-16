# Section 2 (Modeling) 측 요청 — ⑥ `explain` intent 의 `parameters.keywords` 배열 형식 수용

> **요청자**: Section 3 (Simulation) 팀
> **수신**: Section 2 (Modeling) 개발자
> **우선순위**: 🟡 **개선** (현재 Section 3 측에서 우회 가능 — 작은 작업)
> **발견 일자**: 2026-05-12 (Ontology API 전수 호출 감사)
> **예상 작업 비용**: S — handler 입력 normalize 1 줄

---

## 한 줄 요약

> **`explain` intent 는 현재 `natural_language` 또는 `parameters.query|keyword` 만 인식한다.
> Section 3 의 LLM 분류기는 자연스럽게 `parameters.keywords: string[]` 형태를 만든다.
> 두 형식 모두 수용하여 사용자/LLM 의 표현에 견고하게 대응해 달라.**

---

## 실측

| 호출 payload                                                          | 응답              | 비고                                                            |
| --------------------------------------------------------------------- | ----------------- | --------------------------------------------------------------- |
| `{ intent:"explain", natural_language:"실수율이 뭐야" }`               | ✅ 정상 (term + step 2 + table 2) | 잘 동작                                                      |
| `{ intent:"explain", parameters:{ query:"실수율" } }`                  | ✅ 정상            | 잘 동작                                                          |
| `{ intent:"explain", parameters:{ keyword:"실수율" } }`                | ✅ 정상            | 잘 동작                                                          |
| `{ intent:"explain", parameters:{ keywords:["실수율","productivity"] } }` | ❌ "검색할 키워드가 필요합니다" | **Section 3 LLM 의 기본 출력 형식**                              |
| `{ intent:"explain", parameters:{ q:"실수율" } }`                      | ❌ "검색할 키워드가 필요합니다" | (선택) "q" 도 받으면 더 견고                                      |

### 사용자 막힘 흐름

1. 사용자 → "실수율 어디서 쓰여?"
2. Section 3 의 OpenAI 분류기 → `{ intent:"explain", parameters:{ keywords:["실수율"] } }`
3. modeling 응답 → `need_more_info` "검색할 키워드가 필요합니다"
4. 사용자 → "방금 적었잖아?"

---

## 요청 — handler 입력 normalize

```python
def normalize_explain_input(req: OntologyRequest) -> str | None:
    p = req.parameters or {}
    # 우선순위 :
    # 1) parameters.keywords 가 list[str] 이면 " ".join 또는 첫 항목
    if isinstance(p.get("keywords"), list) and p["keywords"]:
        return " ".join(str(k) for k in p["keywords"] if isinstance(k, str))
    # 2) parameters.query / keyword / q
    for key in ("query", "keyword", "q", "text"):
        v = p.get(key)
        if isinstance(v, str) and v.strip():
            return v
    # 3) natural_language fallback
    if req.natural_language and req.natural_language.strip():
        return req.natural_language
    return None
```

이 함수의 반환을 기존 keyword 매칭 로직에 그대로 넣으면 됨.

---

## Acceptance Criteria

- [ ] `{ parameters:{ keywords:["실수율","productivity"] } }` 호출 시 정상 응답
- [ ] `{ parameters:{ keywords:[] } }` 호출 시 기존처럼 `need_more_info`
- [ ] `{ natural_language:"...", parameters:{ keywords:["..."] } }` 둘 다 있으면 keywords 우선
- [ ] 응답 shape 변동 없음 (matched_terms / process_locations / data_locations / source_locations / related_terms / ontology_trace)

---

## Section 3 에서의 활용처

| Section 3 자산                                  | 변경 후 동작                                                                                  |
| ----------------------------------------------- | --------------------------------------------------------------------------------------------- |
| `intent_classifier.py` LLM SYSTEM_PROMPT       | "explain 시 parameters: {} 만" 제약을 풀고 keywords 추출 결과를 자연스럽게 전달                  |
| `BridgeChatPanel.tsx` 의 자연어 chat            | 현재 `parameters.keywords` 가 가도 modeling 이 거절 → 검색 결과 없음 표시. 수정 후 즉시 풍부한 응답. |
| `bridge_agent.explain()` 헬퍼                   | 현재 `natural_language=user_message` 만 보내고 keywords 는 무시. 변경 후 둘 다 보내도 안전.       |

---

## 우회 (Section 3 측에서 이미 처리 가능)

- 옵션 1: Section 3 가 explain 호출 직전 keywords → query (단수) 로 join.
- 옵션 2: Section 3 가 `natural_language` 만 보내고 parameters 는 비움.

→ 이미 Section 3 코드 수정으로 즉시 해결 가능. 다만 **modeling 측이 두 형식을 다 받으면 향후 다른
  client (e.g. ext API, 다른 팀) 가 같은 함정에 빠지지 않음**.

---

## 메타

- **요청 ID**: SECTION2-REQ-06
- **요청 일자**: 2026-05-12
- **선행 작업**: 없음
- **연관 요청**: 없음 (independent)
