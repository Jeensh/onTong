# 4-Level Graph 한계 + 팔란티어 비교 분석

**작성**: 2026-05-02 · **목적**: P11 메모 응답 — "지금 4-level 로 코드 + 도메인 다 커버되나? 팔란티어 비교 후 한계 + 좋은 방법"

---

## 1. 팔란티어가 가진 시각화 무기

### 1.1 Workflow Lineage
- **Cross-ontology relationships** 한 화면에 (한 ontology 만이 아닌 여러 도메인 동시)
- 노드 선택 → Workshop 컴포넌트 자동 highlight (양방향 trace)
- 모든 ontology 의 entities + relations 통합

### 1.2 Vertex (시뮬레이션 + 그래프 통합)
- **Dynamic styling** — color/size 를 parameterized condition 으로 (verification level / 시뮬 state / 위험도)
- **Layer styling** — 같은 그래프 위에 여러 시각 layer overlay
- **Search Around panel** — point-and-click 으로 multi-step filtered sub-graph 생성
- **Chain models** — 한 model 의 output → 다른 model 의 input 자동 연결
- **Scenario 통합** — parameter override 시 그래프 위에서 변화 시각
- **Current vs Simulated state** 동시 시각

### 1.3 Workshop graph widget
- 그래프 widget 내장 (graph / template / diagram)
- 그래프 ↔ widget interaction (선택 시 detail)

---

## 2. 우리 V6 4-level 의 한계 — 9 가지

### 한계 1. 단일 lens 만 — 여러 차원 동시 시각 X
**현재**: kind 별 색 (Action 주황, Term 보라 등) 만.
**문제**: VerificationLevel / domain / confidence / 시뮬 state 등 **여러 의미** 를 동시에 못 봄.
**팔란티어**: Vertex Dynamic styling + Layer styling.

### 한계 2. Cross-domain edge 안 강조
**현재**: 도메인 안 엣지나 도메인 가로지르는 엣지나 같은 굵기.
**문제**: SCM 도메인의 Action 이 Quality 도메인의 Term 에 의존 = 위험 지점인데 시각적 강조 X.
**팔란티어**: Workflow Lineage 가 cross-ontology 명시.

### 한계 3. Path-trace 부재
**현재**: 한 노드 클릭 = 다음 level 진입만.
**문제**: "이 Term 변경 시 영향 path 전체" 를 그래프 위에서 highlight 하는 기능 없음.
**팔란티어**: Vertex 의 Search Around — 노드의 dependencies/dependents 즉시 sub-graph.

### 한계 4. L4 까지 가도 anchor 단위 micro-graph 부재
**현재**: L4 = 코드 메서드 + literal anchor 4개만 평면.
**문제**: 메서드 한 개의 본체 안 dataflow (param → local → branch → return) 가 안 보임. value_flow / mutation / extracted_rules 풍부한 정보 활용 X.
**팔란티어**: Functions 단계까지만 (코드 raw 미시각화). **우리는 더 깊이 갈 수 있음 (강점)**.

### 한계 5. 시간 차원 없음
**현재**: 현 시점 graph 만.
**문제**: signature_locked_at 같은 timestamp 활용 X. "지난 주 vs 이번 주 진척" 비교 X.
**팔란티어**: Scenario "fork" 가 있지만 timeline 은 약함.

### 한계 6. Multi-instance / version 표현 X
**현재**: 한 노드 = 한 fqn 만.
**문제**: Action signature 변경 시 v2 fork 했을 때 v1/v2 동시 보기 X.
**팔란티어**: Scenario branch 제공.

### 한계 7. 5000+ 노드 자동 cluster X
**현재**: mock 데이터 (10개 미만) 라 OK 보임.
**문제**: 실제 5000+ 클래스 + 142 actions = 1000+ 노드. 자동 clustering / community detection 없음.
**팔란티어**: Vertex 가 명시적 cluster, 우리는 unclear.

### 한계 8. Filter / Search highlight 부재
**현재**: 그래프 모드에 filter UI 없음.
**문제**: "verification SIM_VERIFIED+ 만" / "domain=quality 만" / "검색어 매칭 노드 highlight" 못 함.

### 한계 9. Backward (수정모드) 의 그래프 통합 약함
**현재**: Backward 모드 = 4-card grid 텍스트.
**문제**: 영향 받는 노드 들이 그래프 위에서 visual highlight 가 더 강력. P10 의 cascade/path 가 그래프 mode 와 자연 결합.

---

## 3. 우리 vs 팔란티어 — 차별점

