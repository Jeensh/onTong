# Step 1-C: 클립보드 붙여넣기 — 작업 요약

---

## 작업 순서

### 1. 백엔드: 이미지 업로드 API (1C-5)
- **`backend/api/files.py`** 생성 (이전 세션)
  - `POST /api/files/upload/image`: 이미지 파일 업로드 → `wiki/assets/`에 UUID 파일명으로 저장
  - `GET /api/files/{path:path}`: wiki 디렉토리 내 바이너리 파일 서빙 (path traversal 방지)
  - 허용 타입: PNG, JPEG, GIF, WebP, SVG+XML
  - 최대 크기: 10MB
- **`backend/main.py`** 수정
  - `from backend.api import files as files_api` import 추가
  - `app.include_router(files_api.router)` 라우터 등록

### 2. HTML 테이블 변환 유틸 (1C-1)
- **`frontend/src/lib/clipboard/tableConverter.ts`** 생성
  - `containsHtmlTable(html)`: HTML 문자열에 `<table>` 포함 여부 검사
  - `htmlTableToTiptap(html)`: DOMParser로 파싱 → Tiptap 호환 `<table><tbody><tr><th/td>` 구조로 변환
  - 첫 번째 행은 `<th>` (헤더), 나머지는 `<td>`

### 3. 이미지 업로드 클라이언트 (1C-3)
- **`frontend/src/lib/clipboard/imagePaste.ts`** 생성
  - `uploadImage(file)`: FormData로 `POST /api/files/upload/image` 호출 → 상대 경로 반환

### 4. Paste Handler 확장 (1C-2 + 1C-4 통합)
- **`frontend/src/lib/tiptap/pasteHandler.ts`** 생성
  - ProseMirror Plugin으로 `handlePaste`와 `handleDrop` 모두 처리
  - **이미지 붙여넣기 (1C-3)**: clipboard에 image/* 아이템 감지 → `uploadImage()` → `insertContent({ type: "image" })`
  - **HTML 테이블 붙여넣기 (1C-2)**: `text/html`에 `<table>` 감지 → `htmlTableToTiptap()` → `insertContent()`
  - **이미지 드래그앤드롭 (1C-4)**: `handleDrop`에서 동일한 이미지 업로드 흐름

### 5. MarkdownEditor 통합
- **`frontend/src/components/editors/MarkdownEditor.tsx`** 수정
  - `PasteHandlerExtension` import 및 extensions 배열에 추가

---

## 산출물

| 파일 | 설명 |
|------|------|
| `backend/api/files.py` | 이미지 업로드 + 파일 서빙 API |
| `backend/main.py` | files 라우터 등록 추가 |
| `frontend/src/lib/clipboard/tableConverter.ts` | HTML 테이블 → Tiptap 변환 |
| `frontend/src/lib/clipboard/imagePaste.ts` | 이미지 업로드 클라이언트 |
| `frontend/src/lib/tiptap/pasteHandler.ts` | Paste/Drop 핸들러 확장 |
| `frontend/src/components/editors/MarkdownEditor.tsx` | PasteHandler 통합 |

---

## 검증

- TypeScript 타입 체크 통과 (`npx tsc --noEmit`)
