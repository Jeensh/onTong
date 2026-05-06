# onTong Authoring AI — Design Document

> 작성일: 2026-05-04 · Round 5 의 Step 1~15 결정을 통합한 1차 design spec.
> 검토 대상: 사용자(팀 리더) → 합의 후 prototype 단계로.

---

## 1. Vision

### 1.1 문제 정의 (Expression Gap)

도메인 전문가가 ontology 를 작성할 때 다음 두 종류의 부담이 있다:

1. **Grammar 부담** — facets, lookupRule, scope, matchPattern 등 형식적 어휘
2. **Expression Gap** ⭐ — *"도메인을 알아도 어떻게 쓸지 모르겠다"*. 도메인 멘탈 모델 → 형식적 ontology 표현 사이의 갭. 단순 어휘 학습이 아닌, 표현 방식 자체의 부담.

이게 Palantir 가 컨설턴트를 동반시키는 본질적 이유. onTong 에서는 AI 가 그 컨설턴트 역할을 한다.

### 1.2 AI 의 역할 — 번역기가 아닌 컨설턴트

| 차원 | 번역기 (탈락) | 컨설턴트 (채택) |
|------|---------------|------------------|
| 입력 | 사용자 자연어만 | 도메인 + 코드 + 사용자 단편 정보 |
| 판단 | 단순 변환 | granularity / 패턴 일관성 / 누락 식별 |
| 출력 | grammar 변환 결과 | 인터뷰 + 가설 + 추천 + 경고 |
| 모델 | Round 5 작업의 절반 | Round 5 작업 전체 |

### 1.3 Reference

Round 5 archive (`toClaude/modeling/round5-live-authoring.html`) 의 12 step 이 그 자체로 ground truth interview corpus. AI 의 spec 추출 reference 로 사용.

---

## 2. MVP Scope — Option γ (전체)

10가지 capability 모두 구현:

| # | Capability | 사용 모델 |
|---|------------|-----------|
| 1 | 코드 추출 (JPO/Service/Action 자동 분석) | Sonnet |
| 2 | 가설 모델링 (1차 entity 추론) | **Opus** |
| 3 | 인터뷰 설계 (Q 분해, 1~2줄 답변용 placeholder) | Sonnet |
| 4 | 도메인 답변 흡수 (자유서술 → 항목별) | Sonnet |
| 5 | 구조 갭 탐지 (도메인 vs 코드 비대칭) | **Opus** |
| 6 | 모델링 옵션 제시 (A/B/C trade-off + ★ 추천) | **Opus** |
| 7 | 패턴 일관성 검사 (이전 entity 와 비교) | Sonnet |
| 8 | 표시명·식별자 결정 (한국어 + 영어 PascalCase) | Sonnet |
| 9 | archive 자동 생성 (표·다이어그램) | Sonnet (또는 templated) |
| 10 | 다음 step 제안 (의존성 분석) | Sonnet |

---

## 3. Architecture

### 3.1 onTong 통합 위치

- Section 2 (Modeling) 안에 새로 "Authoring 모드"
- 기존 ReAct 채팅 에이전트와 **별도** (ReAct = 검색·조회 / Authoring = 인터뷰·작성)
- 모드 전환 UI

### 3.2 협업 모델 — M-2 (branch + merge, git 식)

각 운영자가 본인 branch 에서 1:1 깊이의 인터뷰. 합의되면 main 에 merge.
- 충돌은 ontology entity 단위로 명시 (Git PR review 와 유사)
- onTong 이 이미 git-aware 이므로 거부감 적음
- 단점: merge UX 가 운영자 부담

### 3.3 맥락 5중 RAG 자동 inject

매 turn AI prompt 에 다음 5개 자동 주입:

1. **Decision Log** — 합의된 모든 결정 (누가 언제 어떤 옵션을 선택했고 왜)
2. **In-Flight 작업** — 다른 branch 진행 중 작업 list
3. **패턴 라이브러리** — 이전 entity 의 패턴 (Plant+Constraint, 2D 구간표 등)
4. **본 branch 인터뷰 history** — 운영자 본인의 모든 대화
5. **Code anchor** — JPO/Service/Action 위치 + 이미 매핑된 entity

