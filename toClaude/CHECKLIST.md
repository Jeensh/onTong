# onTong — 검증 체크리스트 (Testing Manual)

> **역할**: 테스트 수행 절차서. 상태 추적(`[x]`)은 `TODO.md`에서만 관리.
> 기반 문서: `TODO.md`, `3_enhanced_workspace_plan.md`
> 최종 갱신: 2026-03-26

---

## Step 0: 프론트엔드 환경 세팅

### 0-1. Next.js 프로젝트 초기화

```bash
cd /Users/donghae/workspace/ai/onTong
ls frontend/package.json
```

- `frontend/package.json`이 존재한다
- `dependencies`에 `next`, `react`, `react-dom`이 있다
- `devDependencies`에 `typescript`, `@types/react`가 있다
- Tailwind CSS가 동작한다 (v4: CSS-only config — `globals.css`에 `@import "tailwindcss"` 존재, `tailwind.config.ts` 불필요)
- `npm run build` 에러 없이 완료된다
- `npm run dev` 실행 후 `curl -s -o /dev/null -w "%{http_code}" http://localhost:3000` → `200`

### 0-2. shadcn/ui 설치

```bash
ls frontend/src/components/ui/
```

- `components.json`이 존재한다
- 아래 파일이 각각 존재한다:
  `button.tsx`, `badge.tsx`, `command.tsx`, `select.tsx`,
  `dropdown-menu.tsx`, `popover.tsx`, `dialog.tsx`, `sonner.tsx`

### 0-3. Zustand + dnd-kit 설치

```bash
cd frontend && npm ls zustand @dnd-kit/core
```

- 위 명령이 에러 없이 버전을 출력한다 (zustand@5.0.12, @dnd-kit/core@6.3.1)

### 0-4. API 프록시 설정

```bash
# 백엔드 실행 상태에서
curl -s http://localhost:3000/api/wiki/tree | python3 -m json.tool | head -5
```

- `next.config.ts`에 `/api/:path*` → `http://localhost:8001/api/:path*` rewrite가 있다
- 위 curl 명령이 유효한 JSON 배열을 반환한다 (백엔드 기동 후 테스트)

### 0-5. TypeScript 타입 정의

```bash
cd frontend && npx tsc --noEmit
```

- 위 명령이 에러 0개로 완료된다
- 아래 타입이 `src/types/` 하위에 정의되어 있다:
  - `FileType` = `"markdown" | "spreadsheet" | "presentation" | "pdf" | "image" | "unknown"`
  - `Tab` = `{ id, filePath, fileType, title, isDirty }`
  - `WikiFile` = `{ path, title, content, raw_content, metadata, links }`
  - `WikiTreeNode` = `{ name, path, is_dir, children }`
  - `DocumentMetadata` = `{ domain, process, error_codes, tags, author, created }`
  - SSE 이벤트: `ContentDelta`, `SourcesEvent`, `ApprovalRequestEvent`, `ErrorEvent`, `DoneEvent`

---

## Step 1-A: Tab Workspace 기반 레이아웃

### 1A-1. 3-Pane 레이아웃

- 화면이 3개 영역(좌/중앙/우)으로 분할된다
- 패널 경계 드래그로 너비 조절이 된다
- 브라우저 너비 1024px까지 줄여도 레이아웃이 깨지지 않는다

### 1A-2. Zustand 탭 스토어

```
브라우저 DevTools Console에서:
> store = window.__ZUSTAND_STORE__ (또는 React DevTools)
```

- `openTab("getting-started.md")` → `tabs.length === 1`
- 동일 파일로 `openTab` 재호출 → `tabs.length === 1` (중복 없음)
- 다른 파일로 `openTab` → `tabs.length === 2`
- `closeTab(tabs[0].id)` → `tabs.length === 1`
- 마지막 탭 닫기 → `activeTabId === null`
- 활성 탭 닫기 → 인접 탭이 활성화됨

### 1A-3. TabBar 컴포넌트

- 열린 탭이 수평 나열된다
- 활성 탭이 시각적으로 구분된다 (배경색 또는 하단 보더)
- ✕ 버튼 클릭 → 해당 탭 닫힘
- 탭 드래그로 순서 변경 가능 (드롭 후 순서 유지)

### 1A-4. WorkspacePanel

- 탭 0개 → "파일을 선택하세요" 등 빈 상태 메시지 표시
- 탭 활성화 → 해당 콘텐츠 영역 렌더링

### 1A-5. FileRouter

- `.md` 파일 → MarkdownEditor (또는 placeholder 텍스트 "Markdown Editor")
- `.xlsx` → "Spreadsheet Viewer" placeholder
- `.pptx` → "Presentation Viewer" placeholder
- `.pdf` → "PDF Viewer" placeholder
- `.png`/`.jpg` → "Image Viewer" placeholder
- `.unknown` → "지원하지 않는 파일 형식" 메시지

### 1A-6. TreeNav

```bash
# 사전: 백엔드 + ChromaDB 실행 중
```

