# Step P3-7 Summary — 데모 시나리오 끝-끝 브라우저 검증

**완료**: 2026-05-02
**범위**: 헤드리스 Chromium 으로 시나리오 walkthrough → 발견 즉시 fix → 재검증.

## 결과

3 핵심 시나리오 (S1 Import / S5 Graph / S6 Queue) 끝-끝 동작. UX 이슈 6건 발견 & fix.

## 발견 + fix 6건

| # | 문제 | 원인 | Fix |
|---|---|---|---|
| 1 | 페이지 reload 시 빈 그래프/Map | `store.ts` default `activeRepoId="scm"` (mock 잔재). 우리 import 한 건 `slab-design-real` repo_id. | default → `"slab-design-real"` |
| 2 | 188 노드 가로 한 줄로 압축, 라벨 안 읽힘 | dagre LR + 스타형 그래프 (Term/Action hub) | LR → TB + nodesep 32 / ranksep 90 + Handle Top/Bottom |
| 3 | isolated CodeType 91개 노이즈 | framework/infra code_type 이 매핑 없이 포함 | `graph_api.py` `connected_only=true` default — 188 → 117 |
| 4 | 첫 진입 노드 너무 많음 | 117 노드도 스타형 | 데이터 로드 후 가장 connected term/action 자동 focus + hops=2 (>40 nodes 일 때만) |
| 5 | focus 변경 시 viewport 안 맞음 | ReactFlow `fitView` 는 mount 시 1회 | `key={repoId|focus|hops|nodes}` remount 강제 |
| 6 | 키보드 안내 카드 minimap 겹침 | 우하단 좌표 충돌 | L3 (실제 그래프) 일 때만 카드 숨김 |

## 시나리오 검증

### S1 Import (✅)
- TopBar Import 클릭 → 모달 (form/importing/recommending/done 4 phase)
- SSE 진행률 → 353ms 완료
- Done 카드: 123 CodeType / 956 Method / 1018 CallSite + 자동 추천 큐 (29 Term / 36 Action / 34 Realization)

### S5 Graph (✅)
- 그래프 모드 진입 → 자동 focus "화학성분" (degree highest term) 2-hop
- 7 nodes / 6 edges 가시화
- **드라마 DNA 시각화**: SDOrderEntity → 4 PARTIAL (OrderOm/주문스펙/품질데이터/화학성분) amber 점선 + SDOrderChemicalJpo → PRIMARY 2건 emerald 굵게
- 검색박스로 다른 노드 focus 가능, hops 1~4 slider

### S6 Queue (✅)
- LeftPanel 큐 탭: Term/Action/Real/Code 4-section + 카운트 배지 (29/36/34/999)
- Term 첫 행 (에러코드) confirm ✓ → optimistic UI 즉시 큐에서 제거 + 백엔드 29 → 28 정합

### 미진행 (Phase 외)
- S2 "품종" 4-aliases — S5 의 PARTIAL realization 시각화로 사실상 시연됨
- S3 DG003 cascade — Backward 모드는 mock UI, 변경 영향 분석 미구현
- S4 LengthRange 시뮬 — Simulation Engine 미구현

## Phase 3 종합

| Step | 산출 |
|---|---|
| P3-1 | 데모 repo 깊이 파악 + 도메인/Action 후보 inventory |
| P3-2 | Repo Import 백엔드 (Importer + REST + SSE), 122 file → 123/956/1018 |
| P3-3 | 자동 매핑 추천 (29/36/34, glossary + Entity⊃Jpo PARTIAL 자동 검출) |
| P3-4 | Frontend Import UI (모달 4-phase) |
| P3-5 | xyflow + dagre 그래프 (focus + hops + 엣지 색상별 매핑) |
| P3-6 | 큐 confirm/reject (4-section + optimistic UI) |
| P3-7 | 브라우저 walkthrough + UX fix 6건 |

**핵심 데모 셀링 포인트**: SDOrderEntity 의 4 PARTIAL realization 자동 발견 + amber 점선 시각화 — slab-design-real 의 "Entity ⊃ 다수 Jpo 평탄화 흡수" 드라마 DNA 가 사람 손 없이 자동으로 표현됨.

## 다음 후보
- A1 Plugin framework
- A2 Simulation Agent (S4 시나리오 활성화)
- Backward 모드 (S3 시나리오 활성화)
- 또는 사용자 결정 우선순위