### 3.4 충돌 처리

| 충돌 | 처리 |
|------|------|
| 이름 중복 | merge 시 알림 + 둘 중 선택 또는 통합 |
| 패턴 불일치 (entity vs facet) | AI 자동 탐지 → 합의 채팅 생성 |
| 매핑 중복 (같은 코드 anchor) | 양보 또는 분담 재정의 |

---

## 4. UX Patterns (Round 5 HTML → Product)

| Round 5 패턴 | Product UX |
|--------------|------------|
| "내 추측 (코드에서)" 표 | 매 turn 자동 첨부 — collapsible "내 추측" panel |
| 옵션 A/B/C 비교 표 + ★ 추천 | "옵션 컴포넌트" — 표 + 추천 별표 + 1-click 선택 |
| "1~2 줄 OK" 친절한 placeholder | 각 question UI 에 hint + skip 버튼 |
| archive 표·다이어그램 자동 생성 | 각 step 종료 시 markdown/diagram 생성 → entity history 탭 |
| "세분화" 즉시 명령 | 인터뷰 중 "더 작게 쪼개줘" 명령 + AI 가 question 분할 |
| 비대칭/갭 발견 시 별도 step | AI 가 갭 발견 시 인터뷰 일시 중단 + 별도 "갭 토론" 모달 |

### 4.1 Live Preview (좌우 분할)

- **좌측 (채팅)**: 인터뷰 흐름 (지금 우리 협업 그대로)
- **우측 (preview)**: 답변 즉시 entity 객체 생성 → 카드/그래프
  - 사용자 "확정" 누르면 ontology DB 영구 저장
  - 그래프는 dagre/d3 자동 레이아웃
  - 다른 운영자 branch 의 entity 도 read-only 로 보임

### 4.2 archive 와 preview 의 차이

| | archive | preview |
|-|---------|---------|
| 형식 | 한국어 + 표 (사람용) | BusinessTerm 객체 (DB 저장 가능) |
| 저장 | history 텍스트 | ontology DB entity |
| 수정 | 다음 채팅 턴 | preview 클릭 → 인터뷰로 |

---

## 5. Cost Optimization — 5축 (2-tier 모델)

### 5.1 Tiered Model Routing — Opus + Sonnet 만 (Haiku 미사용)

| Tier | 모델 | 작업 |
|------|------|------|
| Hard | **Opus 4.7** | 가설 모델링 / 옵션 trade-off / 구조 갭 탐지 / 비대칭 정정 후 재추천 |
| Standard | **Sonnet 4.6** | 코드 추출 / 답변 정리 / 인터뷰 생성 / 패턴 검사 / archive 생성 / 표시명 결정 |

### 5.2 Prompt Caching (Anthropic native)

- 결정 로그·패턴 라이브러리·코드 anchor 는 캐시 (5분 TTL)
- 두 번째 호출부터 input cost ~10% (90% 할인)
- 인터뷰 빠르게 진행되면 항상 hit

### 5.3 Structured Output

- "옵션 표 + 추천" 같은 패턴은 Pydantic schema 로 강제
- 자유서술 마크다운 대신 structured JSON
- 출력 token 절감 + UI 안정 + 파싱 안정

### 5.4 Code-not-LLM (deterministic)

LLM 호출 없이 코드로 처리:
- 표시명 ↔ id 변환 (매핑 테이블)
- archive 표 → markdown 직렬화 (템플릿)
- entity 그래프 차트 (dagre 자동 레이아웃)
- 중복 entity 이름 검사 (DB query)
- code anchor 매칭 정확도 (string match)

### 5.5 Pre-baked Pattern Templates

자주 나오는 패턴 저장:
- **Plant + Constraint Composition** (Round 5 Step 5)
- **2D 구간표 (CEILING_2D lookup)** (Step 7)
- **Asymmetric scope (Group=top / Capability=Plant)** (Step 10)
- **Wildcard + matchPattern** (Step 5 + 8)

AI 가 사용자 답변을 듣고 "이건 패턴 X 다" 분류 → 템플릿 fill → 끝.

### 5.6 비용 추정 (참고)