- 마운트 시 네트워크 탭에 `GET /api/wiki/tree` 요청이 보인다
- wiki 디렉토리 구조가 트리로 표시된다
- 폴더 클릭 → 펼치기/접기
- 파일 클릭 → Workspace에 새 탭 열림
- 이미 열린 파일 클릭 → 기존 탭 포커스

### Step 1-A 종합 시나리오 (순서대로 수행)

1. 앱 실행 → TreeNav에 wiki 파일 트리 표시
2. `getting-started.md` 클릭 → 탭 1개 생성
3. `order-processing-rules.md` 클릭 → 탭 2개
4. 첫 번째 탭 클릭 → 콘텐츠 전환
5. 두 번째 탭 ✕ → 탭 1개로 줄어듦
6. 마지막 탭 ✕ → 빈 상태

---

## Step 1-B: Markdown Editor (Tiptap)

### 1B-1. 패키지 설치

```bash
cd frontend && npm ls @tiptap/react @tiptap/starter-kit @tiptap/extension-table @tiptap/extension-image
```

- 위 명령이 4개 패키지 모두 버전을 출력한다

### 1B-2. 기본 에디터

- 에디터 영역이 렌더링되고 텍스트 입력 가능
- `Ctrl+B` → 굵은 글씨 토글
- `# ` 입력 → Heading 1 스타일 적용
- 테이블 삽입 UI가 존재하고 삽입 가능

### 1B-3. WYSIWYG ↔ 소스 모드

- 토글 버튼 또는 단축키가 존재한다
- WYSIWYG → 소스: 원본 Markdown 텍스트가 표시된다
- 소스에서 텍스트 수정 가능
- 소스 → WYSIWYG: 수정 내용이 WYSIWYG에 반영된다
- 전환 시 데이터 유실 없음 (소스 모드에서 `**bold**` 추가 → WYSIWYG에서 굵은 글씨)

### 1B-4. 슬래시 명령어

- 빈 줄에서 `/` 입력 → 드롭다운 메뉴 표시
- 메뉴에 최소 5가지 블록 타입 존재 (Heading, List, Table, Code block, Quote 등)
- 항목 선택 → 해당 블록 삽입
- `/h` 타이핑 → 필터링 (Heading 항목만 표시)
- `Escape` → 메뉴 닫힘
- 줄 중간에서 `/` 입력 → 메뉴 미표시 (일반 `/` 문자로 입력)

### 1B-5. 저장 기능

```bash
# 저장 전
md5 wiki/getting-started.md
# 에디터에서 텍스트 추가 → Ctrl+S
# 저장 후
md5 wiki/getting-started.md
```

- `Ctrl+S` → 네트워크 탭에 `PUT /api/wiki/file/{path}` 요청 1회 전송
- 저장 성공 → 탭의 ● dirty 표시 사라짐
- 저장 성공 → Sonner Toast 등 시각적 피드백
- 연속 편집 중 PUT 요청이 발생하지 않음 (debounce)
- 편집 멈춘 후 PUT 요청 1회만 발생 (중복 요청 없음)
- 두 파일의 `md5` 해시가 다르다 (파일이 실제로 변경됨)

### 1B-6. 파일 열기

- 탭 활성화 시 네트워크에 `GET /api/wiki/file/{path}` 요청 1회
- 응답 `content`가 에디터에 표시된다
- 로딩 중 스피너 또는 스켈레톤이 보인다

### Step 1-B 종합 시나리오

1. TreeNav에서 `getting-started.md` 클릭 → 에디터에 콘텐츠 로드
2. 본문에 "테스트 텍스트" 추가 → ● 표시 나타남
3. `Ctrl+S` → 저장 → ● 사라짐
4. 브라우저 새로고침 → 같은 파일 열기 → "테스트 텍스트" 유지
5. 소스 모드 토글 → Markdown 확인 → 다시 토글
6. 빈 줄에서 `/` → 메뉴 → Heading 2 선택 → 삽입

---

## Step 1-C: 클립보드 붙여넣기

### 1C-5. 백엔드 이미지 업로드 API (⚠️ 먼저 구현)

```bash
# 테스트 이미지 생성
convert -size 100x100 xc:red /tmp/test.png 2>/dev/null || \
  python3 -c "from PIL import Image; Image.new('RGB',(100,100),'red').save('/tmp/test.png')" 2>/dev/null || \
  echo "테스트 이미지를 수동으로 /tmp/test.png에 배치"

# API 호출
curl -s -X POST http://localhost:8001/api/files/upload/image \
  -F "file=@/tmp/test.png" | python3 -m json.tool
```

- 200 응답 + JSON 반환: `{"path": "assets/...", "markdown": "![](assets/...)"}`
- `wiki/assets/` 디렉토리에 파일이 실제 저장됨
- 파일명에 타임스탬프 또는 랜덤 문자 포함 (충돌 방지)
- 이미지가 아닌 파일 (`.txt`) 업로드 → 400 에러
- `main.py`에 files 라우터가 등록되어 `GET /openapi.json`에 경로 노출됨

### 1C-1. HTML 테이블 → Table 변환

