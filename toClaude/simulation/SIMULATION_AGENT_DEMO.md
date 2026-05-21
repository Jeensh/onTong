# 시뮬레이션 에이전트 — 데모 가이드

> Section 3 신규 탭 **시뮬레이션 에이전트** 의 5 시나리오 데모.
> 브랜치: `jyu-simul` · URL: `http://localhost:3000/?section=simulation&view=simulation`

---

## 사전 준비

1. ontology.db 가 채워져 있는지 확인:
   ```bash
   sqlite3 data/ontology.db "SELECT COUNT(*) FROM actions WHERE repo_id='slab-design-real-v2'"
   # → 136 이어야 정상
   ```
2. backend (8001) + frontend (3000) 기동 — 본 가이드 작성 시점에서 둘 다 동작 중.
3. `.env` 에 `OPENAI_API_KEY` 설정. 없으면 intent 분류가 `ambiguous` 만 반환.

---

## 5 시나리오 데모

### ① 기능 개선 영향 (impact)

질문 예: **"단중 계산 로직 바꾸면 어디 영향?"**

흐름:
1. 좌측 chat 에 질문 입력 → Enter
2. 중앙 패널에 **대상 후보 선택 카드** — intent 배지 `영향도 분석`, 후보 carousel
3. 가장 위 (추천) 후보 클릭 → Gate III impact 직진 → **executed 카드**
4. 화면 = 영향받는 method 표 + sim_v2 findings (collapsible)

확인 포인트:
- intent 배지가 `영향도 분석`
- 우측 그래프에 target node + 인접 actions
- 좌측 chat 에 turn 1·2 summary

---

### ② 기준 데이터 변경 영향 (impact)

질문 예: **"design 정책 standard 0.5 → 0.3 으로 바꾸면?"**

흐름: ① 과 동일하지만 후보가 다르고 affected_methods 가 다른 set.

---

### ③ 주문 데이터 변경 비교 (simulate + compare)

질문 예: **"이 주문의 thickness 만 바꿔 돌려봐"** 또는 **"thickness 액션 시뮬"**

흐름:
1. 질문 입력 → 후보 카드 (intent 배지 `시뮬레이션`)
2. 후보 선택 → **Bundle 합성 카드 (2/3)**:
   - Java 원본 (좌)
   - Python 변환 (우, 강조)
   - idiom diffs (collapsible)
   - Order fixture 표
   - 변경 후 fixture override JSON 입력란 (amber)
3-A. "이 bundle 로 실행" → 단일 sim 실행 → results / invariant_status / baseline_diff
3-B. override JSON 입력 (예: `{"order": {"thickness": 0.3}}`) → "변경 전·후 비교" → **3-column DIFF 카드**
   - 좌: 변경 전 result
   - 중: 변경 후 result
   - 우: 변경된 필드만 highlight

확인 포인트:
- override 미입력 시 "변경 전·후 비교" 버튼 숨김
- override JSON 파싱 실패 시 alert
- DIFF 카드의 변경 필드 색상 (전 → 후, 빨강 line-through → 초록)

---

### ④ 자연어 → 코드 위치 찾기 (locate)

질문 예: **"edging 룰은 어디 박혀있어?"**

흐름:
1. 후보 카드 (intent 배지 `위치 찾기`)
2. 후보 선택 → Gate III lookup(mode=locate) → **executed_lookup 카드**
3. 화면:
   - 자연어 summary (있으면)
   - target method body
   - callers 리스트 (collapsible)
   - business rules 리스트

---

### ⑤ 설명 (explain)

질문 예: **"Slab 단중이 뭐야?"**

흐름: ④ 와 동일한 lookup, 단 mode=explain. UI 상 차이는 거의 없으나 summary 가 더 풍부.

---

### ⑥ 신규 품종 추가 영향 (hypothesis)

질문 예: **"신규 품종 HC600X 추가되면 어떤 영향?"**

흐름:
- LLM 이 hypothesis intent 로 분류하면 → bundle_prepared → confirm_bundle → Gate III hypothesis (verdict + reasoning)
- impact 로 잘못 분류하면 → impact 흐름 (영향받는 method 표). 사용자가 chat 의 "다른 후보 / 새 질문" 으로 다시 시도 가능.

verdict 색상:
- `passes` → 초록
- `fails`  → 빨강
- 그 외   → 호박색

---

## 추가 버튼

| 위치 | 버튼 | 의미 |
|---|---|---|
| 후보 카드 | **다른 후보** | Gate I 재실행 (같은 query) |
| 후보 카드 | **중단** | session abort |
| ambiguous 카드 | **이 의도로 재검색** | 사용자가 명시한 intent 로 강제 재검색 |
| Bundle 카드 | **이 bundle 로 실행** | Gate III sim/hypothesis |
| Bundle 카드 | **변경 전·후 비교** | compare_with_overrides |
| Executed (simulate) | **재실행** | rerun (같은 bundle) |
| Executed 전체 | **새 질문** | session 초기화 |

---

## 자동 e2e 테스트

```bash
PYTHONPATH=. venv/bin/pytest tests/simulation/test_simulation_agent.py -v
```

테스트 cover:
- `/start` intent + candidates 반환
- `/replay` decisions hydrate
- 시나리오 ① impact → executed
- 시나리오 ③ simulate → bundle → executed
- 시나리오 ④ locate → executed
- `/abort` 처리
- `compare_with_overrides` 의 sentinel (no bundle → 409)
- unknown session → 404

8/8 PASS · 약 3초.

---

## API endpoint

| Method | URL | 설명 |
|---|---|---|
| POST | `/api/section3/simulation/start` | session 생성 + Gate I |
| POST | `/api/section3/simulation/respond/{sid}` | 사용자 결정 처리 |
| GET  | `/api/section3/simulation/replay/{sid}` | transcript hydrate |

RespondRequest.action ∈
`select_candidate | request_other | clarify_intent | confirm_bundle | rerun | compare_with_overrides | abort`

---

## 트러블슈팅

- **intent 가 항상 `ambiguous`**: `.env` 에 `OPENAI_API_KEY` 누락. multiturn 의 `OpenAIIntentClassifier` 가 API 키 없을 때 ambiguous fallback.
- **candidates 0건**: query 의 키워드가 ontology 와 매칭 안 됨. 한·영 양방향 expansion 이 도와주지만 한계 있음. 사용자에게 "다른 후보 / 다른 질문" 안내.
- **bundle confidence 0**: Java→Python transpile 또는 schema fetch 실패. error 메시지 확인.
- **compare_with_overrides 가 field_diffs 0건**: bundle 의 결과 dict 가 비어 있음. translate 후 실행이 stub 으로 떨어진 케이스. 다른 action 으로 시도.
