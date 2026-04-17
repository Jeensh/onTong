# Step 1-D: Multi-Format 뷰어 — 작업 요약

---

## 범위

- **P1 구현**: Excel(읽기+수정+저장), 이미지(줌/패닝)
- **P1.5 보류**: PPT, PDF 뷰어 (placeholder 유지)

## 작업 순서

### 1. 백엔드: 바이너리 파일 저장 API (1D-2)
- **`backend/api/files.py`** 수정
  - `PUT /api/files/{path:path}`: UploadFile로 바이너리 저장, `.md` 거부, path traversal 방지
  - `GET /api/files/{path:path}`: 이미 구현되어 있음 (1C-5에서 완료, 1D-1 겸용)

### 2. SpreadsheetViewer (1D-3 + 1D-4)
- **`frontend/src/components/editors/SpreadsheetViewer.tsx`** 생성
  - SheetJS(`xlsx`)로 `.xlsx` 파일 파싱
  - 멀티시트 탭 지원
  - 셀 더블클릭 → 인라인 편집 (문자열/숫자 자동 타입 감지)
  - Ctrl+S 또는 저장 버튼 → `PUT /api/files/{path}` (FormData로 xlsx 전송)
  - 행번호 + 열 헤더 (A, B, C...) 표시
  - sticky 헤더/행번호

### 3. ImageViewer (1D-7)
- **`frontend/src/components/editors/ImageViewer.tsx`** 생성
  - `GET /api/files/{path}` → `<img>` 렌더링
  - 마우스 휠 줌 (0.1x ~ 5x)
  - 마우스 드래그 패닝
  - 툴바: +/− 버튼, 퍼센트 표시, 1:1 초기화

### 4. FileRouter 연결 (1D-8)
- **`frontend/src/components/workspace/FileRouter.tsx`** 수정
  - `spreadsheet` → `SpreadsheetViewer`, `image` → `ImageViewer` 연결
  - `presentation`, `pdf` → Phase 1.5 placeholder 유지

## 산출물

| 파일 | 설명 |
|------|------|
| `backend/api/files.py` | PUT 엔드포인트 추가 |
| `frontend/src/components/editors/SpreadsheetViewer.tsx` | Excel 뷰어/에디터 |
| `frontend/src/components/editors/ImageViewer.tsx` | 이미지 뷰어 (줌/패닝) |
| `frontend/src/components/workspace/FileRouter.tsx` | 실제 뷰어 연결 |

## 검증

- TypeScript 타입 체크 통과
- npm 패키지 설치: `xlsx` (SheetJS)