```typescript
// 단위 테스트 또는 브라우저 콘솔
const html = '<table><tr><td>이름</td><td>수량</td></tr><tr><td>볼트</td><td>100</td></tr></table>';
const result = htmlTableToMarkdown(html);
console.assert(result.includes('| 이름 | 수량 |'));
console.assert(result.includes('| 볼트 | 100'));
```

- 2x2 HTML 테이블 → 올바른 Markdown 테이블 문자열
- 5x3 이상 테이블도 정상 변환
- 셀 내 `|` 문자가 이스케이프 처리됨
- `<table>` 없는 HTML → `null` 반환

### 1C-2. 테이블 붙여넣기 핸들러

```
[수동 테스트]
1. Excel/Google Sheets에서 3x3 범위 → Ctrl+C
2. Tiptap 에디터 → Ctrl+V
```

- 붙여넣기 결과가 테이블로 렌더링된다 (행/열 구분)
- 소스 모드 전환 시 `|` 구문의 Markdown 테이블이 보인다
- 일반 텍스트 Ctrl+V → 기존대로 텍스트 삽입 (regression 없음)

### 1C-3. 이미지 붙여넣기

```
[수동 테스트]
1. 스크린샷 캡처 도구로 화면 캡처 (클립보드에 이미지)
2. Tiptap 에디터 → Ctrl+V
```

- 네트워크에 `POST /api/files/upload/image` 요청이 보인다
- 업로드 중 에디터에 로딩 placeholder가 표시된다
- 완료 후 이미지가 에디터에 표시된다
- 소스 모드에서 `![](assets/...)` 구문이 보인다

### 1C-4. 이미지 드래그 앤 드롭

```
[수동 테스트] 데스크탑에서 .png 파일을 에디터 영역으로 드래그
```

- 드래그 오버 시 에디터에 시각적 하이라이트
- 드롭 → 이미지 업로드 → 에디터 삽입
- `.txt` 파일 드롭 → 무시 (에러 없음)

---

## Step 1-D: Multi-Format 뷰어

### 1D-1. 백엔드 바이너리 GET (⚠️ 먼저 구현)

```bash
# 사전: wiki/ 에 test.xlsx 배치
curl -s -o /tmp/downloaded.xlsx http://localhost:8001/api/files/test.xlsx
file /tmp/downloaded.xlsx
```

- `file` 명령 출력에 "Microsoft Excel" 또는 "Zip archive"가 포함됨
- 응답 `Content-Type`이 적절함 (MIME 타입)
- 존재하지 않는 파일 → `404` 반환
- path traversal (`../../etc/passwd`) → `400` 또는 `403`

### 1D-2. 백엔드 바이너리 PUT (⚠️ 먼저 구현)

```bash
curl -s -X PUT http://localhost:8001/api/files/test.xlsx \
  -F "file=@/tmp/modified.xlsx" -w "%{http_code}"
```

- 200 응답
- 다시 GET → 수정된 파일 반환
- `.md` 파일 저장 시도 → 400 에러 (MD는 `/api/wiki/*` 사용)

### 1D-3 / 1D-4. SpreadsheetViewer

```
[사전 준비] wiki/에 테스트 .xlsx 파일 배치 (3열 x 10행 정도)
[수동 테스트] TreeNav에서 해당 파일 클릭
```

- 스프레드시트 UI가 렌더링된다 (셀 그리드 표시)
- 셀 데이터가 원본과 일치한다
- 셀 클릭 → 값 편집 가능
- 저장 버튼 클릭 → `PUT /api/files/{path}` 호출
- 탭 닫기 → 다시 열기 → 수정 내용 유지

### 1D-5. PresentationViewer (P1.5)

- 슬라이드가 렌더링된다
- 이전/다음 네비게이션 가능
- 슬라이드 번호 표시

### 1D-6. PdfViewer (P1.5)

- PDF 첫 페이지가 렌더링된다
- 페이지 네비게이션 가능 (이전/다음, 직접 입력)
- 줌 인/아웃 가능
- 50페이지 이상 PDF → 페이지네이션 UI (전체 렌더가 아닌)

### 1D-7. ImageViewer

- 이미지가 표시된다
- 마우스 휠 또는 버튼으로 줌 가능
- 줌 상태에서 드래그로 패닝 가능

### 1D-8. FileRouter 연결

- 각 확장자가 올바른 뷰어로 연결됨 (placeholder 텍스트가 남아있지 않음)

---

## Step 1-E: Metadata Tagging Pipeline

### 1E-B1. schemas.py 수정

```python
cd /Users/donghae/workspace/ai/onTong
python3 -c "
from backend.core.schemas import WikiFile, DocumentMetadata, MetadataSuggestion

# DocumentMetadata 생성
meta = DocumentMetadata(domain='SCM', tags=['cache', 'ops'], error_codes=['DG320'])
assert meta.domain == 'SCM'
assert meta.error_codes == ['DG320']

# WikiFile에 metadata 필드
wf = WikiFile(path='t.md', title='T', content='body', raw_content='---\n---\nbody', metadata=meta, links=[])
assert wf.metadata.domain == 'SCM'

# tags property 호환성
assert wf.tags == ['cache', 'ops']

# MetadataSuggestion
ms = MetadataSuggestion(domain='SCM', tags=['test'], confidence=0.9, reasoning='test')
assert ms.confidence == 0.9

print('1E-B1: ALL PASS')
"
```

