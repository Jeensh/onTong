# Step C6 React Phase 1 — Modeling Workbench 구현 시작

**완료**: 2026-05-02
**기반**: 사용자 4차 답변 (P13=done / P14=critical / P15=phase1 / P16=skip)
**기준 prototype**: V6/V7 인터랙티브 HTML

## 산출물 요약

| 항목 | 수치 |
|---|---|
| 새 React 컴포넌트 | 9 (.tsx) + 1 store (.ts) + 1 API client (.ts) |
| 총 LOC (frontend modeling + ontology API) | 1,815 |
| 누적 backend tests | **121/121 PASSED** (1.61s) |
| frontend tsc | ✓ 에러 없음 |
| backend startup | ✓ 16 ontology endpoints 작동 |

## 디렉토리

```
frontend/src/lib/api/
└── ontology.ts                  # REST client (16 메서드, OntologyQueryClient 정합)

frontend/src/components/sections/
├── ModelingSection.tsx          # 진입점
└── modeling/
    ├── store.ts                 # zustand store (tabs, mode, direction, selection)
    ├── WorkbenchShell.tsx       # 3-pane grid layout + graph mode 토글
    ├── TopBar.tsx               # brand + repo + ⌘K + 그래프/시뮬 버튼
    ├── TabBar.tsx               # 여러 작업 동시 (V4 차용)
    ├── LeftPanel.tsx            # 5 탭 (Map landing / Code / Domain / Action / Queue)
    ├── MainPanel.tsx            # Forward+Backward 토글 + Detail/Split mode
    ├── RightPanel.tsx           # 4 탭 (코드/매뉴얼/호출/영향) + resize 드래그
    ├── GraphMode.tsx            # Top-down L1~L4 (full-screen takeover)
    └── CmdKPalette.tsx          # cmdk 라이브러리 + 통합 검색 + 명령
```

## Phase 1 의 범위 (P15=phase1 정합)

| 영역 | 상태 |
|---|---|
| **Forward 매핑** | ✓ Detail / Split mode |
| **Domain Map landing** | ✓ 좌측 첫 탭, 4 도메인 카드 |
| **5 탭 (Code/Domain/Action/Queue)** | ✓ 모두 작동, API 호출 연결 |
| **Mode 토글** | ✓ Detail / ↕ Split / 🌐 Graph |
| **Graph L1~L4** | ✓ Top-down (mock layout, breadcrumb, level slider, 키보드 1-4 / ↑↓) |
| **상단 탭바** | ✓ 여러 작업 동시 |
| **우측 4탭** | ✓ resize 드래그 작동, Split mode 버튼 |
| **⌘K palette** | ✓ cmdk 라이브러리, 검색 + 명령 |
| **Status bar** | ✓ verification 진척 (live API), Forward/Backward 표시 |
| Backward placeholder | ✓ banner only (Phase 2 강화 예정) |

## Phase 1.5 / 2 (다음)

P14=critical 이라 빠르게 와야 할 것:
- **L5 anchor micro-graph** (★ 우리 차별)

Phase 2:
- Backward 강화 4종 (diff_view / risk_score / cascade / rollback)
- Lens 시스템 (verification / domain / confidence / simulation)
- Path-trace 양방향
- Search Around (노드 우클릭)
- Cross-domain edge 강조
- Filter sidebar
- xyflow 또는 cytoscape 통합 (실제 줌/팬/드래그)

## 기술 스택

- **Next.js 15** + **React 19** (Turbopack)
- **Tailwind** + **shadcn-ui** (Button/Command/Dialog 등)
- **zustand** (store)
- **lucide-react** (icons)
- **cmdk** (⌘K palette, shadcn Command)
- 그래프 라이브러리 후보 (Phase 1.5+): **@xyflow/react** + **@dagrejs/dagre** 또는 **react-force-graph-2d** + **d3-force** (이미 deps 에 있음)

## API 연결

`frontend/src/lib/api/ontology.ts` — 16 메서드 (backend `OntologyQueryClient` Protocol 1:1):
- Term: list / get / effective_parts
- Code: list / get / call sites
- Action: list / get / realizations_for_input / resolve_path
- Anchor: for_action / for_method
- Queue: unmapped / ambiguous_call_sites / verification_progress
- Search: FTS-like

`backend.modeling.persistence.database.bootstrap_database()` 수정 — archive 된 `models.py` 대신 main.py 가 각 layer ORM 직접 import.

## 검증

| 검사 | 결과 |
|---|---|
| `npx tsc --noEmit` | ✓ 에러 없음 |
| 누적 `pytest tests/{code,domain,mapping}_layer tests/api/` | **121/121 PASSED** |
| backend startup | ✓ 16 ontology routes |
| backend `/api/ontology/queue/verification-progress/scm` | `{"repo_id":"scm","total_actions":0,"by_level":{}}` (빈 상태 정상) |
| frontend dev server | ✓ port 3000 |
| browse 시연 (Workbench 화면) | ✓ 좌 5탭 / 중앙 Mode 토글 + 안내 / 우 4탭 / status bar 표시 (스크린샷 c6r_v2.png) |

## 시연 (browse screenshot)

```
TopBar:    onTong  scm·main  [⌘K]  [🌐 그래프]  [▶ 시뮬]
TabBar:    📋 주문_검증 매핑 (active, unsaved ●) | +
Left:      Map | Code | Domain | Action | 큐
           ┌─ SCM (공급망 관리) — 0 actions · 0 terms
           ├─ Quality (품질 관리)
           ├─ Production (생산 관리)
           └─ Logistics (물류)
Main:      [scm › action.scm.order_validate]
           [🔍 Forward | 🔧 Backward] [Detail | ↕ Split | 🌐 Graph]
           "Action 선택 또는 backend 데이터 없음" (정상)
Right:     [코드 | 매뉴얼 | 호출지점 | 영향]  [↕ Split mode 로]  [↔] [⤢]
Status:    U0 D0 SL0 BA0 SV0 PR0 · 0 actions · BODY_ANCHORED+ 0 (0%) · 🔍 Forward 모드
```

## 다음 작업

**Phase 1.5 (P14=critical)**: L5 anchor micro-graph 구현 (R-우리 차별).

또는 **Phase 2**: Backward 강화 / Lens / Path-trace.

Phase 1 완료 — 사용자 시연 후 다음 phase 결정.
