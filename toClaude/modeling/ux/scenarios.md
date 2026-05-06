# C6 — UX 시나리오 + Persona 정의

**작성**: 2026-05-02
**목적**: Workbench UI 통합 화면 design 안 비교의 기준점

---

## Persona — SCM 도메인 분석가 (5명 중 대표 1)

**이름**: 지윤 (가명) · **역할**: SCM 도메인 분석가 (10년) · **나이**: 35

**배경**:
- 슬라브 제조 SCM 도메인 10년 경력
- 매뉴얼 / 표준서 작성 익숙 — 도메인 용어 정확히 구분
- Java 코드 직접 작성 경험 X — 다만 클래스/메서드 구조는 읽을 수 있음
- 시뮬레이션 / 실험 비즈니스 가설 검증 매주 1~2회

**Workbench 사용 동기**:
1. "내가 알고 있는 도메인이 코드에 정확히 매핑됐는지 확인하고 싶다"
2. "코드 변경이 비즈니스에 어떤 영향을 미칠지 가설로 시뮬해보고 싶다"
3. "코드 모르는 동료에게 '이 부분이 바뀐다' 라고 자연어로 설명하고 싶다"

**약점 / 장벽**:
- 5000+ class 한 번에 보면 압도됨
- 영문 fqn (`com.scm.RushOrder`) 만 보면 헷갈림 — 한국어 label 필요
- 매핑 정확도가 의심되면 신뢰 무너져 시뮬 결과도 안 믿음

---

## 4 핵심 시나리오

### S1 — Repo Import 후 첫 진입

**시나리오**: 신규 Java repo 분석 직후 Workbench 처음 들어감.

**user flow**:
1. "어, 클래스 1500개네. 어디서부터 봐야 하지?"
2. role 필터: domain 만 (framework/infra 숨김) → 800개로 줄음
3. 검색박스: "주문" 입력 → 매칭 5개 (Order/StandardOrder/RushOrder + 관련)
4. Order 선택 → detail 화면: extends/implements/methods/fields 한눈에
5. "이 Order 가 도메인 term 에 매핑됐나?" — TypeRealization 확인
6. 매핑 안 됐으면 → "term 등록 / 기존 term 매핑" 버튼

**필요 위젯**: Code Tree (lazy + role 필터) · 검색박스 · CodeType detail 카드 · TypeRealization 큐

---

### S2 — 매뉴얼 등록 + Term 추출

**시나리오**: 매뉴얼 1건 (slab 사양서.pdf) 가져와 BusinessTerm 들 등록.

**user flow**:
1. "매뉴얼 업로드" 버튼 → PDF 업로드
2. LLM 자동 term 추출 → 큐 (BusinessTerm 후보 12개)
3. 후보 1개씩 확인:
   - "주문" (composite, root_entity 추정) → confirm
   - "C 함량" (atomic, float, %, [0.10, 0.25] 추정) → range 약간 수정 후 confirm
   - "Slab 사양" (composite, struct_like_hint?) — 사용자 판단
4. 등록한 term 들 사이 composition 관계 그리기:
   - "주문" → HAS spec → "주문스펙" (1:1)
   - "주문" → HAS chemical → "화학성분" (1:N)
5. 확정한 term tree visualize → 큰 그림 확인

**필요 위젯**: 매뉴얼 업로드 · Term 추출 큐 · Term editor 카드 · Composition 빌더 · Term Tree

---

### S3 — Action 매핑 큐 처리 (가장 빈번)

**시나리오**: Code 분석 + Domain 등록 끝. 이제 Action 매핑.

**user flow**:
1. "Unmapped Methods" 패널 열기 → 87개
2. 첫번째 — `RushOrder.validate(Order)` :
   - "이게 어떤 Action 의 구현?" — LLM 추천: "주문_검증" (84% 매칭)
   - 사용자 OK → Action 자동 생성 + Realization 추가
3. params 매핑:
   - param `Order order` → Action.params[0] = (주문, t.order, **사용자 confirm 필요**)
