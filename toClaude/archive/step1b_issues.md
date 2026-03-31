# Step 1-B: Issues & Fixes

---

## Issue #1: Tiptap SSR Hydration Mismatch

**증상**: `Tiptap Error: SSR has been detected, please set immediatelyRender explicitly to false`

**원인**: Tiptap이 Next.js SSR 환경을 감지했으나 `immediatelyRender` 옵션이 설정되지 않아 hydration 불일치 발생

**수정 파일**: `src/components/editors/MarkdownEditor.tsx`

**수정 내용**: `useEditor`에 `immediatelyRender: false` 추가

**상태**: ✅ 해결

---

## Issue #2: 3-Pane 레이아웃 비율 깨짐 + 리사이즈 불가

**증상**: 중앙 Workspace만 크게 표시되고, 좌측/우측 영역 짤림. 리사이즈 안됨.

**원인**: `react-resizable-panels` v4의 `Group`/`Separator` API가 리사이즈 확장 불가 버그.

**최종 해결**: v4 → v2로 다운그레이드. `PanelGroup`/`PanelResizeHandle` API 사용.

**상태**: ✅ 해결

---

## Issue #3: 저장 실패 500 에러 (Toast 반복)

**증상**: `PUT /api/wiki/file/...` 500 에러 반복 발생

**원인**: Python 3.13 + ARM64에 `onnxruntime` 미지원 → ChromaDB 임베딩 실패 → indexer 에러

**수정**:
- `backend/application/wiki/wiki_indexer.py`: `index_file()`에 try/except 추가, 인덱싱 실패 시 warning만 남김
- `src/lib/api/wiki.ts`: `encodeURIComponent` 제거
- `src/components/editors/MarkdownEditor.tsx`: `loadedRef`로 초기 로드 시 자동 저장 방지

**상태**: ✅ 해결

---

## Issue #4: Heading 등 시각적 스타일 미적용 + 자동 저장 Toast 과다

**증상**: `## Heading` 입력해도 스타일 변화 없음. 자동 저장마다 Toast 표시.

**원인**:
1. Tiptap `prose` 클래스가 Tailwind Typography 플러그인 없이 동작 안 함
2. debounce 자동 저장에 Toast가 붙어있음

**수정**:
- `@tailwindcss/typography` 설치 + `globals.css`에 `@plugin "@tailwindcss/typography"` 추가
- `handleSave`에 `silent` 파라미터 추가: 자동 저장은 Toast 없이, Ctrl+S만 Toast 표시

**상태**: ✅ 해결

---