- 위 스크립트가 `ALL PASS` 출력

### 1E-B2. local_fs.py Frontmatter 파싱

```python
python3 -c "
import asyncio
from pathlib import Path
from backend.infrastructure.storage.local_fs import LocalFSAdapter

adapter = LocalFSAdapter(Path('wiki'))

async def test():
    # frontmatter가 있는 파일
    wf = await adapter.read('kv-cache-troubleshoot.md')
    print(f'metadata.tags: {wf.metadata.tags}')
    print(f'metadata.domain: {wf.metadata.domain}')
    print(f'content starts with ---: {wf.content.startswith(\"---\")}')
    print(f'raw_content starts with ---: {wf.raw_content.startswith(\"---\")}')
    assert not wf.content.startswith('---'), 'content should not contain frontmatter'
    assert wf.raw_content.startswith('---'), 'raw_content should contain frontmatter'
    print('1E-B2: ALL PASS')

asyncio.run(test())
"
```

- frontmatter 파일: `metadata`에 값 채워짐, `content`에 frontmatter 없음
- frontmatter 없는 파일: `#tag` 폴백 동작
- 잘못된 YAML: 에러 없이 빈 metadata + 전체 content
- 바이너리 파일: `[Binary file: .xlsx]` 유지

### 1E-B3. wiki_indexer.py 메타데이터 확장

```python
# ChromaDB 실행 상태에서
python3 -c "
import chromadb
c = chromadb.HttpClient('localhost', 8000)
col = c.get_collection('ontong_wiki')
r = col.get(limit=1, include=['metadatas'])
meta = r['metadatas'][0]
print(meta)
assert 'domain' in meta, 'domain 필드 없음'
assert 'tags' in meta, 'tags 필드 없음'
assert meta.get('tags','').startswith('|') or meta.get('tags') == '', 'tags 파이프 형식 아님'
print('1E-B3: ALL PASS')
"
```

- `file_path`, `heading` 유지 + `domain`, `process`, `error_codes`, `tags`, `author` 추가
- `tags` 값이 `|tag1|tag2|` 파이프 구분자 형식
- 빈 필드는 `""` (None이 아님)

### 1E-B4. chroma.py query_with_filter

```python
python3 -c "
from backend.infrastructure.vectordb.chroma import chroma
chroma.connect()

# 필터 없이 (기존 동작)
r1 = chroma.query_with_filter('캐시 장애', n_results=3)
assert len(r1['ids'][0]) > 0, '기본 검색 실패'

# 도메인 필터
r2 = chroma.query_with_filter('캐시', where={'domain': 'SCM'})
print(f'filtered results: {len(r2[\"ids\"][0])}')

# 태그 포함 필터
r3 = chroma.query_with_filter('장애', where={'tags': {'\$contains': '|장애대응|'}})
print(f'tag filtered: {len(r3[\"ids\"][0])}')

print('1E-B4: ALL PASS')
"
```

- `where=None` → 기존 query와 동일 결과
- 도메인 필터 → 해당 도메인 문서만 반환
- ChromaDB 미연결 → 빈 결과 (에러 아님)

### 1E-B5. rag_agent.py

- `metadata_filter` 파라미터 추가 확인 (코드 grep)
- 필터 있을 때 `query_with_filter()` 호출 확인
- 필터 없을 때 기존 동작 유지

### 1E-B6. GET /api/metadata/tags

```bash
curl -s http://localhost:8001/api/metadata/tags | python3 -m json.tool
```

- 200 + JSON: `{"domains": [...], "processes": [...], "error_codes": [...], "tags": [...]}`
- 각 배열에 중복값 없음
- wiki 문서의 태그가 포함됨

### 1E-B7 / 1E-B8. AI Auto-Suggest

```bash
curl -s -X POST http://localhost:8001/api/metadata/suggest \
  -H "Content-Type: application/json" \
  -d '{"content": "# KV 캐시 장애 대응\nRedis TTL 만료 시 대량 DB 조회 발생", "existing_tags": []}' \
  | python3 -m json.tool
```

- 200 + JSON: `domain`, `process`, `error_codes`, `tags`, `confidence`, `reasoning` 포함
- `tags`에 문서 내용과 관련된 태그가 추천됨
- `existing_tags`에 있는 태그는 추천에서 제외됨

### 1E-B9. 하위 호환성 검증

```bash
curl -s http://localhost:8001/api/search/tags | python3 -m json.tool
```

- 기존 `GET /api/search/tags` 엔드포인트가 정상 동작 (regression 없음)

### 1E-F1. MetadataTagBar

- `.md` 파일 열기 → 에디터 상단에 MetadataTagBar 표시
- `.xlsx` 파일 열기 → MetadataTagBar 미표시
- 열기/접기 토글 동작

### 1E-F2. TagInput

