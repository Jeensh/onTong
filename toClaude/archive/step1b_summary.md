# Step 1-B: Markdown Editor (Tiptap) — 작업 요약

> 완료일: 2026-03-25

---

## 추가 패키지

- `@tiptap/react`, `@tiptap/starter-kit`, `@tiptap/pm` — 코어
- `@tiptap/extension-table` (TableKit), `extension-table-row`, `extension-table-cell`, `extension-table-header`
- `@tiptap/extension-image`, `extension-task-list`, `extension-task-item`, `extension-placeholder`
- `@tiptap/extension-code-block-lowlight`, `lowlight` — 코드 하이라이팅
- `turndown`, `@types/turndown` — HTML → Markdown
- `marked` — Markdown → HTML

## 이슈 해결

- **Tiptap v3 export 변경**: `@tiptap/extension-table`에 default export 없음 → `{ TableKit }` named import 사용
- **TableKit.configure**: `resizable` 옵션이 TableKitOptions에 없음 → configure 없이 사용
- **ESLint warnings**: 미사용 변수/import 정리 (Decoration, DecorationSet, editorRect, node 파라미터)

---

## 1B-1. Tiptap 패키지 설치

- 13개 Tiptap 관련 패키지 + Markdown 변환 3개 패키지 설치

## 1B-2. MarkdownEditor 기본 컴포넌트

- `src/components/editors/MarkdownEditor.tsx` 생성
- Tiptap extensions: StarterKit, TableKit, Image, TaskList, TaskItem, Placeholder, SlashCommandExtension
- `prose prose-sm` 스타일 적용, 최소 높이 300px
- 로딩/에러 상태 처리

## 1B-3. WYSIWYG ↔ 소스 모드 토글

- 토글 버튼: 툴바 우측 FileCode/Eye 아이콘
- WYSIWYG → Source: `htmlToMarkdown(editor.getHTML())` → textarea
- Source → WYSIWYG: `markdownToHtml(sourceText)` → `editor.commands.setContent()`
- 양방향 전환 시 데이터 유실 없음

## 1B-4. 슬래시 명령어 (`/`)

- `src/lib/tiptap/slashCommand.ts` — ProseMirror Plugin 기반
- 10개 블록 타입: Heading 1/2/3, Bullet List, Ordered List, Task List, Table, Code Block, Blockquote, Horizontal Rule
- 빈 줄에서만 트리거 (줄 중간 `/`는 일반 문자)
- Escape로 메뉴 닫기
- `src/components/editors/SlashMenu.tsx` — 드롭다운 UI
  - 키보드 ArrowUp/Down 네비게이션
  - 타이핑 시 필터링 (`/h` → Heading만)
  - Enter로 선택, 마우스 클릭 지원

## 1B-5. 저장 기능

- **Ctrl+S 수동 저장**: `PUT /api/wiki/file/{path}` + Sonner Toast 피드백
- **Debounce 자동 저장**: 편집 후 3초 무입력 시 자동 PUT
- 저장 성공 → `setDirty(tabId, false)` → ● 표시 사라짐
- 저장 실패 → 에러 Toast

## 1B-6. 파일 열기

- 탭 활성화 시 `GET /api/wiki/file/{path}` → `markdownToHtml` → `editor.setContent()`
- `key={activeTab.id}`로 탭 전환 시 컴포넌트 재생성 (에디터 상태 격리)
- 로딩 중 "불러오는 중..." 표시

## 추가 작업

- **EditorToolbar** (`src/components/editors/EditorToolbar.tsx`): Undo/Redo, Bold/Italic/Strike/Code, H1/H2/H3, 리스트 3종, Quote/HR/Table, 소스 토글, 저장 버튼
- **Markdown 변환 유틸** (`src/lib/tiptap/markdown.ts`): Turndown + table/taskList 커스텀 규칙, marked
- **Wiki API 클라이언트** (`src/lib/api/wiki.ts`): fetchTree, fetchFile, saveFile
- **Sonner Toaster** → layout.tsx에 추가
- **WorkspacePanel**: FileRouter에 `tabId` prop 전달, `key={activeTab.id}` 추가
- **FileRouter**: markdown case에서 MarkdownEditor 실제 연결

---

## 검증 결과

| 항목 | 결과 |
|------|------|
| npm run build | ✅ 에러 없음 |
| Tiptap 패키지 설치 | ✅ 13개 |
| Markdown 변환 | ✅ turndown + marked |
| WYSIWYG ↔ 소스 | ✅ 양방향 토글 |
| 슬래시 명령어 | ✅ 10개 블록 타입, 필터링, Escape |
| 저장 (Ctrl+S + debounce) | ✅ dirty 표시 연동 |
| 파일 로드 | ✅ API → 에디터 (런타임 테스트는 백엔드 필요) |

---

## 생성/수정된 파일

```
frontend/src/
├── app/layout.tsx                            # Toaster 추가
├── components/
│   ├── editors/
│   │   ├── MarkdownEditor.tsx                # 신규 — 메인 에디터
│   │   ├── EditorToolbar.tsx                 # 신규 — 툴바
│   │   └── SlashMenu.tsx                     # 신규 — 슬래시 메뉴 UI
│   └── workspace/
│       ├── FileRouter.tsx                    # 수정 — MarkdownEditor 연결, tabId prop
│       └── WorkspacePanel.tsx                # 수정 — key + tabId 전달
├── lib/
│   ├── api/wiki.ts                           # 신규 — Wiki API 클라이언트
│   └── tiptap/
│       ├── markdown.ts                       # 신규 — MD ↔ HTML 변환
│       └── slashCommand.ts                   # 신규 — 슬래시 명령 extension
```
