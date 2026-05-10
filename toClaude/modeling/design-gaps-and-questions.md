# onTong — 디자인 갭 및 미해결 의문

> **작성**: 2026-05-07 · `section1-2-3-overview.html` 발표 가이드 정리하면서 식별된 영역들.
>
> **범위**: project_decisions_v3 (12개) + v4 (16개) 가 ground truth 인 상태에서
> 논리적으로 막히거나, 명세 부재거나, 운영 시 모호한 영역.
>
> **결정자**: 사용자. 각 항목은 옵션을 나열하되 추천만 함 (강제 X).
>
> **활용**: 발표 자료 (overview.html) 가 "이런 부분은 미해결" 이라고 솔직하게 라벨링하기 위한 단일 ground truth. 발표 시 외부 관계자에게도 그대로 공유 가능.

---

## 0. 한눈에

| # | 영역 | 한 줄 요약 | 심각도 |
|---|---|---|---|
| 1 | VerificationLevel — SIM_VERIFIED 자동 결정 | 시뮬레이션이 "통과" 했다는 기준이 명세 부재 | 🔴 핵심 |
| 2 | Anchor invalidation | 코드 변경 후 stale anchor 자동 발견 + 재confirm 흐름 미명세 | 🔴 핵심 |
| 3 | composite parts inheritance | extends 시 effective_parts 의 override 규칙 모호 | 🟡 중간 |
| 4 | 시뮬레이션 input fixture | DB 룩업 함수의 sandbox 데이터 source 미구현 | 🔴 핵심 |
| 5 | Java interface dispatch — Python 재현 | 다형성 코드의 sandbox 실행 방식 미설계 | 🔴 핵심 |
| 6 | Gap Inspector 부재 | 코드 ↔ ontology 갭 자동 발견 도구 보류 | 🟡 중간 |
| 7 | (codeType, codeField) → atomic invariant | DB 강제 vs API 강제 vs 충돌 허용 — 미결정 | 🟡 중간 |
| 8 | PRIMARY vs PARTIAL TR 의미 | composite ↔ entity 와 atomic ↔ entity 의 invariant 차이 | 🟡 중간 |
| 9 | 8 표준 domain naming 일관성 | 자동 recommend 결과가 흩어짐. 정정 스코프 미결정 | 🟢 가벼움 |
| 10 | Authoring AI 비용 vs 100K entity scale | 풀 자동화 비용 비현실. 운영 모델 명세 부재 | 🟡 중간 |
| 11 | Two-Layer ground truth 충돌 | 코드 vs 사용자 합의 ontology — 누가 우선? | 🔴 핵심 |
| 12 | dispatch_source.user_confirmed 큐 흐름 | Case 5/6/7 사용자 확정 UX 명세 부재 | 🟢 가벼움 |
| 13 | constraint vs 방어로직 갭 — UI/UX | ontology 제약사항이 코드에 검증 안 됨을 모델러에게 명시 — 미설계 | 🔴 핵심 |
| 14 | anchor 의 권한 / 감사 로그 | 50K anchor 의 confirmed_by / last_audit_at 메타 부재. PR sign-off 절차 0 | 🟡 중간 |
| 15 | 동시성 / 충돌 해결 | 운영자 A·B 가 같은 method 의 다른 anchor 동시 수정 시 정책 부재 | 🟡 중간 |
| 16 | 신뢰도 부패 | confirm 후 영원히 confirmed? 도메인 진화 시 재검증 주기 0 | 🟡 중간 |
| 17 | anchor invalidation 폭발 | refactoring PR 1개 머지 → 수백 anchor 동시 stale → 큐 폭발 | 🔴 핵심 |
| 18 | 신참 user_queue 오답 | branch anchor 잘못 confirm → false-positive ENFORCED → 시뮬 신뢰도 거짓 상승 | 🟡 중간 |
| 19 | god-method 일반화 | 23 줄 cumulativeProductivity 외에 5K 줄 god-method 의 anchor 검출 정밀도 미입증 | 🟡 중간 |
| 20 | enforced 판정 mechanism tier | AST 매칭 / LLM / 사람 confirm 의 3-tier — false-positive 률 명시 부재 | 🟡 중간 |
| 21 | 성능 / 인덱싱 / 검색 | 50K row 에서 binding_target FQN 검색 인덱스 / cache 전략 0. feedback_scale_5k_classes 위반 | 🔴 핵심 |
| 22 | Spring Data JPA / 자동 생성 SQL 의 anchor 처리 | method name 자체가 비즈니스 로직 (findByXxxOrderByYyyAsc) — body anchor 부족. @Query / JPQL / native SQL 도 동일 | 🔴 핵심 |
| 23 | NPE → HIST FAIL 미구현 (HrSpec/CastSpec) | 룩업 실패 시 NPE — 데이터 결함 사일런트. HIST 기록 미구현 (Phase B B.1+B.2) | 🟡 중간 |
| 24 | wildcard 미구현 (HrSpec) | 운영 룩업은 wildcard 지원, 코드는 정확매칭만. drama DNA. (Phase B B.1) | 🟡 중간 |
| 25 | PlantMappingService hardcoded 매핑 (CastSpec) | sm_cd → (cast_cd, machine_cd) 매핑이 코드에 박힘. 운영 변경 시 코드 수정 필요. (Phase B B.2) | 🟡 중간 |
| 26 | EdgingGroup PRIORITY in PK 디자인 quirk | PRIORITY 가 PK 일부 — 일반적이지 않음. 같은 (cmp,org) 다중 row 강제 unique. (Phase B B.4) | 🟡 중간 |
| 27 | HrMin/MaxWgt 2D sheet row 폭증 위험 | N thickness × M width = N×M row. 운영 부담. (Phase B B.5) | 🟡 중간 |
| 28 | order_chemical 24 컬럼 풀모델 향후 보강 | 8 성분 × 3 = 24 컬럼 21-step 미참조. chemistry 시뮬 시 풀모델 보강. (Phase C C.1) | 🟢 가벼움 |
| 29 | SDOrderLogic reflection 매핑 (drama DNA) | 4 Jpo → SDOrderEntity reflection 평탄화. ontology 표현 한계. (Phase C C.1) | 🟡 중간 |
| 30 | in-memory composite TR 표현 한계 | SDSlabEntity 5 work composite 의 file:line 매핑 어려움. (Phase C C.2) | 🟡 중간 |
| 31 | SLAB_DESIGN_HIST 미모델링 | FAIL 이력 + 21-step history 적재 table 미등록. (Phase C C.2) | 🟡 중간 |
| 32 | SlabNoSequence side effect | 12자리 sequence 발급. 시뮬 결정성 문제. (Phase C C.2/C.3/C.6) | 🟡 중간 |
| 33 | SdDesigner step 14 미구현 TODO | 제품단중 최대화 모드. 2022-04-01 박XX TODO. (Phase C C.3) | 🟢 가벼움 |
| 34 | SpecificGravityProvider hardcoded 매핑 | 강종 → 비중 매핑 코드 박힘. PlantMappingService (#25) 같은 패턴. (Phase C C.4) | 🟡 중간 |
| 35 | SdSecondWgtHighAction commented-out legacy (drama DNA) | 작성자 시그니처 + 날짜 + 제거 사유 주석. ontology 표현 한계. (Phase C C.5) | 🟢 가벼움 |
| 36 | SdDesigner javadoc REQUIRES_NEW vs 실제 default REQUIRED 갭 | drama DNA over-statement. P-2019-0445 부분 fix. (Phase C C.6) | 🟡 중간 |

🔴 = 풀 시연 / 외부 발표 전 결정 권장. 🟡 = 운영 시 부딪침. 🟢 = 점진 보강.

**합계 36 항목** (Phase A: #1~#22 / Phase B 신규: #23~#27 / Phase C 신규: #28~#36)

---

## 1. SIM_VERIFIED — 시뮬레이션 "통과" 의 기준 🔴

### 영역
v4 결정 — VerificationLevel state machine 6 단계: `UNMAPPED → DRAFT → SIGNATURE_LOCKED → BODY_ANCHORED → SIM_VERIFIED → PR_PROVEN`.

### 의문
앞 4 단계 (UNMAPPED ~ BODY_ANCHORED) 는 자동 계산 명확:
- TR 존재 → DRAFT
- signature_hash 매칭 + Action.params 일치 → SIGNATURE_LOCKED
- AnchorBinding 모든 anchor 등록 → BODY_ANCHORED

**SIM_VERIFIED 는 어떤 기준에 자동 전환?**
- (a) 시뮬레이션 결과가 코드 결과와 == 일 때 → 코드가 ground truth 이므로 시뮬은 항상 코드를 따라가야 = 시뮬 가치 0
- (b) 시뮬레이션이 사용자 expected output 과 == 일 때 → 사용자 expected output 정의 도구 부재
- (c) 시뮬레이션이 정상 종료 (no exception) 일 때 → 신뢰도 낮음 (semantic 정확성 보장 X)
- (d) 사용자가 한 번 confirm 한 시뮬레이션 시나리오 (input fixture + expected output) 통과 시

### 영향
- 시뮬레이션 신뢰도 calibration 의 핵심
- VerificationLevel 의 다음 단계 (PR_PROVEN — Java patch 가 PR 통과) 의 입력 게이트
- 풀 시연에서 "이 Action 은 SIM_VERIFIED 입니다" 라는 메시지의 의미 정의

### 가능 해결 방향
- **추천 (d)**: SimulationScenario entity 도입. 사용자가 시나리오 (input 6 컬럼 fixture + expected `productivity` output 같이) 확정. 그 시나리오 통과 N 회 = SIM_VERIFIED.
- 별 명세 없이 (c) 로 가면 "시뮬 통과 = 신뢰" 라는 잘못된 인식 위험.

---

## 2. Anchor invalidation — 코드 변경 후 stale anchor 🔴

### 영역
v3 결정 Q-C: "혼합 anchor confirm" — formula/literal 자동 confirmed, branch/lookup 만 사용자 큐.

### 의문
코드가 ground truth = 코드 변경 자유. 그러나:
- method body 변경 시 `body_hash` 바뀜 → 그 method 의 모든 AnchorBinding 의 fragment 가 stale (정확한 line range / AST node 가 더 이상 같지 않음)
- 자동 fuzzy match (AST diff minor 시 자동 따라감)? 또는 자동 invalidation 후 큐에 추가?

**명세 부재 항목**:
- body_hash 변경 감지 → 어떤 trigger?
- BODY_ANCHORED 자동 해제 → DRAFT 로 회귀? 아니면 STALE 신규 상태?
- 큐 폭주 위험 (5K class × 10 binding/method = 50K binding. 한 PR 에 다수 binding stale 가능)
- LLM 재추천 (fuzzy match) 의 비용 cap?

### 영향
운영 핵심. 코드가 자주 변경되면 ontology 가 항상 stale. 사용자가 매 PR 마다 큐 처리 시간 들어감.

### 가능 해결 방향
- **추천 mix**:
  - (a) signature_hash 변경: SIGNATURE_LOCKED 자동 해제 + 큐 추가 (가벼운 변경 — params 이름만 바뀐 등)
  - (b) body_hash 변경 + AST diff < 30%: 자동 fuzzy match → AnchorBinding 의 line range 갱신 + STALE 신규 상태로 표시 (사용자가 다음 보면 confirm)
  - (c) body_hash 변경 + AST diff ≥ 30%: BODY_ANCHORED 자동 해제 + LLM 재추천 + 큐
- 신규 상태 STALE 도입 검토 — 의미: "anchor 가 자동 갱신됐으나 사용자 1회 검증 필요"

---

## 3. composite parts — inheritance + composition override 🟡

### 영역
Round 5 archive — BusinessTerm 의 inheritance + composition 둘 다 DAG. Resolver.effective_parts = "own → 자손 우선 override".

### 의문
구체 의미 모호:
- A extends B. B.parts = [x, y]. A.parts = [y].
  - effective_parts(A) = ?
  - 옵션 (i): A 의 own [y] only → x 잃음
  - 옵션 (ii): A.[y] + B.[x] = [x, y] (merge, A 의 y 우선)
- atomic 이 inherited from parent 인 경우 — atomic 의 facet 만 재정의 가능?
- composition + inheritance 동시 작동: A composes C, A extends B, B composes D. effective_parts(A) = ?

### 영향
- 8 표준 + Order 4 sub-entity 처럼 hierarchical 구조 사용 시 핵심
- Resolver 의 algorithm 명세 필요 (현재 Round 5 archive 의 자연어 설명만)

### 가능 해결 방향
- **추천 (ii) merge with own override**: 자식이 명시한 part 만 own. 그 외는 부모 inherit. 같은 atomic 정의 시 자식 우선.
- override 명시 keyword (`@override` like) 도입 검토 — 의도성 강제

---

## 4. 시뮬레이션 input fixture — DB 룩업 sandbox 데이터 🔴

### 영역
v4 결정 C3 — "사용자 입력 BASE + InputAdapter plugin".

### 의문
시뮬레이션 = ontology 기반 한국어 Python 함수 실행. 함수가 DB 룩업 (예: `ProductivityStd.lookup(cmp, org, proc, grade, prodKind, customer)`) 호출 시:
- sandbox 안에서 어떤 데이터?
- 사용자 입력 BASE = 사용자 form 으로 row 입력? 어떤 UI?
- InputAdapter plugin = 외부 데이터 source. 미구현 (Round 4 leftovers).

### 영향
- 시뮬레이션의 실제 작동 여부. 데이터 없으면 lookup 결과 None → cumulativeProductivity 의 default 0.95 fallback → 시뮬 결과 부정확.
- 데모 시 fixture 어디서 만드나?

### 가능 해결 방향
- **추천 ScenarioBuilder UI**:
  - 시뮬 시나리오 = (Action target, input atomic values, **lookup row fixture**, expected output)
  - 사용자가 form 으로 ProductivityStd row 6~10 개 입력 (data table)
  - sandbox 의 DB 룩업 = mock — 입력 row 에서 정확매칭 후 productivity 반환
- 자동 추천: repo 의 test fixture / DB dump 가 있다면 자동 import

---

## 5. Java interface dispatch — Python sandbox 재현 🔴

### 영역
v4 결정 D3 — "자동 dispatcher + CallSiteAnalyzer 정적 분석". 9-enum dispatch_source.

### 의문
Java 다형성:
```java
List<RuleAction> rules = ...;
for (RuleAction r : rules) {
    BigDecimal v = r.evaluate(input);  // dispatch
}
```
이걸 한국어 Python 으로 어떻게 변환?

옵션:
- (a) Python class hierarchy + isinstance check (정적)
- (b) dispatch table (callsite 별 hardcoded — CallSiteAnalyzer 결과 활용)
- (c) Python duck typing — 메서드 이름만 일치하면 OK (실수율 가능)
- (d) Python dataclass + match-case (3.10+)

### 영향
- 룰엔진 fallback 로직 (Customer / EdgingGroup 등 8 표준의 max/min fallback) 시뮬레이션
- factory pattern (CallSiteAnalyzer Case 4) 의 sandbox 동작
- D3 dispatch_source 9-enum 의 sandbox-side 의미 정의

### 가능 해결 방향
- **추천 (b)**: CallSiteAnalyzer 가 정적 분석으로 dispatch table 추출 → PythonGenerator 가 그 테이블을 코드로 emit. user_confirmed case 만 사용자가 직접 매핑.
- (c) 만으로는 안 됨 — instanceof_guard / factory_branch 등 정적 분석으로 결정된 case 가 runtime 동작과 일치해야 시뮬 신뢰성 확보

---

## 6. Gap Inspector 부재 — 코드 ↔ ontology 갭 자동 발견 🟡

### 영역
Round 5 Phase A.7.7 — 보류 중 ("Authoring AI 후" 표시 후 후속 결정 부재).

### 의문
코드가 ground truth + ontology 가 사용자 합의. 둘이 어긋나면?
- 새 method 추가 → ontology 미반영 → BODY_ANCHORED 0 (자동 발견 OK)
- 새 BusinessRule 추가 (코드의 if 조건) → ontology Action 의 effects 미반영 → 자동 발견 어려움
- composite.parts 가 코드 field 와 mismatch (code field 추가) → 자동 발견 어려움
- ontology atomic 정의에 type 이 string(2) 인데 코드 컬럼이 string(3) 으로 변경 → 자동 발견 어려움

### 영향
- 시간 지나면 ontology 가 코드와 점점 어긋남
- 시뮬 신뢰도 (BODY_ANCHORED 였던 binding 이 사실은 stale)

### 가능 해결 방향
- Round 5 archive 의 옵션 G-1/G-2/G-3 채택 (보류 풀기)
- 매주 / 매 배포 자동 갭 스캔 + 큐 추가
- **추천 G-2** (Inline) — 매핑 워크플로우 자체에 갭 탐지 통합

---

## 7. (codeType, codeField) → atomic invariant 강제 🟡

### 영역
Round 6 Step 1 archive — "(atomic, codeType, codeField) 가 unique" 라고 명시.

### 의문
시스템이 invariant 로 강제하나?
- (codeType.X, codeField.Y) 가 두 atomic A 와 B 에 매핑되면? 도메인 의미상 한 컬럼 = 한 atomic 이어야 자연.
- 이 경우 시뮬 시 X.Y 가 어떤 atomic value 로 unification 할지 ambiguity.

### 영향
- data integrity. 충돌 row 가 들어가면 시뮬 시 결과 비결정
- API 의 PARTIAL TR 등록 시 사전 충돌 detect 부재

### 가능 해결 방향
- **추천 (a) DB unique constraint**: `UNIQUE(repo_id, code_type_fqn, code_field_name)` on TypeRealization (PARTIAL scope)
- API 에서 미리 충돌 detect + alert → 사용자가 "기존 매핑 교체할지" 결정
- 충돌 허용 모드도 옵션 (예: experimental — 두 매핑 다 keep, 시뮬 시 ambiguity warning)

---

## 8. PRIMARY vs PARTIAL TR 의 명확한 invariant 🟡

### 영역
TypeRealization scope (PRIMARY / PARTIAL).

### 의문
v4 결정에서 두 개념의 명확한 의미 부재:
- PRIMARY = entity 가 atomic / composite 자체 (1:1)
- PARTIAL = entity 의 일부 field / 일부 슬롯이 atomic / composite 의 part

**구체 케이스**:
- `CustomerStdEntity` → `term.scm.customer_std` (composite) PRIMARY → entity 의 모든 field 가 composite 의 part + facet 으로 mapping?
- atomic ↔ entity PRIMARY 가능? (예: `enum class ProcCode { SM, HR, ... }` → atomic `proc` PRIMARY)
- 한 entity 가 두 composite 에 PRIMARY 가능? (도메인 의미상 의문)

### 영향
- TR 모델의 invariant 정의 → DB constraint + API validation 결정
- composite ↔ entity PRIMARY 시 entity 의 field 가 composite parts 와 정확히 일치해야 하나?

### 가능 해결 방향
- **추천 invariant 명시**:
  - PRIMARY = exclusive (한 entity 가 한 composite/atomic 에만 PRIMARY)
  - PARTIAL = many-to-many (한 entity 의 한 field 가 한 atomic 에 매핑, 한 atomic 이 여러 entity 의 여러 field 에 매핑 가능)
  - composite PRIMARY entity 는 entity field ⊇ composite parts ∪ facets (entity 가 composite 보다 더 많은 field 가질 수 있음, 적으면 안 됨)

---

## 9. 8 표준 domain naming 일관성 🟢

### 영역
큐의 자동 추천 — domain 분포 (scm 16 / scm.spec 3 / scm.product 1 / scm.order 5 / scm.slab 4).

### 의문
8 표준 (HrSpec / CastSpec / EdgingSpec / EdgingGroup / HrMinWgt / HrMaxWgt / CustomerStd / ProductivityStd) 의 domain 일관성 부재. recommend bulk 한계.
- HrSpec / CastSpec / EdgingSpec → `scm.spec`
- EdgingGroup / HrMinWgt / HrMaxWgt / CustomerStd → `scm` 평면
- ProductivityStd → `scm.product`

### 영향
- ontology 가독성 + 자동 분류 (graph viz 의 cluster)
- Round 6 Step 2 에서 S-2 (`scm.std` 신규 통일) 추천 중 — 다른 6 표준 정정은 이번 세션 스코프 외

### 가능 해결 방향
- **추천 (a)**: Round 6 종료 후 별 phase 로 나머지 6 표준 정정 (별도 작업)
- 사용자가 Round 6 Step 2 에서 S-1 (그대로 두기) 선택 시 정정 자체 보류

---

## 10. Authoring AI 비용 vs 100K entity scale 🟡

### 영역
project_authoring_graph_agent (R6) + memory feedback_scale_100k.

### 의문
- Authoring AI 풀 사이클 1 entity ≈ $5 (cap 5+6+7+10+11+12 + reflect_every overhead)
- 5K 엔티티 = $25K
- 100K 엔티티 = $500K (사용자 메모: "100K+ 문서 규모")
- M1 (직접 인터뷰) 도 사용자 시간 1-2h/entity → 5K = 5000h+

### 영향
운영 모델. "전체 entity ontology 화" 가 가능한가?

### 가능 해결 방향
- **추천 Pareto + 점진**:
  - (a) 핵심 entity (10~50개 — 최상위 BusinessTerm root) 만 사용자 인터뷰
  - (b) 나머지는 recommend bulk (자동) + 검색 시점 spot confirm
  - (c) M2 자동화 + 신규/변경 entity 만 인터뷰 (delta)
- 100K scale 은 "전부 confirm" 의미 아닐 수도 — 사용자 의도 재확인 권장

---

## 11. Two-Layer ground truth 충돌 — 코드 vs ontology 🔴

### 영역
project_decisions_v4 — D1=C (Two-Layer 분리). + memory feedback_simulation_design — "코드가 ground truth, NOT Javadoc/매뉴얼".

### 의문
- 코드가 ground truth = 코드 변경 자유, 시뮬은 코드를 재현
- ontology 가 사용자 합의 (Round 5/6 인터뷰) = 사용자 ground truth

**둘이 어긋나면?**
- 시뮬 결과 ≠ 코드 결과 → 코드 ground truth 우선 → ontology 가 잘못 → ontology 수정
- 사용자 ontology 합의 ≠ 코드 동작 → ?
  - 옵션 (i): 코드 우선 (코드 = ground truth 원칙) → 사용자 합의 무효화 → 사용자 신뢰 손실
  - 옵션 (ii): 사용자 합의 우선 (= "이 코드 잘못") → 코드 결함 표시 → 코드 수정 흐름
  - 옵션 (iii): "intentional simplification" — 사용자가 "이건 ontology 단순화, 코드는 다른 동작" 으로 명시

### 영향
- 운영 의사결정 기본 원칙
- Gap Inspector (보류 중) 가 잡은 갭의 처리 방식

### 가능 해결 방향
- **추천 (iii) "intentional simplification"** + (ii) "code defect" 두 모드:
  - 갭 발생 시 사용자가 분류 (단순화 / 결함)
  - 단순화 → ontology 변경 X, 갭 metadata 만 누적 (Gap entity)
  - 결함 → 코드 수정 시나리오 자동 생성 (Java draft PR — v3 결정 Q-E)

---

## 13. constraint vs 방어로직 갭 — UI/UX 🔴

### 영역
Round 6 Step 3 의 사용자 통찰 (Q7d). project_decisions_v3 + Round 5 archive 의 BusinessRule 모델 + Gap Inspector (보류) 와 직결.

### 의문
사용자 인용 (정확):
> "방어로직을 도입해야하는데, 아직 레거시 코드는 방어로직이 없는 거잖아? 온톨로지 레벨에서는 제약사항으로 걸어놔야 하는 것 같고, 소스는 그걸 따르고 있지 않다면 제약사항을 어길 수 있다고 모델링 하는 사람에게 알려줄 수 있도록 UI/UX가 되어야 할 것 같은데, 어떻게 해야할지 너와의 고찰이 필요하다"

구체:
- ontology 가 BusinessRule 등록 (예: `0.50 ≤ productivity ≤ 1.0`)
- 코드가 그 rule 검증 안 함 (cumulativeProductivity 의 가드 분기 부재 — P-2020-0834 방어로직 보류)
- 모델링 하는 사람이 갭 인식 + 처리 결정 (코드 결함 / 의도된 단순화 / 개선 candidate) 가능해야

**미설계 영역**:
- BusinessRule 자동 검출 흐름 (코드 분석으로 가드 분기 자동 발견)
- ENFORCED / UNENFORCED / VIOLATED 상태 자동 분류
- 새 매핑 등록 시 toast 알림
- composite term 카드의 「제약사항」 섹션 (UI 위치 + 인터랙션)

### 영향
- 코드 결함 (P-2020-0834 같은) 의 점진 발견 — 운영 신뢰성
- 모델러의 갭 인식 — ontology vs 코드 ground truth 정합 (#11 영역과 결합)
- 시뮬 신뢰도 — rule 위반 코드의 시뮬 결과 신뢰 X (SIM_VERIFIED #1 영역 과 결합)

### 가능 해결 방향
- **추천 phased**:
  - Phase 1 (이번 Round 6 Step 7): BusinessRule entity 등록 (ontology 모델만)
  - Phase 2 (별 phase): 코드 가드 분기 AST 자동 검출
  - Phase 3 (별 phase): UI/UX — 「제약사항」 섹션 + 상태 배지 + toast
  - Phase 4: Gap Inspector (#6) 와 통합

- BusinessRule 모델 (Round 5 archive):
```
BusinessRule:
  fqn: rule.scm.std.productivity_safe_range
  applies_to_term: term.scm.std.productivity_std
  applies_to_facet: productivity
  expression: "0.50 <= productivity <= 1.0"
  severity: HIGH
  evidence: P-2020-0834
  enforced_by: []     # 검증 코드 list (방어로직)
  violated_at_call: list  # 위반 메서드 list
```

- UI 상태 배지:
  - 🟢 ENFORCED — 가드 분기 자동 검출 + 사용자 confirm
  - 🟡 UNENFORCED — 가드 분기 부재 (잠재 결함)
  - 🔴 VIOLATED — 위반 명시 (예: hardcoded 1.05)

---

## 12. dispatch_source.user_confirmed 큐 흐름 🟢

### 영역
v4 결정 D3 — 9-enum 중 user_confirmed = 사용자 큐.

### 의문
CallSiteAnalyzer 가 모호 (Case 5 generic / Case 6 Strategy Map / Case 7 Reflection) 표시 → 사용자 수동 결정. 큐의 흐름 명세:
- 큐 row 의 정보: candidate list + context + LLM 추천?
- 사용자 input format: 단일 선택 / 복수 선택 / 자유 입력?
- 사용자 입력 후 dispatch_source 자동 갱신?

### 영향
- 다형성 매핑의 사용자 협업 UX
- 이미 frontend QueueTab + ambiguous-call-sites endpoint 라이브 → 동작 검증 필요

### 가능 해결 방향
- 현재 frontend 구현 검증 → 갭 식별 → 추가 작업 결정

---

## 14. Anchor 의 권한 / 감사 로그 🟡

### 영역
AnchorBinding 운영 모델 (5K class · 50K+ anchor scale).

### 의문
- anchor 가 누구에 의해 언제 confirm 됐는지 추적 부재
- ChangeSpec 자동 PR 단계에 sign-off 절차 0 (누가 책임?)
- BusinessRule 추가 / 변경 시 권한 모델 미설계
- ontology editor / code reviewer / domain SME 역할 분리 부재

### 영향
- 50K anchor 의 신뢰성 — 누가 잘못 confirm 했는지 사고 후 추적 어려움
- 자동 PR 의 책임 소재
- 외부 audit / compliance 요구 시 답 못 함

### 가능 해결 방향
- anchor 에 메타 추가: `confirmed_by` / `confirmed_at` / `last_audit_at` / `risk_level`
- 4-eye review 정책 (베테랑 1 + 신참 1 confirm 시 승급)
- 자동 PR Step 6 앞에 SME 사인-오프 필수
- BusinessRule 변경은 도메인 SME 권한만

---

## 15. 동시성 / 충돌 해결 🟡

### 영역
multi-operator 운영 환경.

### 의문
- 운영자 A 가 anchor ② confirm 중 B 가 같은 method body 의 anchor ④ 수정 시?
- 같은 binding_target 에 두 confirm 동시 입력 시?
- 같은 BusinessRule 에 두 enforced_by 동시 등록 시?
- `_shared/` 격리 정책과 어떻게 통합?

### 영향
- 운영자 동시 작업 시 데이터 무결성
- Authoring AI 도구 (multi-operator 가능) 의 충돌 처리
- ChangeSpec 의 다중 입력 (운영자별 다른 ChangeSpec) 시 시뮬 결과 어느 게 정답?

### 가능 해결 방향
- anchor 단위 optimistic lock (`version` 필드)
- binding_target FQN 단위 lock-free queue (배치 confirm)
- 충돌 시 "두 confirm 충돌 — 어느 거 채택" UI
- BusinessRule 은 변경 lock (한 번 한 명만)

---

## 16. 신뢰도 부패 (confirmed 의 영원성?) 🟡

### 영역
VerificationLevel + AnchorBinding 의 시간 차원.

### 의문
- anchor 가 한 번 confirmed 되면 영원히 confirmed 인가?
- 도메인이 진화하면 (예: 2026 운영자가 confirm → 2028 공정 8 → 9 추가) 과거 confirm 이 stale?
- BusinessRule 의 evidence (P-2020-0834 같은) 가 시간 지나면서 의미 변화?
- 운영자 인터뷰 기반 ontology 의 staleness?

### 영향
- 5 년 후 ontology 의 신뢰성
- 시뮬 결과의 시간 의존 — 옛 anchor 기반 시뮬이 현재에 맞는가?
- 운영자 교체 시 (전 운영자 합의 → 새 운영자 비동의 가능)

### 가능 해결 방향
- `last_confirmed_at` + 재검증 주기 (예: 6 개월)
- `confirmed_by` 가 퇴사 / 부서 이동 시 자동 STALE 표시
- 도메인 변경 (BusinessRule 추가 / atomic 추가) 시 영향 받는 anchor 자동 STALE
- Round 5/6 식 인터뷰의 정기 재실시

---

## 17. anchor invalidation 폭발 🔴

### 영역
운영 시 anchor 변경 처리 (design-gaps #2 의 운영 측면).

### 의문
- 5K class · 평균 10 anchor / method = 50K+ anchor
- "early-exit 패턴 일괄 정리" 같은 refactoring PR 1 개 머지 시 수백 anchor 동시 stale
- design-gaps #2 의 "AST diff &lt; 30% 자동 fuzzy match" 가 일괄 변경 시 모두 ≥ 30% 로 떨어짐 → 큐 폭발
- 사용자 큐 처리 SLA / 우선순위 부재

### 영향
- 운영 핵심 — refactoring PR 의 비용 사용자에게 떨어짐
- 큐 backlog 누적 → 도구 사용성 추락
- ENFORCED rule 이 일괄 stale 되면 시뮬 신뢰도 일시적 ↓

### 가능 해결 방향
- 큐 처리 우선순위 (ENFORCED 검증 anchor 우선 / 중요 Action 우선)
- 일괄 변경 batch 검수 모드 (한 PR 의 모든 stale anchor 한 번에 review)
- LLM 자동 재추천 (사용자 시간 절약, 단 검수 필요)
- 우선 STALE 표시 + 점진 처리 (즉시 invalidation 아님)

---

## 18. 신참 user_queue 오답 🟡

### 영역
혼합 confirm (v3 Q-C) 의 UX.

### 의문
- branch anchor 의 도메인 의미는 베테랑만 안다고 가이드도 인정 (Q2 of self-check)
- 신참이 user_queue 를 잘못 confirm → `enforced_by` 거짓 등록 → BusinessRule 🟢 ENFORCED 거짓 표시
- 시뮬 신뢰도 거짓 상승 → 운영 사고 가능

### 영향
- false-positive ENFORCED 의 운영 위험
- 신참 confirm 의 sample-audit 부재
- 4-eye review 부재

### 가능 해결 방향
- 신참 confirm = "tentative" 상태 (베테랑 검수 후 confirmed 승급)
- 4-eye review (2 명 합의 시 confirmed)
- 베테랑 sample-audit 정기 (월 N 건)
- LLM 보조 — 신참 confirm 시 LLM 이 의견 제시

---

## 19. god-method 일반화 🟡

### 영역
AnchorBinding 의 적용 범위.

### 의문
- 본 가이드의 9 anchor 는 cumulativeProductivity (23 줄) + findFirstMatch (5 줄) 두 깔끔한 메서드
- 5K 줄 god-method 에서 anchor 50개+ 나오면? UI / 검수 부담
- framework 호출 (Spring `@Transactional`, MyBatis SQL) 과 비즈니스 코드 혼합 메서드의 anchor 정밀도?
- v4 결정 Q4'=A 의 "god-method 사각지대 흡수" 주장이 23 줄 예시로 입증 안 됨

### 영향
- 운영 코드의 다수가 god-method (특히 레거시) → 가이드의 가치가 비현실적일 수 있음
- 자동 anchor 검출의 false-positive / false-negative
- Method.role 자동 분류 (business / framework / infra) 의 정확도

### 가능 해결 방향
- 5K 줄 god-method 1 개 추가 예시 (가이드 보강)
- anchor 검출 알고리즘 명세 (AST + heuristic + LLM 보조)
- 부분 매핑 모드 — god-method 의 일부 anchor 만 매핑 OK 로 명시

---

## 20. enforced 판정 mechanism tier 🟡

### 영역
BusinessRule.enforced_by / violated_at_call 의 자동 도출.

### 의문
- branch anchor `if (p &lt; 0.50) p = 0.50;` 가 rule `0.5 ≤ p ≤ 1.0` 의 lower_bound 를 enforce 한다는 판정 근거?
- 정규식? AST 패턴 매칭? LLM 추론? — 셋 다 false-positive 률 다름
- 가이드는 "Gap Inspector 자동 분류" 라고만 함 — 실제 알고리즘 명세 부재

### 영향
- enforced 의 신뢰도 — 거짓 ENFORCED 가 시뮬 신뢰도 거짓 상승 (#18 과 결합)
- BusinessRule 추가 시 자동 분류 동작 여부

### 가능 해결 방향
- 3-tier mechanism:
  - tier 1: AST 패턴 매칭 (confidence high, false-positive low)
  - tier 2: LLM 보조 (confidence medium, 사용자 검수 필요)
  - tier 3: 사람 confirm (confidence highest)
- tier 별 false-positive 률 측정 + 표시
- enforced_by 의 evidence 필드 — 어느 tier 가 결정?

---

## 21. 성능 / 인덱싱 / 검색 🔴

### 영역
50K anchor scale 의 운영 성능.

### 의문
- ChangeSpec 입력 시 `SELECT * FROM AnchorBinding WHERE binding_target.fqn = ...` 가 50K row 에서 어떻게 빠르게?
- FQN 인덱스 / 역인덱스 / cache 전략 부재
- Workbench UI 가 5K class 의 anchor 리스트를 어떻게? 가상 스크롤?
- feedback_scale_5k_classes 메모리 ("절대로 전체 노드 렌더 X") 위반 위험

### 영향
- 운영 사용성 — 50K row 에서 검색 1+ 초 시 도구 unusable
- Workbench graph 모드 의 anchor 표시 부담
- Authoring AI 의 graph tool 호출 응답성

### 가능 해결 방향
- AnchorBinding 테이블의 인덱스: (binding_target_fqn, body_hash, kind, code_method_fqn)
- 50K row 에서 ChangeSpec 쿼리 &lt; 500ms SLA
- Workbench UI 가상 스크롤 + 페이지네이션 (anchor 100 개씩)
- 검색 우선 (FTS5) — 전체 list 안 보여줌

---

## 22. Spring Data JPA / 자동 생성 SQL 의 anchor 처리 🔴

### 영역
AnchorBinding 의 적용 범위. 사용자 통찰 (Round 6 Step 7 Q3).

### 의문
사용자 인용:
> "코드를 봤을때 저기서 매칭되는 로직은 sql로 처리되는 것 같은데, 이 경우도 우리 생각대로 로직과 매핑이 잘 연결된 온톨로지가 만들어지나?"

구체:
- `CustomerStdService.findFirstMatch` body 는 단순 호출 (`repository.findBy...` + `isEmpty` + `get(0)`)
- 진짜 비즈니스 로직 (4-key 매칭 + PRIORITY ASC) 이 **method name 자체** 에 박혀있음 (Spring Data JPA naming convention)
- body anchor 만으로는 비즈니스 로직 표현 부족
- @Query annotation (JPQL / native SQL) 의 경우 query string 자체가 비즈니스 로직 — 어떻게 anchor?

### 영향
- Repository / Service 의 도메인 매핑 정밀도 — 데이터 access layer 의 핵심 의미 누락
- 시뮬레이션 정확성 — body anchor 부족 시 sandbox generation 시 metadata 만 의존 → 신뢰도 ↓
- ChangeSpec "PRIORITY ASC → DESC" 같은 변경의 자동 검출 — method name 변경 추적?

### 가능 해결 방향
- **추천 (a)**: anchor_kind 신규 `method_signature` 도입 — method name pattern 자체를 도메인 의미와 binding
  ```
  AnchorBinding:
    anchor_kind: method_signature
    fragment: "findByCmpCdAndOrgCdAndProductNameCdAndCustomerCdOrderByPriorityAsc"
    binding_target:
      - matching_keys: [cmp, org, product_kind, customer]
      - tiebreaker: PRIORITY_ASC
  ```
- **(b)**: signature_hash 모니터링 + metadata 동기화 (현재 v3 결정 응용 — body 가 아닌 signature 변경 시 큐)
- **(c)**: @Query annotation 의 경우 query string parsing → fragment 단위 anchor 별도 처리
- **(d)**: Spring Data JPA 의 derived query parser 통합 → method name → 자동 metadata 도출

→ Round 6 Step 7 의 Customer 2 anchor (isEmpty / get(0)) 는 body 매핑만 잡음. 실제 비즈니스 의미는 metadata 가 cover. 별 phase 보강 필수.

---

## 23. NPE → HIST FAIL 기록 미구현 (HrSpec / CastSpec) 🟡

### 영역
Phase B B.1 / B.2 의 HrSpecService.lookup / CastSpecService.lookup. 운영 표준의 룩업 실패 정책.

### 의문
- 룩업 실패 시 NPE 발생 (caller side). 이상적 동작 = HIST 에 "열연공장 없음" / "연주공장 없음" FAIL 기록 + 명시적 에러.
- 현재 코드는 NPE — 데이터 결함 발견 어려움.

### 영향
- 운영 신뢰도 ↓ (사일런트 NPE)
- 시뮬레이션 fixture 작성 시 "어떤 데이터 누락이 어떤 효과를 가져오는지" 불명확
- BR `productivity_safe_range` 같은 violated_at_call 패턴으로 노출 가능

### 가능 해결 방향
- (a) BR 등록 — `rule.scm.spec.standard_lookup_must_have_hist_fail` (enforced_by: 없음, violated_at_call: HrSpecService.lookup + CastSpecService.lookup)
- (b) facets 기록만 — composite.lookup_failure_policy = "npe_silent" + design-gaps 항목

→ Phase E 결정 후보. 코드 수정 vs ontology 만 표현 trade-off.

---

## 24. wildcard 미구현 (HrSpec) 🟡

### 영역
Phase B B.1. Round 5 archive 의 wildcard 매칭 정책 (★ / %LIKE / LIKE% / NULL) 이 코드에 미구현.

### 의문
- 운영 룩업은 wildcard 지원, 코드는 정확매칭만 (`HrSpecService.lookup` = findById)
- 현재 마킹: `composite.facets.match_pattern: ["EXACT"]` + `pk_quality_issue: "wildcard_match_not_implemented"`
- 시뮬레이션 시 wildcard 정책 변경 (★ 추가 등) ChangeSpec 어떻게?

### 영향
- 시뮬레이션 wildcard 시나리오 테스트 불가 (코드 자체가 미지원)
- ChangeSpec "EdgingSpec wildcard 정책 → HrSpec 도 적용" 시 코드 추가 필요

### 가능 해결 방향
- (a) 코드 보강 (HrSpecService 에 wildcard fallback 추가) — drama DNA 훼손 우려
- (b) ontology 표현만 (현재) + Phase E 에서 ChangeSpec 시 코드 보강 제안

→ B.1 archive 의 결함 마킹으로 표현 완료. Phase E 처리 권장.

---

## 25. PlantMappingService hardcoded 매핑 (CastSpec) 🟡

### 영역
Phase B B.2. CastSpecJpo PK 6 컬럼 중 (cast_cd, machine_cd) 가 sm_cd 로부터 PlantMappingService 의 하드코딩 매핑으로 도출.

### 의문
- 운영 변경 시 (제강 ↔ 연주 매핑 변경) 코드 수정 필요
- ontology 가 hardcoded 매핑을 어떻게 노출? `action.facets.has_hardcoded_mapping: true` + Action 명시 (`map_sm_to_cast_machine`) 로 처리

### 영향
- 데이터 분리되어야 할 매핑이 코드에 박힘 → 변경 비용 높음
- 시뮬레이션 시 매핑 변경 ChangeSpec — 코드 patch 필요

### 가능 해결 방향
- (a) 운영 측에 데이터 분리 제안 (PlantMapping 테이블 신규)
- (b) ontology 표현만 + design-gaps 로 운영 인지

→ B.2 archive 마킹 완료. 운영팀 협의 후 처리.

---

## 26. EdgingGroup PRIORITY in PK 디자인 quirk 🟡

### 영역
Phase B B.4. EdgingGroupJpo PK = (cmp, org, **priority**). PRIORITY 가 PK 일부 — 일반적이지 않은 디자인.

### 의문
- 일반적 tiebreaker 는 column, PK 아님. 현재 디자인 = 같은 (cmp, org) 에 다중 row 등록 시 priority 강제 unique
- 매칭 조건 (grade/product/customer/widths) 은 PK 가 아님
- 이상적 PK = (cmp, org, grade, product, customer, hr_tgt_width range)

### 영향
- 실수로 같은 priority 등록 시 DB 제약 위반
- ChangeSpec "priority 정렬 정책 변경" 시 PK 영향 → migration 복잡

### 가능 해결 방향
- (a) 마킹만 (`composite.facets.pk_quality_issue: "priority_in_pk_unusual"`) — 현재 채택
- (b) 운영 측에 PK 재설계 제안 (Phase E 결정)

→ B.4 archive 마킹 완료. Q3 BR 정책으로 enforced_by 등록한 `edging_group_match_strategy` 와 별개.

---

## 27. 2D sheet row 폭증 위험 (HrMin/MaxWgt) 🟡

### 영역
Phase B B.5. HrMinWgtJpo / HrMaxWgtJpo PK = (cmp, org, hr_plant_cd, thickness, width). 2D sheet 의 cell 좌표 = thickness × width.

### 의문
- N thickness × M width = N×M row. 운영 부담 (특히 widefield 의 2D matrix 전체 채워야 함)
- 5K 클래스 가정 + 100K 문서 규모 (memory 정책) 와 같은 운영 시나리오 검증 필요

### 영향
- 운영 데이터 관리 비용 ↑
- ChangeSpec "thickness 단위 변경 (10mm → 5mm)" 시 row N×2 폭증

### 가능 해결 방향
- (a) facets 마킹 + design-gaps 등록 (현재 채택)
- (b) 2D sheet 대신 piecewise function 표현 — 코드 변경 필요
- (c) 운영 측에 row 압축 제안 (range-based)

→ B.5 archive 마킹 완료. Phase E 결정 (운영팀 협의 후).

---

## 28. order_chemical 24 컬럼 풀모델 향후 보강 🟢

### 영역
Phase C C.1. SDOrderChemicalJpo 의 8 성분 (C/Si/Mn/P/S/Cr/Ni/Al) × 3 (MIN/MAX/AIM) = 24 컬럼이 21-step 알고리즘에서 미참조. 코드 주석 명시.

### 의문
- 향후 chemistry 시뮬 시나리오 (강종 분류·검증) 확장 필요할 수 있음
- 현재는 composite 1 + facets <code>unused_in_21step: true</code> 마킹만 (Q3 결정)
- 풀모델 시 atomic 8 (성분) + facet 24 추가 필요

### 영향
- chemistry 시뮬 시나리오 ChangeSpec 불가 (현재)
- 운영 변경 시 (강종 spec 변경) ontology 가 표현 안 됨

### 가능 해결 방향
- (a) 현재 facets 마킹만 유지 + Phase E 일괄 결정
- (b) Phase E 에서 풀모델 (atomic 8 + facet 24)
- (c) 별도 phase F 에서 시뮬 시나리오 등장 시 보강

→ C.1 Q5 합의 — 현재 마킹만, 추후 보강.

---

## 29. SDOrderLogic reflection 매핑 (drama DNA) 🟡

### 영역
Phase C C.1. SDOrderLogic.toEntity reflection 패턴 — 4 Jpo (om/os/qd/chemical) → SDOrderEntity 평탄화. ontology 가 reflection 패턴 표현 한계.

### 의문
- Action `flatten_jpo_to_entity` (workflow kind) 로 등록했지만 reflection 의 dynamic dispatch 표현 부족
- Java dispatch sandbox 재현 (#5) 와 같은 카테고리 — Python sandbox 시뮬 시 reflection 처리 불명확

### 영향
- 시뮬레이션 정확성 — sandbox 가 reflection 매핑 에뮬레이션 어려움
- ChangeSpec "Jpo 컬럼 추가" 시 SDOrderLogic 수정 자동 추적 어려움

### 가능 해결 방향
- (a) Action.facets `uses_reflection: true` + Phase E 결정 — 현재 채택
- (b) reflection 매핑을 explicit code 로 변환 (drama DNA 훼손)
- (c) Java dispatch sandbox (#5) 와 통합 결정

→ C.1 Q6 합의. design-gaps #5 와 결합.

---

## 30. in-memory composite TR 표현 한계 🟡

### 영역
Phase C C.2. SDSlabEntity 5 work composite (first_range / second_wgt / split_state / final_range / target) 가 in-memory state. ontology TR 은 코드 위치 (file + line) 매핑.

### 의문
- in-memory state 는 코드의 specific file:line 에 매핑되지 않음 (전체 SDSlabEntity 의 23 작업필드)
- 현재 TR 은 SlabResultJpo (DB-backed) 만 매핑. 5 work composite 의 facets 는 composite 정의 자체로만 표현
- ChangeSpec "first_width_low 의미 변경" 시 추적 정밀도 ↓

### 영향
- 시뮬 신뢰도 — in-memory state 의 fragment-level dataflow 추적 어려움
- AnchorBinding 의 fragment 단위 매핑 (anchor_kind: local) 이 부분 해결책

### 가능 해결 방향
- (a) AnchorBinding 보강 (Phase E) — local var anchor 로 in-memory state 매핑
- (b) composite.facets 의 source_position facet 추가 (file:line:method)
- (c) in-memory state 자체를 별 모델링 단위로

→ C.2 Q8 합의. Phase E 결정.

---

## 31. SLAB_DESIGN_HIST 미모델링 🟡

### 영역
Phase C C.2. SDSlabEntity 의 FAIL 이력 + 21-step history 적재 대상 = SLAB_DESIGN_HIST table. 현재 ontology 미등록.

### 의문
- SdHistoryAction 3 메서드 (recordValidationFailure/recordStep/recordAlgorithmFailure) 가 적재 대상
- composite term.scm.slab.slab_design_hist 미등록 — Action 의 side_effects 만 표현
- HIST 의 PK + 컬럼 매핑 필요

### 영향
- ChangeSpec "history 적재 정책 변경" 시뮬 불가
- design-gaps #23 (NPE → HIST FAIL 미구현) 과 연결 — HIST 자체가 ontology 에 없으면 #23 의 violated_at_call 표현 어려움

### 가능 해결 방향
- (a) Phase E 에서 SLAB_DESIGN_HIST composite 등록 (cmp/org/hist_id/order_no/slab_no/step_no/step_name/error_code/snapshot/event_time)
- (b) 현재 마킹만 유지 (Action.side_effects 로만)

→ C.2 Q8 합의. Phase E 보강.

---

## 32. SlabNoSequence side effect 🟡

### 영역
Phase C C.2 / C.3 / C.6. SlabNoSequence.next() = 12자리 sequence 발급. side effect — 재호출 시 다른 값 반환.

### 의문
- atomic.slab_no.facets `generated_by: SlabNoSequence` 로 표현
- 시뮬 sandbox 에서 sequence 재현 어떻게? (예: 항상 1 증가? 임의 fixture?)
- ChangeSpec 시뮬 시 동일 입력 → 다른 slab_no 출력 = 결정성 위반

### 영향
- 시뮬 결정성 — 같은 ChangeSpec 두 번 실행 시 다른 slab_no
- ChangeSpec diff 비교 시 slab_no 차이가 noise (의미 없음)

### 가능 해결 방향
- (a) sandbox 의 slab_no 를 deterministic mock 으로 (예: "S0001", "S0002")
- (b) slab_no 를 diff 비교에서 제외 (semantic ignore list)
- (c) sequence 재현 정책 명시 (Phase E)

→ C.2 Q8 합의. design-gaps #4 (input fixture) 와 결합 가능.

---

## 33. SdDesigner step 14 (제품단중 최대화) 미구현 TODO 🟢

### 영역
Phase C C.3. SdDesigner.design 의 step 14 = 제품단중 최대화 모드. TODO (2022-04-01 박XX) 명시. 현재 미구현.

### 의문
- Round 5 archive 의 21-step 흐름 명세에는 있으나 코드 미구현
- ChangeSpec "step 14 활성화" 시뮬 시 코드 patch 필요 — 단순 ontology 변경 X

### 영향
- 시뮬 시나리오 폭 제한 — 제품단중 최적화 변형 시뮬 불가
- 향후 운영 정책 변경 시 코드 보강 필요

### 가능 해결 방향
- (a) 현재 design-gaps 등록만, Phase E 에서 구현 결정
- (b) Phase D API 명세에 step 14 placeholder 포함
- (c) 코드 보강 (drama DNA 훼손 우려, 사용자 결정)

→ C.3 Q7 합의. Phase E (또는 별 phase) 결정.

---

## 34. SpecificGravityProvider hardcoded 강종→비중 매핑 🟡

### 영역
Phase C C.4. SpecificGravityProvider.get(gradeCd) → BigDecimal 비중. 강종별 매핑이 코드에 hardcoded.

### 의문
- 운영 변경 시 (신규 강종 추가) 코드 수정 필요
- design-gaps #25 (PlantMappingService hardcoded) 와 같은 패턴
- ontology 표현 = action.facets `has_hardcoded_mapping: true`

### 영향
- 운영 자율성 ↓ (강종 ↔ 비중 매핑 변경에 코드 patch 필요)
- ChangeSpec "비중 매핑 변경" 시뮬 시 코드 patch 단계 추가

### 가능 해결 방향
- (a) 운영 측에 데이터 분리 제안 (SPECIFIC_GRAVITY_TABLE 신규 등) — Phase E 결정
- (b) ontology 표현만 + hardcoded 마킹 (현재 채택)

→ C.4 Q7 합의. design-gaps #25 와 결합 처리.

---

## 35. SdSecondWgtHighAction commented-out legacy fallback (drama DNA) 🟢

### 영역
Phase C C.5. SdSecondWgtHighAction.java:53-55 의 commented-out legacy fallback (`// 2018-06-12 김XX 긴급패치: 두께 NULL 인 강종 별도 처리 → 추후 정합성 점검에서 차단되어 제거`). drama DNA — 작성자 시그니처 + 날짜 + 제거 사유.

### 의문
- ontology 가 commented 코드 패턴을 어떻게 표현?
- 현재는 design-gaps 항목 + Action.operational_history 으로만 (논리적 표현 없음)
- ChangeSpec "주석 코드 활성화" 시뮬 시 어떻게?

### 영향
- 표현 한계 — drama DNA 핵심 영역 (CLAUDE.md 명시) 의 ontology 표현 불완전
- 향후 commented-out 코드 패턴 자동 추출 도구 필요

### 가능 해결 방향
- (a) 현재 design-gaps 등록 + operational_history 만 (현재)
- (b) Phase E 에서 anchor_kind: comment 신규 도입
- (c) ChangeSpec format 에 "주석 활성화" 동작 명시

→ C.5 Q6 합의. Phase E (또는 Phase D ChangeSpec format 결정 시) 결정.

---

## 36. SdDesigner javadoc REQUIRES_NEW vs 실제 default REQUIRED 갭 🟡

### 영역
Phase C C.6. SdDesigner.java:68 javadoc `해결: history 자체 @Transactional 분리 (REQUIRES_NEW) — 이XX 패치` 언급. 그러나 SdHistoryAction 실제 코드 = `@Transactional` (default propagation = REQUIRED, REQUIRES_NEW 미적용).

### 의문
- javadoc 의 의도 (REQUIRES_NEW) vs 실제 코드 (default REQUIRED) 갭
- 운영 이슈 P-2019-0445 (2019-06-08 history rollback) 해결로 javadoc 표현됐으나 실제 patch 는 별 클래스 분리만 — 부분 fix
- BR rule.scm.slab.history_isolated_transaction 등록 (C.6) 했지만 실제 isolation 정도 모호

### 영향
- 운영 신뢰도 — javadoc 따라 갈 수 없음 (drama DNA over-statement)
- ChangeSpec "REQUIRES_NEW 도입" 시뮬 시 의미 있는 시나리오 (실제 patch 효과 검증)

### 가능 해결 방향
- (a) 현재 design-gaps 등록 + BR.operational_history 부분 명시 (현재 채택)
- (b) Phase E 에서 ChangeSpec 시뮬으로 REQUIRES_NEW 도입 효과 검증
- (c) 코드 보강 (운영 결정)

→ C.6 Q9 합의. ChangeSpec 시뮬 후보.

---

## 정리 — 발표 시 외부 관계자에게 솔직하게 라벨링할 영역

### 시연하기 좋은 영역 (✅ 작동)
- 자동 recommend (BusinessTerm + Action + TR bulk import)
- Round 6 식 사용자-AI HTML 인터뷰 + DB confirm
- Authoring AI graph-aware ReAct (cap 1·2·5·6·7·10·11·12)
- Workbench UI (5 mode rail + L/C-L/C-R/R + Domain compound graph)
- ELK 풀 마이그 + Perspective + URL state sync

### 솔직히 말할 미해결 (⚠ 결정 필요)
- 🔴 SIM_VERIFIED 자동 결정 기준 (#1)
- 🔴 Anchor invalidation 자동 흐름 (#2)
- 🔴 시뮬 input fixture (#4)
- 🔴 Java dispatch sandbox 재현 (#5)
- 🔴 코드 vs ontology 갭의 처리 (#11)

### 점진 보강 영역 (🟡 운영 중 다듬기)
- composite inheritance override (#3)
- TR invariant DB 강제 (#7, #8)
- 8 표준 domain 일관성 (#9)
- Authoring AI 비용 모델 (#10)
- dispatch user_confirmed UX (#12)

### Gap Inspector 보류 결정 (🟡 별 phase)
- #6 — Round 5 archive 의 G-1/G-2/G-3 미결정 → 보류 풀기 결정 필요

---

**다음 액션 제안** (사용자 결정):
1. 발표 시연 전에 🔴 5개 결정 받기 (특히 #1 SIM_VERIFIED, #11 ground truth 충돌)
2. Round 6 종료 후 #9 (8 표준 domain) 정정 작업
3. Gap Inspector 보류 풀기 (#6) — 운영 신뢰성 핵심

---

## Phase D D.3 검수 합의 — 신규 등록 5 항목 (Phase E backlog)

> 2026-05-10. `handoff-spec/04-changespec-simresult-schema.md` 의 fresh-context 서브에이전트 2 검수에서 도출. WARN 레벨 — D.4 와 병행 가능, Phase E 일괄 결정.

### #37 4번째 verdict "advisory_warning" 도입 검토 🟡
**영역**: simulation verdict / explanation panel
**의문**: 3-tier (sim_verified/violation/inconclusive) 만으로 운영 사고 7건 회귀 표현 충분한가? P-2019-0445 같은 "코드와 javadoc 어긋나는데 BR 위반은 아님" 시나리오는 변별력 부족.
**영향**: drama DNA + warning-only BR 시나리오의 explanation panel 표현
**가능 해결 방향**: (a) 4번째 verdict 추가 (b) inconclusive 안에 sub_kind 필드 (c) 현행 유지 (drama 는 sim_verified 안에 표시)

### #38 transitive BR 누락 정책 (04 에 부분 반영) 🟡
**영역**: simulation verdict 판정
**의문**: 04 에서 direct BR 누락만 inconclusive, transitive BR 누락은 warning. 21-step 워크플로 (transitive BR 60+) 환경에서 이 정책이 실무에 맞는지 확인 필요.
**영향**: SIM_VERIFIED 진급 빈도 / false-negative 비율
**가능 해결 방향**: Phase E 에서 운영 데이터 수집 후 임계값 (transitive 누락 N% 까지 허용) 결정

### #39 anchor invalidation 추가 trigger (T4/T5) 🟡
**영역**: anchor invalidation
**의문**: 04 의 3-trigger (PR merge / manual / auto-detect) 외에 (T4) Maven POM upgrade — Java 라이브러리 시그니처 변경 (T5) IDE refactoring (rename / extract method) 가 빠짐. 5K 클래스 가정에서 IDE refactor 일상이라 무시 못 함.
**영향**: stale anchor 의 미감지 → 시뮬 결과 신뢰도 저하
**가능 해결 방향**: (a) IDE refactor hook (T5) 우선 — git diff + AST 비교로 method_fqn 변경 감지 (b) Maven POM upgrade 는 별도 검사 (c) Phase E 우선순위 결정

### #40 anchor 재바인딩 미처리 알림 큐 🟡
**영역**: anchor invalidation 흐름 (B4 검수)
**의문**: 재진급 흐름의 "Authoring agent 재바인딩" 책임 부분이 04 의 4.6 에서 "별도 흐름, 본 명세 외" 로 위임됨. 운영자가 재바인딩 안 하면 영원히 SIGNATURE_LOCKED 갇힘 위험.
**영향**: VerificationLevel 분포 왜곡 (잠재적 SIM_VERIFIED 회복 누락)
**가능 해결 방향**: (a) timeout 기반 alert (예: 7일 이상 재바인딩 안 됨) (b) 자동 재바인딩 candidate 큐 (c) 04.4.7 의 IncidentReview 큐와 통합

### #41 ChangeSpec scenario_fixture lookups row 형식 🟡
**영역**: ChangeSpec input fixture
**의문**: 04 의 ChangeSpec.scenario_fixture.lookups 가 `{"Customer:7": {...}}` placeholder 만. row 의 atomic-set 정의 (TableSpec → atomic_fqn 목록) 가 04 에서 빠지고 D.4 위임됨. 04 만 보고 P-2018-0098 fixture 작성 불가.
**영향**: 명세의 외부 단독 전달성 부분 손상 (04 → D.4 강결합)
**가능 해결 방향**: (a) D.4 산출과 함께 04 보강 (b) lookups schema 별도 partition (c) 현행 유지 + D.5 통합 가이드에서 cross-link

---

(이전 36 → 41 항목으로 증가. Phase A 22 + B 5 + C 9 + D 5 = 41.)

---

## Phase D D.4 검수 합의 — 신규 등록 6 항목 (Phase E backlog)

> 2026-05-10. `handoff-spec/05-runner-interface.md` 의 fresh-context 서브에이전트 2 검수에서 도출. WARN 레벨 — 본 명세 핵심 흐름은 우선 수정 6건으로 반영, 본 6 항목은 깊은 디테일이라 D.5 / Phase E 일괄 결정.

### #42 BR violation vs RuntimeException 구분 정밀화 🟡
**영역**: Java sandbox / instrumentation
**의문**: 05 Section 2.3 step 4 의 "method 안에서 throw 된 BR violation 은 정상 결과로 처리". Java 의 일반 RuntimeException (NullPointer / IllegalArgument 등) 와 BR throw 를 instrumentation jar 가 구분해야 함. 알고리즘 (어떤 exception class? 어떤 marker? throw site 와 BR.enforced_by 의 매칭?) 명세 부족.
**영향**: BR violation 의 false-positive / false-negative
**가능 해결 방향**: (a) instrumentation jar 가 BR.enforced_by method 의 throw 만 BRViolation 으로 변환 (b) 별도 BRException class 도입 + 코드 수정 (c) 모든 RuntimeException 을 BRException 후보로 + BR.enforced_by 매칭 후 분류

### #43 type_assignable 의미 (subclass / generic / primitive) 🟡
**영역**: Java sandbox dispatch_consistent 판정
**의문**: 05 Section 2.3 step 3 의 type_assignable 함수의 정밀 정의 부재. Java 의 raw type vs parameterized type, primitive vs boxed, interface vs abstract class 등 어떻게 처리?
**영향**: 04 verdict (f) 의 정확성 — false dispatch_consistent 위험
**가능 해결 방향**: (a) Java reflection 의 `Class.isAssignableFrom` 만 (b) generic type 도 고려 — `TypeToken` 기반 (c) struct equivalence 까지 (d) AST 기반 정밀 비교

### #44 LookupDataSource 3 mode 행동 차이 🟡
**영역**: lookup data source
**의문**: 05 Section 3.5 의 `fixture_with_db_fallback` / `db_snapshot` 모드의 행동 명세 부족. PK miss 시 None 반환 vs 예외, fixture override 우선순위, snapshot 의 timestamp resolution.
**영향**: 운영 사고 회귀 시 fixture 오류 (실 DB 가 다른 값 가지고 있을 때) 의 사용자 경험
**가능 해결 방향**: 각 모드별 단위 테스트 + 명세 1줄씩 추가 (D.5 또는 Phase E)

### #45 drama_dna_columns 활용처 (현재 dead field) 🟡
**영역**: TableSpec
**의문**: 05 Section 3.2 의 TableSpec.drama_dna_columns 가 정의만 있고 활용처가 어디에도 명세 안 됨. dead field 위험.
**영향**: drama DNA 정보가 시뮬 결과 / explanation panel 에 노출 안 될 수 있음
**가능 해결 방향**: (a) validate() 가 drama columns 변경 시 warning 생성 (b) sandbox dispatch 시 drama columns 의 alias 추적 (c) 제거 (현재 미활용이라면)

### #46 artifact streaming vs 일괄 dump 🟡
**영역**: artifact collection
**의문**: 05 Section 6.1 의 `jvm_log` "dispatch 별 append" — 실시간 streaming 인지 종료 후 일괄 dump 인지 미정. 03 의 GET /runs/{id}/artifacts 가 진행 중 run 부분 결과 반환 가능한지도.
**영향**: 운영 디버깅 UX (긴 시뮬 진행 상태 추적)
**가능 해결 방향**: (a) 실시간 streaming + 03 endpoint 가 진행 중 부분 반환 (b) 일괄 dump + completed 만 반환 (c) hybrid — jvm_log 만 streaming

### #47 검증 step 누락 (graalvm / 3-mode lookup / 부분 다운그레이드) 🟡
**영역**: 검증 시나리오 / Section 10
**의문**: 05 Section 10 의 7 단계 검증이 stub 1개 + jvm_subprocess 1개만 다룸. graalvm_polyglot tier, 3-mode lookup (fixture_with_db_fallback / db_snapshot), 부분 다운그레이드 (04 Section 4.3 step 4 의 stale_ratio 0.30) 검증 누락. anchor invalidation 도중 진행 중 run 처리도 빠짐.
**영향**: 본 명세의 충분성 입증 부족 — Phase E 운영 진입 전 보강 필요
**가능 해결 방향**: 검증 7 → 12 단계로 확장 (graalvm 1 + 3-mode 2 + 부분 다운그레이드 1 + anchor invalidation 도중 1)

---

(이전 41 → 47 항목으로 증가. Phase A 22 + B 5 + C 9 + D 5 (D.3) + D 6 (D.4) = 47.)

---

## Phase D 인계 검증 — 신규 등록 1 항목 (Phase E backlog)

> 2026-05-10. handoff-spec/ 인계 가능성 점검 (실제 ontology DB 상태 검증) 에서 도출.

### #48 BusinessRule 5개 archive 발췌 누락 → ✅ 해소됨 (2026-05-10)
**영역**: Phase C BusinessRule
**원인**: 1차 archive Explore agent 추출에서 archive HTML 일부 표만 발췌 → 5개 누락. archive 는 17개 다 가지고 있었음.
**해소**: 사용자 지적으로 직접 grep `rule\.scm\.` 패턴 → archive 의 17 unique fqn 모두 확인. 누락된 5개 추출 + import:
- `rule.scm.slab.absolute_max_kg_safety_cap` (Phase C 21-step body — 2017 운영 회의 history)
- `rule.scm.slab.sm_plant_active_required` (DG101 charAt(0)==' ' 가드)
- `rule.scm.slab.confirmed_plant_cd_format` (NULL/length<8 형식 가드)
- `rule.scm.slab.history_isolated_transaction` (P-2019-0445 history)
- `rule.scm.slab.slab_no_sequence_per_count` (매수 row 복제 패턴)
**최종**: ontology DB BR 17/17 완전 import. archive 가 ground truth 역할 입증.
**교훈**: Explore agent 의 grep 발췌가 부분일 수 있음 — fqn 패턴 (`rule.scm.*` 등) 으로 직접 grep 으로 한 번 더 검증하는 것이 안전.

---

## 인계 깊이 검증 — 신규 등록 1 항목 (Phase E backlog)

> 2026-05-10. 사용자 의심 ("코드 따로, 온톨로지 따로 매핑 아니냐") 으로 풀 매핑 검증 실시. 4-way (Action↔Method, Anchor↔Method, BR↔Method, Term↔CodeType) 중 3개는 100% 살아있고, atomic TR 부재 16건이 갭으로 발견.

### #49 16 atomic term ↔ code_type TR 부재 🟡
**영역**: Domain ↔ Code 매핑
**의문**: 16 atomic term (cmp / org / proc / grade / customer / order_no / slab_no / cast_cd / hr_plant_cd / machine_cd / sm_cd / edging_group_cd / confirmed_plant_cd / priority / product_kind / specific_gravity) 이 BusinessTerm 정의만 있고 어느 Java field/type 과 1:1 매핑되는지 TR 부재. 29 composite TR + 5 partial TR 만 등록됨.

**원인 분석**: 이 atomic 들은 Java 에서 dedicated type 이 아니라 `String cmp`, `String org` 같은 method 인자 String 으로 흩어져 있음. 따라서 "어느 type 의 어느 슬롯" 이 아니라 "어느 method 의 어느 인자 인덱스" 로 link 되어야 함. 현 mapping_layer 의 TypeRealization schema 는 type-level (CodeType) 만 취급 — atomic↔method-arg 의 표현 자리가 없음.

**영향**: 
- spec 04 `atomic_overrides={"cmp": "01"}` 의 path resolution 알고리즘 (§1.2) 이 동작하려면 atomic 이 어느 method 인자 위치에 등장하는지 알아야 함. 현 상태에서는 broadcast 로 fallback (모든 String 인자 후보 순회) 또는 사용자 explicit 지정.
- AnchorBinding.target_slot 이 일부 보충 (예: `action.metadata.fallback_kind`) 하지만 atomic 인자 위치 표시 전용 anchor 는 없음.

**가능 해결 방향**:
- (a) **AtomicArgBinding 신규 entity** — `{atomic_fqn, code_method_fqn, arg_index}`. 16 atomic × 평균 2~3 method 위치 = ~40 row. 자동 추출 가능 (Java parser 가 method signature 의 String 인자명 매칭).
- (b) **method_signature 보강** — `code_methods.params_atoms_json = [{"index": 0, "atomic_fqn": "term.scm.shared.cmp"}, ...]`. 같은 정보를 code_methods 안에 inline.
- (c) **현행 유지 + spec 04 path resolution 보강** — atomic_overrides 가 broadcast + 사용자 disambiguation 큐 지원. 새 entity 안 만듦.

**현 인계 영향**: 첫 시뮬 시나리오 `action.scm.std.match_customer_limit_for_order` 는 method 인자 4개 (cmp, org, proc, grade) — 이름 매칭이 1:1 이라 broadcast 작동 OK. 하지만 atomic 이 method 안에서 다른 변수명으로 흩어진 경우 (예: `String foo = order.getCmp();` 후 사용) 추적 부실. Phase E 에서 (a)/(b)/(c) 결정 권장.

---

(이전 48 → 49 항목으로 증가. Phase A 22 + B 5 + C 9 + D.3 5 + D.4 6 + 인계 검증 1 + 깊이 검증 1 = 49.)