- 타이핑 → 자동 완성 드롭다운 표시
- 항목 선택 → Badge 추가
- Enter → 새 태그 Badge 생성
- ✕ 클릭 → Badge 제거
- 이미 추가된 태그 → 드롭다운에서 비활성

### 1E-F3. DomainSelect / ProcessSelect

- 드롭다운에 기존 목록 표시 (`/api/metadata/tags`에서 로드)
- 선택 → 값 반영

### 1E-F4. AutoTagButton

```
[수동 테스트] MD 문서 본문 작성 → ✨ Auto-Tag 클릭
```

- 클릭 → 로딩 스피너 표시
- 응답 후 → 점선 테두리 Badge로 추천 태그 표시
- 추천 Badge에 ✓(수락) / ✕(거절) 액션 존재
- 수락 → 일반 Badge(실선)로 전환
- 거절 → Badge 제거
- API 실패 → Toast "추천 실패" + 수동 입력 가능 상태 유지

### 1E-F5. Frontmatter 동기화

```typescript
// 브라우저 콘솔 또는 단위 테스트
import { serializeMetadataToFrontmatter, stripFrontmatter, mergeFrontmatterAndBody } from './lib/markdown/frontmatterSync';

const yaml = serializeMetadataToFrontmatter({ domain: "SCM", tags: ["cache"] });
console.assert(yaml.includes("domain: SCM"));
console.assert(yaml.includes("- cache"));

const body = stripFrontmatter("---\ndomain: SCM\n---\n# Title\nBody");
console.assert(body === "# Title\nBody");

const merged = mergeFrontmatterAndBody({ domain: "SCM", tags: ["cache"] }, "# Title\nBody");
console.assert(merged.startsWith("---"));
console.assert(merged.includes("# Title"));
```

- `serializeMetadataToFrontmatter` → 올바른 YAML 문자열
- `stripFrontmatter` → `---...---` 블록 정확히 제거
- `mergeFrontmatterAndBody` → frontmatter + 본문 결합
- 빈 metadata → frontmatter 블록 미생성 (또는 빈 `---\n---\n`)

### 1E-F6. 통합

```
[수동 시나리오]
1. frontmatter 있는 MD 열기 → TagBar에 기존 값 표시
2. 태그 추가 → 저장
3. 다시 열기 → 추가한 태그 유지
```

- 열기 → TagBar 역직렬화 동작
- 저장 → frontmatter 갱신 + `PUT /api/wiki/{path}` 호출
- 재열기 → 갱신된 메타데이터 유지
- ChromaDB에 새 metadata 반영 확인 (1E-B3 체크리스트 재수행)

---

## Step 1-F: AI Copilot + SSE 스트리밍

### 1F-0. 백엔드 Approval 발행 로직 (⚠️ 먼저 구현)

```bash
curl -s -X POST http://localhost:8001/api/agent/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "이 내용을 Wiki에 추가해줘: # 테스트\n테스트 본문", "session_id": "test-1"}' \
  --no-buffer
```

- SSE 스트림에 `event: approval_request` 이벤트가 포함된다
- `approval_request` 이벤트에 `action_id`, `path`, `diff_preview`가 포함된다

### 1F-1. SSE 클라이언트

```typescript
// 통합 테스트: 브라우저 콘솔
const events = [];
await streamChat("KV 캐시 장애?", "sess-1", (e) => events.push(e));
console.log(events.map(e => e.event));
// 기대: ["routing", "content_delta", ..., "sources", "done"]
```

- `content_delta` 이벤트 순서대로 수신
- `sources` 이벤트 파싱 성공
- `done` 이벤트 수신 시 Promise 정상 resolve
- 네트워크 끊김 시 에러 콜백 호출 (5초 timeout 등)

### 1F-2. AICopilot 채팅 UI

- 입력 필드 + 전송 버튼 존재
- Enter → 메시지 전송
- 사용자 메시지가 채팅 목록에 표시
- AI 응답이 채팅 목록에 표시
- 전송 중 입력 필드 비활성화
- 새 메시지 시 자동 스크롤

### 1F-3. 스트리밍 표시

- 응답이 토큰 단위로 실시간 추가된다 (한 번에 전체가 아님)
- 스트리밍 중 커서 또는 "..." 인디케이터 표시
- `done` 이벤트 후 인디케이터 사라짐

### 1F-4. 출처 표시

- 답변 하단에 출처 목록 표시 (파일 경로)
- 출처 클릭 → 해당 문서가 Workspace에서 탭으로 열림

### 1F-5. 승인/거절

```
[수동 테스트] "이 내용을 Wiki에 추가해줘" 입력
```

- `approval_request` 수신 → 승인/거절 UI 표시
- diff 미리보기 표시
- [승인] 클릭 → 네트워크에 `POST /api/approval/resolve` 요청 (`approved: true`)
- [거절] 클릭 → 네트워크에 `POST /api/approval/resolve` 요청 (`approved: false`)
- 승인 후 → "반영 완료" 피드백
- 거절 후 → "거절됨" 피드백

### 1F-6. 에러 핸들링

- 백엔드 다운 시 → "서버 연결 실패" Toast
- 빈 메시지 전송 → 프론트엔드 validation (요청 미전송)