4. anchor binding 큐:
   - literal `200.0` in body → 후보 slot list 에서 `params[0]<RushOrder>.spec.diameter.range[1]` 선택
   - literal `1, 5` → `params[0]<RushOrder>.priority.range`
5. 모든 anchor confirm → VerificationLevel 자동 SIGNATURE_LOCKED → BODY_ANCHORED
6. CallSite 모호 큐: `validate@Order` 호출지점 — RushOrder/StandardOrder 후보, 사용자 컨텍스트 보고 RushOrder 선택

**필요 위젯**: Unmapped 패널 · Action 카드 (param 편집) · Path picker (자동완성) · Anchor binding 큐 · CallSite 모호 큐 (후보 + 컨텍스트 + LLM 추천)

---

### S4 — VerificationLevel 진척 + 다음 작업 선택

**시나리오**: 작업 시작 전 / 끝날 때 — "어디까지 매핑됐나?" 진척 확인.

**user flow**:
1. 대시보드: 전체 Action 142개
   - PR_PROVEN: 8 / SIM_VERIFIED: 31 / BODY_ANCHORED: 47 / SIGNATURE_LOCKED: 22 / DRAFT: 18 / UNMAPPED: 16
2. "이번주 목표는 SIM_VERIFIED 50개" → 31 → 50, 19 더 필요
3. BODY_ANCHORED 47개 클릭 → 그 list 보고 "이 중 시뮬 돌릴 수 있는 것" 골라
4. Action 1개 선택 → simulation drawer (A2 agent 가 plug 됐을 때 — Phase A2)
5. 시뮬 실행 → SIM_VERIFIED 로 자동 승급

**필요 위젯**: VerificationLevel 진척 대시보드 · Action list (level 별 필터) · 진척 KPI

---

## 통합 화면이 보여야 할 것 (모든 시나리오 공통)

| # | 영역 | 위젯 |
|---|---|---|
| 1 | Code 트리 | lazy + role 필터 + 검색 |
| 2 | Domain Term 트리 | inheritance 시각화 (extends 실선/implements 점선) + composition |
| 3 | Action 카드 | nested params + realizations 다중 + verification 배지 |
| 4 | 매핑 큐 (3종) | Unmapped Methods · Ambiguous CallSites · Anchor Confirm |
| 5 | Path picker | composite tree 자동완성 (subtype cast 포함) |
| 6 | 검색 | 통합 (Term/Action/CodeType/CodeMethod/Rule) |
| 7 | Verification 진척 | 대시보드 (level 별 카운트, 클릭으로 list) |
| 8 | (Phase A) Simulation drawer | sub plugin point — 처음부터 자리만 |

---

## 통합 화면 안의 의사결정 좌표

각 design 안은 다음 8 차원에서 trade-off:

| 차원 | A 극단 | B 극단 |
|---|---|---|
| 정보 밀도 | 모든 게 한번에 보임 (대시보드) | 한 번에 한 작업 (focus) |
| 큐 우선 | 큐 (Unmapped 등) 가 메인 | 트리 탐색이 메인 |
| Code-Domain | 수평 분할 (둘 다 동시) | 단일 패널 (mode 토글) |
| 키보드 | ⌘K + 단축키 우선 | 마우스 드래그 우선 |
| 그래프 | 트리 위주 (수직 list) | 그래프 위주 (노드 시각화) |
| Inline 편집 | 모달 / drawer 분리 | 카드 안 inline edit |
| 컨텍스트 | 사이드 패널 풍부 | 메인만, 클릭으로 detail |
| Mobile | 데스크탑 only | 적응형 |

---

## 평가 기준 (사용자가 안 비교 시 사용)

1. **첫 진입 ~ 첫 매핑까지 클릭 수** — 적을수록 좋음
2. **Unmapped 큐 47개 처리 효율** — keyboard / drag 활용도
3. **검색-탐색 전환 비용** — ⌘K → 결과 → detail 흐름
4. **5000+ class 환경 성능 + 가독성** — virtual scroll / lazy
5. **5분 vs 5시간 사용 시 피로도** — 정보 노이즈

위 4 시나리오 모두 — design 안마다 "이 시나리오에서 어떤 모습?" 으로 비교.
