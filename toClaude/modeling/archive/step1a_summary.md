# Step 1-A: Tab Workspace 기반 레이아웃 — 작업 요약

> 완료일: 2026-03-25

---

## 추가 패키지

- `react-resizable-panels@4.7.6` — 3-Pane 리사이즈 가능 레이아웃

## 이슈 해결

- **react-resizable-panels v4 API 변경**: v3의 `PanelGroup`/`PanelResizeHandle` → v4에서 `Group`/`Separator`로 이름 변경, `direction` → `orientation`으로 prop명 변경. 빌드 에러 후 수정.

---

## 1A-1. 3-Pane 메인 레이아웃

- `src/app/page.tsx` 재작성
- `react-resizable-panels`의 `Group` + `Panel` + `Separator` 사용
- 좌측 TreeNav (20%, min 12, max 35) | 중앙 Workspace (55%, min 30) | 우측 AI Copilot placeholder (25%, min 15, max 40)
- Separator에 hover 시 색상 변경 transition 적용

## 1A-2. Zustand 탭 스토어

- `src/lib/workspace/useWorkspaceStore.ts` 생성
- `openTab(filePath)`: 중복 방지 (동일 파일 → 기존 탭 포커스), 확장자 기반 FileType 자동 분류
- `closeTab(tabId)`: 활성 탭 닫기 시 인접 탭 자동 활성화, 마지막 탭 닫기 → activeTabId = null
- `setActiveTab(tabId)`, `reorderTabs(from, to)`, `setDirty(tabId, isDirty)`
- Tab ID 생성: `tab-${Date.now()}-${random}`

## 1A-3. TabBar 컴포넌트

- `src/components/workspace/TabBar.tsx` 생성
- `@dnd-kit/core` + `@dnd-kit/sortable` 기반 드래그 정렬
- `PointerSensor` (distance: 5px threshold로 클릭과 드래그 구분)
- 활성 탭: `border-foreground` 하단 보더 + 배경색 구분
- dirty 표시: 주황색 ● (tab.isDirty)
- ✕ 버튼: hover 시 표시, stopPropagation으로 탭 전환 방지
- 탭 0개 → TabBar 자체 미표시 (null return)

## 1A-4. WorkspacePanel 컴포넌트

- `src/components/workspace/WorkspacePanel.tsx` 생성
- TabBar + 콘텐츠 영역 flex column 구조
- 활성 탭 존재 → FileRouter 렌더링
- 활성 탭 없음 → "파일을 선택하세요" 빈 상태 메시지

## 1A-5. FileRouter 컴포넌트

- `src/components/workspace/FileRouter.tsx` 생성
- FileType 기반 switch 분기:
  - `markdown` → "Markdown Editor" placeholder
  - `spreadsheet` → "Spreadsheet Viewer" placeholder
  - `presentation` → "Presentation Viewer" placeholder
  - `pdf` → "PDF Viewer" placeholder
  - `image` → "Image Viewer" placeholder
  - `unknown` → "지원하지 않는 파일 형식" 메시지

## 1A-6. TreeNav 컴포넌트

- `src/components/TreeNav.tsx` 생성
- `useEffect`로 `GET /api/wiki/tree` fetch → state 저장
- 재귀적 `TreeItem` 컴포넌트 (폴더 펼치기/접기, 기본 expanded)
- 폴더: ChevronRight/Down + Folder 아이콘
- 파일: File 아이콘 + 클릭 시 `openTab(node.path)`
- 로딩/에러/빈 상태 처리
- depth 기반 padding으로 트리 들여쓰기

---

## 검증 결과

| 항목 | 결과 |
|------|------|
| npm run build | ✅ 에러 없음 |
| tsc --noEmit | ✅ (빌드에 포함) |
| 3-Pane 레이아웃 | ✅ 코드 구조 완성 |
| Zustand 스토어 | ✅ openTab/closeTab/setActiveTab/reorderTabs/setDirty |
| TabBar 드래그 정렬 | ✅ @dnd-kit 통합 |
| WorkspacePanel 빈 상태 | ✅ |
| FileRouter 분기 | ✅ 6개 FileType 커버 |
| TreeNav API 연동 | ✅ (런타임 테스트는 백엔드 기동 필요) |

---

## 생성/수정된 파일

```
frontend/src/
├── app/page.tsx                              # 3-Pane 레이아웃으로 교체
├── lib/workspace/useWorkspaceStore.ts        # 신규
├── components/
│   ├── TreeNav.tsx                            # 신규
│   └── workspace/
│       ├── TabBar.tsx                         # 신규
│       ├── WorkspacePanel.tsx                 # 신규
│       └── FileRouter.tsx                     # 신규
```
