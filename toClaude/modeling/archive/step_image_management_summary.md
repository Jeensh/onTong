# Image Management System — 구현 요약

**날짜**: 2026-04-17
**브랜치**: `main`
**커밋**: `dd5be50`..`f2f2826` (5 commits)
**테스트**: 60 pass (28 registry + 32 analysis), TS clean
**설계**: `docs/superpowers/specs/2026-04-17-image-management-design.md`
**플랜**: `docs/superpowers/plans/2026-04-17-image-management.md`

---

## 구현 범위 (11 Tasks)

### 백엔드 (Tasks 1-7)

| Task | 내용 | 파일 |
|------|------|------|
| 1 | ImageRegistry (hash index + ref counting + scan) | `image_registry.py` |
| 2 | Source field on ImageAnalysis sidecar | `models.py` |
| 3 | SHA-256 hash dedup upload | `files.py` |
| 4 | Registry init + tree_change event handler | `main.py` |
| 5 | Ref tracking on document save (diff old/new) | `wiki_service.py` |
| 6 | Admin API (stats, list, delete, bulk-delete) | `files.py` |
| 7 | OCR inheritance endpoint | `files.py` |

### 프론트엔드 (Tasks 8-11)

| Task | 내용 | 파일 |
|------|------|------|
| 8 | fabric.js + ImageCopyExtension | `pasteHandler.ts`, `MarkdownEditor.tsx` |
| 9 | ImageViewerModal (fullscreen + annotation) | `ImageViewerModal.tsx` (NEW) |
| 10 | ImageManagementPage (admin gallery) | `ImageManagementPage.tsx` (NEW) |
| 11 | Routing + types + admin gate | `workspace.ts`, store, router, TreeNav |

---

## 주요 설계 결정

- **인메모리 레지스트리**: 시작 시 assets/ 디렉토리 스캔, 런타임은 이벤트 기반 업데이트. 100K+ 문서에서도 메모리 오버헤드 최소화 (이미지 수는 문서 수보다 훨씬 적음)
- **12자 SHA prefix 파일명**: `sha256[:12] + ext` — 충돌 확률 극히 낮으면서 URL 가독성 유지
- **fabric.js dynamic import**: 번들 크기 최소화, 편집 모드 진입 시에만 로드
- **Intersection Observer**: 갤러리 썸네일 lazy loading (rootMargin 200px)
- **서버사이드 페이지네이션**: `list_entries(page, size, filter, search)` — 100K+ 이미지 대비

## 미검증 항목 (다음 세션)

- 브라우저 UI 검증: 이미지 클릭→뷰어, 어노테이션 편집→저장, 갤러리 페이지
- fabric.js 캔버스 크기 반응형 동작
- OCR 상속 플로우 end-to-end