| 시나리오 | 비용 |
|----------|------|
| Naive (모두 Opus) | ~$10 (round 5 100 턴 가정) |
| 2-tier (Opus + Sonnet) ★ 채택 | ~$4.5 |
| 3-tier (+ Haiku) | ~$2.6 (탈락) |

→ 2-tier 로 ~2.2x 절감. 한 entity 인터뷰 = ~$0.5. 100 entity ontology = ~$50.

---

## 6. Satisfaction Tactics (비용 영향 없음)

| 전략 | 효과 |
|------|------|
| 응답 streaming | "AI 가 생각 중" 체감 ↓ |
| "가설부터 던지기" 강제 | 적극성 ↑ |
| preview 즉시 갱신 | "함께 만드는" 감각 |
| archive history 검색 | "Step 5 에서 뭐 결정?" 즉시 조회 |
| 명시 명령 즉시 반응 | "세분화" / "다시 추천" 1턴 처리 |

만족감 80% → ~90% 달성 목표.

---

## 7. Grammar Simplification (Authoring AI 가 사용할 새 grammar)

기존 grammar 의 30% 발명 부분을 정제:

| 기존 | 신규 | 효과 |
|------|------|------|
| `facets` | `properties` | Palantir 와 정합. 친숙도 ↑ |
| `lookupRule: CEILING_2D` 같은 enum | "어떻게 룩업하는가" 자연어 + 코드 함수 reference | 유연성 ↑, 학습부담 ↓ |
| `matchPattern: EXACT/WILDCARD` | row 자체에 `match: '*'` 표시 | 단순 |
| `scope: 회사·소` | `ownedBy` 관계 (없으면 top-level) | 명시 |
| `tabular [(...)]` | 그대로 유지 | 표준 회복 시 entity 폭증 trade-off — 의도적 채택 |

→ 결과: 학습 표면적 30% 감소.

---

## 8. Roadmap

| Phase | 내용 | 산출물 |
|-------|------|--------|
| **B.1** ✓ | 1차 요구사항 (γ 채택) | Step 13 archive |
| **B.2** ✓ | Live preview + Multi-Operator + UX | Step 14 archive |
| **B.3** ✓ | 가성비 5축 + 만족감 5 전략 | Step 15 archive |
| **B.4** ⏳ | Design 문서 (이 문서) + review | `authoring-ai-design.md` |
| **B.5** | Prototype — entity 1개로 검증 (HrPlant 추천) | 동작 가능 demo |
| **B.6** | 전체 구현 (10 capability) | onTong Authoring 모드 |
| **B.7** | slab-design ontology 재실행 (보류 작업 재개) | 완성된 ontology |
| **B.8** | Gap Inspector (Step 11) 통합 | 자동 갭 탐지 |
| **B.9** | Customer / Productivity 표준 (Phase A.8~) | 8 표준 ontology 완성 |

Round 5 의 slab-design ontology 작업은 B.7 에서 재개. 그동안의 archive 는 폐기 X — 인터뷰 corpus 로 활용.

---

## 9. Risks & Open Questions

### 9.1 Multi-operator merge UX
- M-2 채택은 했지만 entity 단위 merge 의 운영자 경험은 미정.
- prototype 단계에서 사용자 테스트 필요.

### 9.2 LLM 비용 실측
- 위 추정은 추산. prototype 에서 turn 별 비용 로깅 → routing 정책 보정.

### 9.3 Grammar 단순화 vs 기존 entity 호환
- 기존 onTong 에 이미 entity 가 있다면 마이그레이션 정책 필요.
- 현재 round 5 작업은 archive 만 있고 entity 0개라 영향 없음.

### 9.4 Prompt Caching 효과 의존성
- 5분 TTL — 인터뷰가 짧게 끊기면 cache miss 증가.
- 모니터링 필수.

### 9.5 패턴 라이브러리 진화
- Pre-baked patterns 는 처음엔 비어있음. 운영자 확정 → 자동 등록 메커니즘 필요.

---

## 10. 핵심 차별화

> "ontology 작성 비용을 LLM-naive 도구의 1/2~1/4 수준에서, 도메인 전문가 혼자도 가능하게."

