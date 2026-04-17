# 데모 테스트 버그픽스 요약 (2026-03-26)

## 수정된 버그 (10건)

| # | 버그 | 원인 | 수정 파일 |
|---|------|------|-----------|
| 1 | 이미지 업로드 후 사이드바 assets 안 보임 | ALLOWED_EXTENSIONS에 이미지 확장자 누락 | `local_fs.py` |
| 2 | 엑셀 복사→붙여넣기 시 이미지로 삽입 | paste handler에서 이미지 체크가 테이블보다 먼저 | `pasteHandler.ts` |
| 3 | 표 헤더/세로선 안 보임 | Tiptap 테이블 CSS 없음 | `globals.css` |
| 4 | 표 병합/행열 추가 접근 어려움 | UI 없음 | `TableContextMenu.tsx` (신규) |
| 5 | 셀 선택 안 됨 | selectedCell CSS 없음 | `globals.css` |
| 6 | xlsx 수정 후 저장 안 됨 | stale closure + 브라우저 캐싱 | `SpreadsheetViewer.tsx` |
| 7 | Domain/Process 드롭다운 비어있음 | 기본 옵션 없음 + wiki 파일에 frontmatter 없음 | `MetadataTagBar.tsx`, wiki 파일 |
| 8 | 태그 입력 시 글자 쪼개짐 | 한국어 IME isComposing 미처리 | `TagInput.tsx` |
| 9 | Auto-Tag 추천 실패 | Gemini 무료 쿼터 초과 | `.env` → OpenAI로 전환 |
| 10 | /api/metadata/tags 500 에러 | 이미지 파일을 텍스트로 읽기 시도 | `local_fs.py` |
