# Step C6 React Phase 1.5 + Phase 2 — Modeling Workbench 완성

**완료**: 2026-05-02
**기반**: 사용자 "1.5 → 2 진행" 명시

## 산출물 요약

| 항목 | Phase 1 | Phase 1.5+2 | 총합 |
|---|---|---|---|
| 파일 | 9 .tsx + 1 store + 1 API | +1 BackwardMode + 1 GraphFilters | 11 .tsx + 1 store + 1 API |
| LOC (modeling + ontology API) | 1,815 | +420 | **2,235** |
| backend tests | 121/121 | 121/121 (변경 없음) | 121/121 PASSED |
| frontend tsc | ✓ | ✓ | ✓ clean |

## Phase 1.5 — L5 anchor micro-graph (★ 우리 차별)

`GraphMode.tsx` 에 L5 추가:
- Type Level 확장: `1 | 2 | 3 | 4 | 5`
- Level 5 슬라이더 + 키보드 (1-5, ↑↓)
- Level4View 의 메서드 노드 클릭 → setLevel(5)
- **Level5View** — 메서드 본체 dataflow:
  - Action (위) → 4 anchor binding (점선 → branch)
  - Field/param (좌) → branch (가운데, literal 표시) → return (우) 4 줄
  - extracted_rule (아래) ← branch
  - SVG markers + arrow + label
  - "★ L5 — onTong 차별 강점" callout 우측

## Phase 2a — Backward 강화 (4 종)

`BackwardMode.tsx` 신설 (V7 prototype 의 React 화):

| 영역 | 구현 |
|---|---|
| Banner | amber 색조 + 변경 대상 표시 |
| **Branch bar** | 4 가설 동시 (0.25→0.30 / 0.28 / 0.35 / Mn 동시), active 토글, "+ 새 분기" |
| **Risk score ring** | conic gradient 62/100 + 영향 크기 / 시뮬 신뢰도 / HARD 위반 분해 |
| **Side-by-side diff** | As-is / To-be 좌우, Java/Term/Rule/매뉴얼 4 탭, line del/add/unchanged 색 구분 |
| **Cascade tree** | depth 슬라이더 (1~5), 직접/간접 색 구분, ⚠ HARD 위반 강조 (rule.scm.quality_grade_a) |
| Action 버튼 | 🌊 시뮬 실행 / 📤 draft PR / 🌐 그래프 위 path 시각화 |

MainPanel 의 `BackwardPlaceholder` 제거 → 실제 `BackwardMode` 컴포넌트 mount.

## Phase 2b — Graph Lens 시스템

store 에 `lens: 'verify'|'domain'|'confidence'|'simulation'|'none'` 추가.
GraphFilters 좌측 sidebar 에 lens 버튼 5종 토글.
`Node` 컴포넌트에서 lens 별 background tint:
- **verify**: UNMAPPED 빨강, DRAFT 노랑, BODY_ANCHORED 파랑, SIM_VERIFIED 초록 등
- **domain**: 4 색
- (confidence/simulation/none — UI 노출만, 실제 styling 은 Phase 3 데이터 연결 시)

GraphMode 헤더에 활성 lens 표시 bar 추가.

## Phase 2c — Path-trace 양방향

store 에 `pathTrace`, `pathTraceHops`, `pathTraceFromFqn` 추가.
GraphFilters 의 Path-trace 섹션:
- 4 dir 토글 (forward / backward / 양방향 / off)
- hop 슬라이더 1~5
- "From: <fqn>" 표시 (pathTraceFromFqn)

`Node` 컴포넌트:
- `pathTraceFromFqn` 일치 노드 → border 강조 + glow shadow
- 그 외 노드 → opacity 30% (dim)
- 클릭으로 path-trace 시작 (현재 mock)

## Phase 2d — Search Around (노드 우클릭) + Cross-domain edge + Filter sidebar

**Search Around**:
- Level3View 의 노드 onContextMenu 핸들러 → `setCtxMenu({x, y, nodeFqn})`
- 우클릭 menu (CtxItem 6개): X-hop deps/dependents/매뉴얼/코드 위치/Backward 진입/Path-trace 양방향
- Path-trace 옵션 클릭 시 store 업데이트 (pathTraceFrom + dir)