---

## Step 4: 마이그레이션 + 통합 테스트

### 4-1 ~ 4-3. Frontmatter 추가

```bash
head -6 wiki/getting-started.md
head -6 wiki/order-processing-rules.md
head -6 wiki/kv-cache-troubleshoot.md
```

- 각 파일이 `---`로 시작한다
- `domain`, `tags` 등이 문서 내용에 적절하게 채워졌다
- 본문 내 `#tag`가 제거되었거나 frontmatter와 일치한다

### 4-4. 재색인

```bash
curl -s -X POST http://localhost:8001/api/wiki/reindex | python3 -m json.tool
```

- 200 응답 + chunk 수 반환
- ChromaDB에서 metadata 필드 확인 (1E-B3 체크 재수행)

### 4-5 ~ 4-8. E2E 시나리오

각각 CHECKLIST를 참조하여 순서대로 수행.

---

## Phase 1 최종 데모 시나리오

> **아래 10개가 전부 통과하면 Phase 1 완료.**

1. 앱 실행 → 3-Pane UI 정상 표시
2. TreeNav → `kv-cache-troubleshoot.md` 열기 → 탭 + 에디터 + MetadataTagBar
3. 에디터에서 편집 → `Ctrl+S` 저장
4. ✨ Auto-Tag → 추천 수락 → 저장
5. 두 번째 탭: `order-processing-rules.md` → 탭 전환 동작
6. AI Copilot: "KV 캐시 장애 시 대응 절차는?" → 스트리밍 답변 + 출처
7. AI Copilot: "이 내용을 Wiki에 추가해줘" → 승인/거절 → 승인 → 파일 반영
8. Excel 파일 열기 → 수정 → 저장
9. 이미지 붙여넣기 → 자동 업로드 + 에디터 삽입
10. Excel 표 붙여넣기 → Markdown 테이블 생성

---

## Ad-hoc: 인증 추상화 레이어

### 검증 항목

**Backend**

```bash
cd /Users/donghae/workspace/ai/onTong
source venv/bin/activate
python -c "from backend.core.auth import User, AuthProvider, get_current_user; print('OK')"
python -c "from backend.core.auth.factory import create_auth_provider; p = create_auth_provider('noop'); print(type(p).__name__)"
```

- `from backend.core.auth import ...` 정상 import
- `create_auth_provider('noop')` → `NoOpAuthProvider` 반환
- 백엔드 시작 로그에 `Auth provider: noop` 표시
- 모든 API 엔드포인트가 기존처럼 정상 동작 (NoOp이므로 인증 없이 통과)

**Frontend**

```bash
cd /Users/donghae/workspace/ai/onTong/frontend
npx tsc --noEmit
```

- TypeScript 컴파일 에�� 없음
- `Providers.tsx`가 `layout.tsx`에서 children을 감싸고 있음
- 앱 실행 시 기존 기능 모두 정상 동작 (DevAuthProvider가 항상 인증됨 상태 반환)

**교체 시뮬레이션 (수동 검증)**

- `factory.py`에서 없는 provider 이름 입력 시 `ValueError` 발생 확인:
  ```python
  python -c "from backend.core.auth.factory import create_auth_provider; create_auth_provider('unknown')"
  ```

---

# Phase 2+ 검증 체크리스트

> **최종 갱신**: 2026-04-01
> 아래 항목들은 Pre-Demo Verification Protocol에서 사용.
> `## Quick Smoke Test`는 매 변경 후 반드시 실행. 나머지는 해당 기능 변경 시 실행.

---

## Quick Smoke Test (매 변경 후 필수)

```bash
# 1. 백엔드 테스트
./venv/bin/pytest tests/ -x -q

# 2. 프론트엔드 타입 체크
cd frontend && npx tsc --noEmit

# 3. 프론트엔드 빌드
cd frontend && npm run build

# 4. 백엔드 서버 기동 확인
source venv/bin/activate && uvicorn backend.main:app --port 8001 &
sleep 3
curl -sf http://localhost:8001/api/wiki/tree | head -c 100
# → JSON 배열 출력

# 5. 기본 채팅 동작
curl -s -N -X POST http://localhost:8001/api/agent/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "장애 대응 절차 알려줘", "session_id": "smoke"}' \
  | grep -c "content_delta"
# → 1 이상
```

- [ ] pytest 전체 PASS
- [ ] tsc --noEmit 에러 0개
- [ ] npm run build 성공
- [ ] 백엔드 /api/wiki/tree 정상 응답
- [ ] 채팅 content_delta 이벤트 수신

---

## 충돌 감지 & 비교 해결

### CD-1. 충돌 경고 (SSE)

```bash
# 충돌 나야 하는 질문 (구체적 수치 비교)
curl -s -N -X POST http://localhost:8001/api/agent/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "밥 짓는법 쌀 몇컵?", "session_id": "cd-1"}' \
  | grep "conflict_warning"
```

