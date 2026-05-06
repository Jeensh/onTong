# Step P3-4 Summary — Frontend Repo Import UI

**완료**: 2026-05-01
**범위**: TopBar 「Import」 버튼 + 모달 — path 입력 → SSE 진행률 → 자동 매핑 추천 persist → 큐 카드.

## 결과

사용자가 클릭 한 번으로:
1. 임의의 Java repo path 입력
2. 백엔드가 122 파일 → 123 CodeType / 956 method / 1018 CallSite 추출 (~150ms)
3. 자동으로 29 BusinessTerm + 36 Action + 34 TypeRealization 후보 생성 (`confirmed=False`)
4. 결과 카드로 "큐에 N건 적재됨" 확인

## 신규 / 수정

| 파일 | 종류 | 핵심 |
|---|---|---|
| `frontend/src/lib/api/ontology.ts` | 수정 | `startRepoImport` / `getRepoImportStatus` / `streamRepoImportProgress` (EventSource) / `recommendForRepo` + 3 DTO |
| `frontend/src/components/sections/modeling/RepoImportModal.tsx` | 신규 | shadcn Dialog. 4 phase (form → importing → recommending → done/error). SSE → polling 폴백 |
| `frontend/src/components/sections/modeling/TopBar.tsx` | 수정 | 「Import」 버튼 (FolderInput 아이콘) 추가 |

## 설계 포인트

- **SSE → polling 폴백**: 네트워크 중단/프록시 buffering 대비. `EventSource.onerror` 시 `getRepoImportStatus` 0.5s 폴링으로 자동 전환. 사용자 경험 보장.
- **자동 chained 호출**: import done → 즉시 recommend persist=true 호출. 사용자가 두 번 클릭할 필요 없음 (큐가 채워진 상태로 닫기).
- **idempotent**: 같은 repo_id 재import 시 백엔드의 `delete_repo` cascade + FK pragma 로 깨끗하게 교체. 모달 재오픈 가능.
- **모달 close cleanup**: 진행 중 닫으면 EventSource 즉시 close, form 200ms 후 리셋 — 다시 열면 깨끗한 상태.

## 검증

- `npx tsc --noEmit` exit 0.
- 모달이 호출하는 백엔드 시퀀스 curl 직접 확인: POST /import → SSE done → POST /recommend?persist=true → 29/36/34.

## 다음 (P3-5)

xyflow + dagre 자동 layout — Graph mode 가 실제 import 한 데이터 기반으로 렌더링.
- 노드: CodeType + BusinessTerm + Action
- 엣지: TypeRealization (PRIMARY/PARTIAL 색상 구분) + Inheritance + Composition + Realization
- 자동 레이아웃: dagre LR / TB
- subgraph navigation: 5000+ class 가정, 검색으로 중심 노드 선택 → BFS k-hop 만 표시