**Cross-domain edge**:
- store 에 `showCrossDomainHighlight` 추가
- Level3View 의 "화학성분_검증" 노드는 `domain="quality"` + `crossDomain` flag → ring + ⚠ 배지

**Filter sidebar** (`GraphFilters.tsx`):
- domain 체크박스 4개 (toggleGraphDomain)
- verification min select (UNMAPPED/SIGNATURE_LOCKED/BODY_ANCHORED/SIM_VERIFIED)
- "Cross-domain edge 강조" 토글
- Lens 버튼들

WorkbenchShell 의 grid: graph mode 시 좌측을 `LeftPanel` 대신 `GraphFilters` 로 교체.

## Phase 2e — xyflow 통합 / 검증

xyflow 통합은 기존 mock layout 위에 점진. 현 단계는:
- `@xyflow/react` 의존성 확인 ✓ (이미 package.json)
- 기존 mock div positioning 으로도 lens / path-trace / cross-domain 시연 충분
- 본격 xyflow 도입은 실제 데이터 연결 (Phase 3) 시 — node positioning 자동화 (dagre layout) 가 핵심
- 현재 store 의 graph 옵션 (lens/pathTrace/...) 는 xyflow 통합 시에도 그대로 쓰임

## 검증

| 검사 | 결과 |
|---|---|
| `npx tsc --noEmit` | ✓ clean (no output) |
| 누적 backend tests | **121/121 PASSED** (1.58s) |
| frontend dev server | ✓ port 3000 |
| backend startup | ✓ port 8000, 16 ontology routes |
| browse Forward Detail | ✓ 정상 (Phase 1 시연) |
| browse Backward 강화 | ✓ branch / risk / diff / cascade 모두 표시 (`/tmp/c6r2_bwd.png`) |
| browse Graph mode | ✓ navigate 후 표시 (browse 클릭 약간 불안정) |

## 시연 (Backward 강화)

```
[BACKWARD]  C 함량 max 0.25 → 0.30 변경 영향 · 4 branches · risk 62/100
분기:  ●0.25→0.30(current)  ○0.25→0.28(보수)  ○0.25→0.35(적극)  ○Mn도 동시  + 새 분기
┌── 위험도 62 (conic ring) ─ 영향 14위치+6Action+2Rule · 신뢰도 78% · HARD 1건 ──┐
│                                                          [시뮬] [draft PR] │
└──────────────────────────────────────────────────────────────────────┘

SIDE-BY-SIDE DIFF                                      [Java][Term][Rule][매뉴얼]
┌── As-is (현재) ──────────┐ ┌── To-be (제안, emerald) ──┐
│ ...                     │ │ ...                       │
│ - latest.C > 0.25       │ │ + latest.C > 0.30         │
│ ...                     │ │ ...                       │
└─────────────────────────┘ └─────────────────────────┘

CASCADE — 직접 + 간접 영향                              depth: ━●━━━ 2 hops
[term] term.scm.c_pct.range[1]                                  변경 시작점
↓ [rule] rule.scm.c_range                                       precondition refs
↓ [action] action.scm.주문_검증                                preconditions[0]
↓ [action] action.scm.화학성분_검증                            preconditions[2]
↓↓ [action] action.scm.출하_승인                              depends on (간접)
↓↓ [rule] rule.scm.quality_grade_a                            ⚠ HARD 위반 가능

[🌐 그래프 위에서 path 시각화]                  diff/risk/cascade/branch ✓
```

## 다음

- **Phase 3** (실제 데이터 연결): xyflow + dagre 자동 layout, Java repo import → CodeType 트리 + Action 자동 추출 + 매핑 큐 데이터 살아있게
- **Agent Phase**: A1 Plugin framework → A2 Simulation Agent → A3 ChangeSpec+PR Agent → A4 NL 영향 분석 Agent

C6 React (Phase 1 + 1.5 + 2) 완료 — Workbench UI 통합 완성.
