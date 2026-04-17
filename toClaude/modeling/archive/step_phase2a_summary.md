# Phase 2a: Source Viewer + Mapping Workbench — 완료 요약

## 완료 항목
- **Source API** (`source_api.py`): 파일 트리, 파일 내용, 엔티티 위치 조회 3개 엔드포인트
- **SourceViewer** (`SourceViewer.tsx`): 파일 트리 + Monaco 읽기 전용 에디터
- **MappingCanvas** (`MappingCanvas.tsx`): React Flow 도메인 그래프 + 엔티티 패널 + 드래그-드롭 매핑
- **MappingWorkbench** (`MappingWorkbench.tsx`): 분할 패널 (55%/45%) + 양방향 연동
- **ModelingSection 통합**: "매핑 워크벤치" 사이드바 탭 추가

## 검증 결과
- Backend: 14/14 tests pass (source API)
- Frontend: TypeScript clean (zero errors)
- 보안: path traversal, symlink, recursion depth, binary file 방어

## 커밋 이력
1. `7736e20` fix: harden source API (path traversal + symlinks)
2. `ec8cb4a` feat: source file content API
3. `b425708` feat: React Flow, Monaco deps + API client
4. `041aa0b` feat: SourceViewer component
5. `83368bb` feat: MappingCanvas component
6. `fd8f065` fix: stale closure bug in SourceViewer
7. `101293e` feat: MappingWorkbench split panel
8. `f9fc721` feat: ModelingSection integration
9. `d9922d4` feat: entity location lookup API
10. `9f69ee2` feat: entity-to-file navigation wiring

## 주요 기술 결정
- Monaco Editor read-only 먼저 (에디터 기능은 추후)
- React Flow v12 + dagre 자동 레이아웃
- Ref 패턴으로 stale closure 방지 (handleEditorMount)
- `[data-id]` DOM 속성 기반 drop target 감지

## 향후 작업
- INFRA-1: Docker Sandbox (독립 기능)
- INFRA-2: Redis 파일 트리 캐싱 (대규모 repo 대응)
- INFRA-3: 매핑 이력 추적 (Audit Trail)
- INFRA-4: WebSocket 실시간 동기화