- [ ] `conflict_warning` 이벤트 1개 발생
- [ ] `details` 필드가 한국어
- [ ] `conflict_pairs` 배열에 페어 1개 이상
- [ ] 각 페어에 `file_a`, `file_b`, `similarity`, `summary` 포함

### CD-2. 충돌 오탐 없음

```bash
# 충돌 안 나야 하는 일반 질문
curl -s -N -X POST http://localhost:8001/api/agent/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "밥 맛있게 짓는법 알려줘", "session_id": "cd-2"}' \
  | grep -c "conflict_warning"
# → 0

# 관련 없는 주제
curl -s -N -X POST http://localhost:8001/api/agent/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "VPN 접속 방법", "session_id": "cd-3"}' \
  | grep -c "conflict_warning"
# → 0
```

- [ ] 일반적 질문에서 `conflict_warning` 0건
- [ ] 무관한 주제에서 `conflict_warning` 0건

### CD-3. ConflictDashboard API

```bash
# 유사 문서 쌍 조회
curl -s "http://localhost:8001/api/conflict/duplicates?threshold=0.9" | python3 -m json.tool | head -20

# 풀 스캔
curl -s -X POST http://localhost:8001/api/conflict/full-scan
sleep 2
curl -s http://localhost:8001/api/conflict/scan-status
```

- [ ] `/api/conflict/duplicates` → JSON 배열 반환
- [ ] 각 항목에 `file_a`, `file_b`, `similarity` 포함
- [ ] full-scan 후 scan-status에 progress 반영

### CD-4. 문서 비교

```bash
curl -s "http://localhost:8001/api/wiki/compare?path_a=밥%20맛있게%20짓는%20법.md&path_b=테스트/맛있게_밥_짓는_법.md" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print('A:', d['file_a']['path']); print('B:', d['file_b']['path']); print('A content length:', len(d['file_a']['content'])); print('B content length:', len(d['file_b']['content']))"
```

- [ ] `file_a`, `file_b` 각각 `path`, `content`, `metadata` 포함
- [ ] content 길이 0 이상

### CD-5. Deprecation & Lineage

```bash
# deprecate API (주의: 실제 문서 상태 변경)
# curl -s -X POST "http://localhost:8001/api/conflict/deprecate?path=테스트/맛있게_밥_짓는_법.md&superseded_by=밥%20맛있게%20짓는%20법.md"

# lineage 확인
curl -s "http://localhost:8001/api/wiki/lineage/밥%20맛있게%20짓는%20법.md" | python3 -m json.tool
```

- [ ] lineage API가 `supersedes`, `superseded_by` 필드 반환
- [ ] deprecated 처리 후 superseded_by 체인 정상

---

## 문서 관계 그래프

### GR-1. Graph API

```bash
curl -s "http://localhost:8001/api/search/graph?center_path=밥%20맛있게%20짓는%20법.md&include_similar=true&similarity_threshold=0.8" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print('nodes:', len(d['nodes'])); print('edges:', len(d['edges']))"
```

- [ ] `nodes` 배열에 center 노드 포함
- [ ] `edges` 배열에 similarity/link 엣지 포함
- [ ] similarity_threshold 조절 시 엣지 수 변화

---

## 검색 API

### SR-1. Hybrid 검색

```bash
curl -s "http://localhost:8001/api/search/hybrid?q=장애대응&n=5" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print('results:', len(d['results'])); [print(f'  {r[\"path\"]} ({r[\"score\"]:.3f})') for r in d['results'][:3]]"
```

- [ ] results 배열 반환, 각 항목에 `path`, `score` 포함
- [ ] 관련 문서가 상위에 위치

### SR-2. Quick 검색

```bash
curl -s "http://localhost:8001/api/search/quick?q=캐시&limit=3" \
  | python3 -m json.tool | head -10
```

- [ ] 결과 반환, limit 이하 개수

---

## 스킬 시스템

### SK-1. 스킬 목록 & 매칭

```bash
curl -s http://localhost:8001/api/skills/ | python3 -c "import sys,json; d=json.load(sys.stdin); print('skills:', len(d['skills'])); [print(f'  {s[\"title\"]}') for s in d['skills'][:5]]"

curl -s "http://localhost:8001/api/skills/match?q=장애%20대응" | python3 -m json.tool
```

- [ ] 스킬 목록에 등록된 스킬 표시
- [ ] match API가 관련 스킬 반환

---

## 메타데이터 & 태깅

### MT-1. 메타데이터 태그

```bash
curl -s http://localhost:8001/api/metadata/tags | python3 -c "import sys,json; d=json.load(sys.stdin); print('domains:', len(d['domains'])); print('tags:', len(d['tags']))"

curl -s http://localhost:8001/api/metadata/untagged | python3 -c "import sys,json; d=json.load(sys.stdin); print('untagged:', len(d))"
```

- [ ] domains, tags 배열 반환
- [ ] untagged 목록 반환

### MT-2. 메타데이터 템플릿

```bash
curl -s http://localhost:8001/api/metadata/templates | python3 -m json.tool | head -15
```

- [ ] templates 설정 반환 (domains, processes, tag_presets)

---

## 문서 작성/수정 (SSE + Approval)