| 영역 | 팔란티어 | onTong V6 | onTong 잠재력 |
|---|---|---|---|
| **Cross-ontology** | ✓ Workflow Lineage | △ L1 도메인만 | ✓ V7: cross-domain edge 강조 |
| **Dynamic styling** | ✓ Vertex Layer | ✗ 단일 lens | ✓ V7: Lens 시스템 |
| **Search Around** | ✓ point-and-click sub-graph | ✗ hierarchical drill-down 만 | ✓ V7: 노드 right-click |
| **시뮬 통합** | ✓ Scenario + dynamic styling | △ A2 별도 | ✓ V7: 시뮬 lens |
| **Chain models** | ✓ output→input | ○ Action sub_actions | △ workflow Action 만 |
| **Time / version** | △ Scenario | ✗ | ▲ Phase 2 |
| **5000+ cluster** | ✓ | ✗ | ▲ Phase 2 |
| **★ 코드 anchor 단위** | ✗ Functions 추상화 | △ L4 평면 | ✓ V7: L5 micro-graph (우리 고유) |
| **★ Java OO 다형성** | ✗ Object Type 만 | △ Realization 다중 | ✓ V7: 다형성 dispatch path 시각 |
| **★ 매뉴얼 통합** | ✗ | ✓ DESCRIBED_IN | ✓ V7: 매뉴얼 fragment 노드 |
| **★ 매핑 신뢰도** | ✗ | △ VerificationLevel | ✓ V7: verification lens |

★ = onTong 만의 차별 (팔란티어 안 다룸).

---

## 4. V7 보강 8 안

### A. Lens 시스템 (팔란티어 dynamic styling 차용)
같은 그래프 위에 4 종 lens 토글 / multi-lens:
- **Verification lens**: 노드 색 = level (회색/노랑/초록 gradient)
- **Domain lens**: 색 = 도메인 (4 색)
- **Confidence lens**: 엣지 굵기 = realization confidence
- **Simulation lens**: 노드 크기 = 시뮬 hot path 빈도 (A2 plug 시)

### B. Path-trace mode (양방향)
한 노드 클릭 → "영향 path" 모드:
- **Forward**: 이 노드 → 사용하는 모든 노드 (outgoing cascade) 강조
- **Backward**: 이 노드 ← 의존 모든 노드 (incoming cascade) 강조
- 양방향 동시 가능, hop 깊이 1~∞ 슬라이더

### C. Search Around panel (팔란티어 차용)
노드 right-click 메뉴:
- "X-hop dependencies"
- "X-hop dependents"
- "관련 매뉴얼 fragments"
- "이 노드의 영향 받는 코드 위치"
→ 즉시 sub-graph 로 zoom

### D. L5 — Anchor micro-graph (NEW, 우리 고유)
L4 의 메서드 1개 더블클릭 → L5 진입:
- param → local → branch → return dataflow 시각
- value_flow / mutations / extracted_rules 활용
- 각 anchor 노드 클릭 → 매핑 슬롯 표시

### E. Cross-domain edge 강조
- 도메인 boundary crossing edge: 노란 색 + 굵게
- "이 변경이 다른 도메인에 영향" 자동 detect + 경고

### F. Filter sidebar (그래프 모드 좌측)
- Verification min level
- role (domain/framework/infra)
- domain (SCM/Quality/Production/Logistics)
- confirmed-only toggle

### G. Search highlight (그래프 위)
- 그래프 모드에서 검색박스 → 매칭 노드 highlight + 나머지 dimming
- ⌘F 단축키

### H. 5000+ cluster (Phase 2)
- Community detection (Louvain/modularity)
- 줌 레벨 별 자동 expand/collapse
- "1000+ 노드 시 자동 cluster" mode

---

## 5. Backward 모드 강화 (P10 4가지)

### Side-by-side diff
- 좌: 현재 (As-is) / 우: 제안 (To-be)
- 코드 / Term / Rule 모두 diff

### Risk score
- 영향 크기 (몇 곳 수정?) × 시뮬 통과 신뢰도 × HARD-rule 위반 가능성
- 0~100 score 표시

### Cascade preview
- 직접 영향 + 간접 영향 (다른 Action 의 effect → 또 다른 Term)
- depth 1~∞ 슬라이더로 cascade level

### Rollback / branch 분기
- 가설 여러 개 동시 (Scenario 처럼)
- 각 가설 = 독립 branch
- branch 비교 / merge / discard

---

## 6. 결론

**4-level 만으로 부족**: 9 한계 중 6개 (1-3, 5, 6, 8) 는 단순 level 추가로 해결 안 됨. **시각 layer / lens / path / search** 같은 새 mechanism 필요.

**우리 차별 강점**: 코드 raw + 매뉴얼 + 매핑 신뢰도 = 팔란티어가 못하는 것. V7 의 L5 (anchor micro-graph) + verification lens + 매뉴얼 fragment 노드 가 차별 포인트.

**V7 통합**: 위 보강 A~G + Backward 강화 4가지 → 단일 prototype.