- Palantir Foundry: 시각 UI + 컨설턴트 동반 (비싼)
- Apache Atlas / DataHub: 단순 typed entity (표현력 부족)
- OWL/RDF 도구: 학술적 (학습부담)
- **onTong**: AI 컨설턴트 + 가성비 routing + 살아있는 preview + git-식 협업

---

## 11. 검토 요청 (Step 16 에서 답변 완료)

Step 16 답변 정리:
- Q1: 인증·권한 불필요. 데이터 모델/모니터링/API design 은 prototype 단계엔 minimal (Step 17 에서 명확화).
- Q2: 보강은 iterative — 발견되면 그때 고침.
- Q3: Roadmap OK.
- Q4: 첫 prototype = **HrPlant**.
- Q5: 우선 mitigate = 9.1 / 9.3 / 9.4 / 9.5 (9.2 비용 실측은 prototype 진행하며 자동 측정).
- Q6: 본인 review.
- Q7 ⚠️ 새 우려: scale·latency → §12 추가 (아래).

**Q1 quality bar (Step 17):** "minimal 을 너무 대충 만들어서 본 모델 만들 때 문제 생기지 않도록" — prototype 도 실제 데이터 layer / LLM routing / API 패턴 사용. 임시방편 로직 금지.

---

## 12. Scale & Latency (Step 17 추가)

### 12.1 Assumptions
- 5K+ classes / 100K+ documents / 100~500 ontology entities / 3~10 concurrent operators

### 12.2 작업별 Latency (naive vs 최적화)

| 작업 | naive | 최적화 후 | 색 |
|------|-------|-----------|-----|
| 코드 anchor lookup | ~10ms | ~10ms | 🟢 |
| 표시명 ↔ id 변환 | ~1ms | ~1ms | 🟢 |
| archive 직렬화 | ~5ms | ~5ms | 🟢 |
| 코드 추출 (large repo) | ~30s | ~1s | 🟡 (lazy + index) |
| 인터뷰 LLM 1 turn | 3-8s | 3-6s (caching) | 🟡 |
| 패턴 일관성 검사 | ~10s | ~500ms | 🟡 (RAG top-5) |
| Decision Log 검색 | ~5s | ~50ms | 🟡 (FTS5) |
| 그래프 전체 렌더 | ~10s+ | ~500ms | 🔴 (subgraph) |
| Branch merge conflict | ~10s+ | ~1s | 🔴 (hash diff) |
| 동시 운영자 cache | miss 폭발 | namespace 분리 | 🔴 |

### 12.3 5 정책 (모두 채택)

1. **SQLite FTS5 + 임베딩 RAG** — 코드 metadata, Decision Log, 패턴 라이브러리. (5K 클래스 feedback 과 일관).
2. **Subgraph navigation** — 현재 entity + 1-hop neighbors 만 렌더. 클릭 시 확장. (ontology graph UX feedback 과 일관).
3. **Layered Prompt Caching** — Layer 1 (전역, 모든 운영자 공유) / Layer 2 (branch 별) / Layer 3 (turn). 운영자별 namespace.
4. **Lazy chunked 코드 추출** — repo import 시 metadata 만, 인터뷰 도중 file body on-demand chunk 단위.
5. **Hash diff merge** — entity·property 단위 hash, branch 간 hash 비교. 변경된 것만 LLM 충돌 분석.

### 12.4 진짜 병목 — LLM 자체 시간

위 정책 적용 후 남는 위험: LLM ~3~6s. 대응:
- **Streaming 응답** — 글자 단위로 → ChatGPT/Claude 와 유사한 체감
- **첫 turn cache miss** — UI loading 표시. 이후 cache hit 일반.
- **점진적 merge UX** — 100+ entity 한꺼번에 conflict 시 entity 단위로 분할 review (Risk 9.1 mitigation).

평균 turn: ~3-5s (LLM + UI render).

---

## 13. 검토 완료 (Step 17 에서 답변)

- Q1: prototype minimal — 본 모델 만들 때 문제 없도록 quality bar 유지. 임시방편 금지.
- Q3: 5 정책 전부 동의.
- Q4: scale·latency 우려 해소.
- Q5: §12 추가됨.
- Q6: prototype (B.5) 진입 OK.