### WE-1. 문서 생성 플로우

```bash
curl -s -N -X POST http://localhost:8001/api/agent/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "서버 점검 체크리스트 만들어줘", "session_id": "we-1"}' \
  | grep -E "event: (approval_request|content_delta)" | head -5
```

- [ ] `approval_request` 이벤트 발생
- [ ] `action_type: "wiki_write"` 포함
- [ ] `content` 필드에 생성될 문서 내용 포함
- [ ] 채팅 content_delta에 긴 본문이 아닌 간단 안내만 표시

### WE-2. 문서 수정 플로우

```bash
curl -s -N -X POST http://localhost:8001/api/agent/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "밥 맛있게 짓는 법.md 문서에 현미밥 짓는법 섹션 추가해줘", "session_id": "we-2", "attached_files": ["밥 맛있게 짓는 법.md"]}' \
  | grep -E "event: (approval_request|content_delta)" | head -5
```

- [ ] `approval_request` 이벤트 발생
- [ ] `action_type: "wiki_edit"` 포함
- [ ] `original_content` 필드에 원본 내용 포함
- [ ] `content` 필드에 수정된 내용 포함

### WE-3. Approval 처리

```bash
# 승인 API (action_id는 위 테스트에서 추출)
# curl -s -X POST http://localhost:8001/api/approval/resolve \
#   -H "Content-Type: application/json" \
#   -d '{"action_id": "...", "approved": true, "session_id": "..."}'
```

- [ ] approved=true → 파일 실제 저장
- [ ] approved=false → 파일 미변경

---

## 문서 잠금 (Locking)

### LK-1. 잠금 라이프사이클

```bash
# 잠금 획득
curl -s -X POST http://localhost:8001/api/lock \
  -H "Content-Type: application/json" \
  -d '{"path": "test-lock.md", "user": "tester", "ttl": 10}' | python3 -m json.tool

# 잠금 상태 확인
curl -s "http://localhost:8001/api/lock/status?path=test-lock.md" | python3 -m json.tool

# 잠금 해제
curl -s -X DELETE "http://localhost:8001/api/lock?path=test-lock.md&user=tester"
```

- [ ] 잠금 획득 → locked: true
- [ ] 상태 확인 → holder 정보 표시
- [ ] 해제 → locked: false

---

## 파일/에셋 관리

### FM-1. 미사용 에셋

```bash
curl -s http://localhost:8001/api/files/assets/unused | python3 -m json.tool | head -10
```

- [ ] 미참조 이미지 목록 반환 (또는 빈 배열)

---

## Pre-Demo 자동 검증 스크립트

> 위 체크리스트의 핵심 항목을 한 번에 실행하는 스크립트.
> 변경 후 `bash toClaude/verify.sh`로 실행.

```bash
#!/bin/bash
# toClaude/verify.sh — Pre-Demo Quick Verification
set -e
cd "$(dirname "$0")/.."

echo "═══ 1. pytest ═══"
./venv/bin/pytest tests/ -x -q

echo ""
echo "═══ 2. TypeScript ═══"
cd frontend && npx tsc --noEmit && cd ..

echo ""
echo "═══ 3. Backend alive ═══"
curl -sf http://localhost:8001/api/wiki/tree > /dev/null && echo "OK" || echo "FAIL: backend not running"

echo ""
echo "═══ 4. Chat basic ═══"
DELTAS=$(curl -s -N -X POST http://localhost:8001/api/agent/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"장애 대응 절차","session_id":"verify"}' | grep -c "content_delta")
[ "$DELTAS" -gt 0 ] && echo "OK ($DELTAS deltas)" || echo "FAIL: no content_delta"

echo ""
echo "═══ 5. Conflict false-positive check ═══"
FP=$(curl -s -N -X POST http://localhost:8001/api/agent/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"밥 맛있게 짓는법 알려줘","session_id":"verify-fp"}' | grep -c "conflict_warning")
[ "$FP" -eq 0 ] && echo "OK (no false positive)" || echo "FAIL: false positive conflict"

echo ""
echo "═══ 6. Conflict detection ═══"
CD=$(curl -s -N -X POST http://localhost:8001/api/agent/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"밥 짓는법 쌀 몇컵?","session_id":"verify-cd"}' | grep -c "conflict_warning")
[ "$CD" -gt 0 ] && echo "OK (conflict detected)" || echo "WARN: conflict not detected (LLM dependent)"

echo ""
echo "═══ 7. API endpoints ═══"
curl -sf "http://localhost:8001/api/conflict/duplicates?threshold=0.9" > /dev/null && echo "conflict/duplicates: OK" || echo "FAIL"
curl -sf "http://localhost:8001/api/search/graph?center_path=밥%20맛있게%20짓는%20법.md" > /dev/null && echo "search/graph: OK" || echo "FAIL"
curl -sf http://localhost:8001/api/metadata/tags > /dev/null && echo "metadata/tags: OK" || echo "FAIL"
curl -sf http://localhost:8001/api/skills/ > /dev/null && echo "skills: OK" || echo "FAIL"

echo ""
echo "═══ DONE ═══"
```
