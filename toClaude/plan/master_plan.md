# onTong - Workspace 고도화 계획
## 작성일: 2025-03-25
## 기반: 2_claude_final_plan.md + 추가 요구사항 + 코드 검토 반영

---

## 추가 요구사항 요약

| # | 요구사항 | 핵심 키워드 |
|---|---------|------------|
| 1 | Workspace 영역을 옵시디언처럼 탭 형식으로 동작 | Multi-Tab UI |
| 2 | PPT, Excel 등 다양한 파일을 열람/수정 (오픈소스 활용) | Multi-Format Viewer/Editor |
| 3 | 일반 MD 문서는 당연히 수정 가능 | Markdown WYSIWYG |
| 4 | MD 파일에 엑셀 표나 이미지를 바로 붙여넣기 | Clipboard Paste (Table/Image) |
| 5 | YAML Frontmatter 메타데이터를 RAG 파이프라인에 통합 | Metadata Tagging Pipeline |
| 6 | 직관적인 태그 입력 UI + AI Auto-Suggest + Human-in-the-loop | Smart Tag UX |

---

## 현재 구현 상태 (계획 전 기준선)

계획과 기존 코드의 정합성을 보장하기 위해 현재 상태를 명시한다.

| 컴포넌트 | 상태 | 비고 |
|----------|------|------|
| **인증 추상화** (AuthProvider, NoOp, deps) | ✅ 완료 | Provider 교체로 SSO/LDAP/OIDC 지원 가능 |
| **백엔드 Core** (config, schemas, session) | ✅ 완료 | |
| **Storage** (ABC + LocalFSAdapter) | ✅ 완료 | frontmatter 파싱 미지원 — `#tag` 정규식만 |
| **VectorDB** (ChromaWrapper) | ✅ 완료 | `query()`만 있음, `where` 필터 없음 |
| **WikiService / Indexer / Search** | ✅ 완료 | metadatas에 `file_path`/`heading`만 저장 |
| **Router + ToolRegistry** | ✅ 완료 | 2-tier intent classification |
| **RAG Agent (WIKI_QA)** | ✅ 완료 | SSE 스트리밍 |
| **Simulator / Tracer Agent** | Mock only | Phase 2 |
| **API 엔드포인트** | ✅ 완료 | wiki, search, agent, approval |
| **프론트엔드** | ✅ 완료 | Phase 1 전체 구현 + Auth 추상화 |

---

## 1. Multi-Tab Workspace (옵시디언 스타일)

### 개념

기존 계획의 중앙 "Markdown Editor" 영역을 **탭 기반 Workspace**로 확장한다.
여러 파일을 동시에 열어두고 탭으로 전환하며, 파일 타입에 따라 적절한 뷰어/에디터를 렌더링한다.

```
┌─────────────────────────────────────────────────────────────────┐
│ [Tree Nav]  │  ┌─ Tab Bar ──────────────────────┐ │ [AI Copilot] │
│             │  │ 📄 guide.md │ 📊 data.xlsx │ ✕ │ │              │
│  wiki/      │  ├──────────────────────────────────┤ │  채팅 영역   │
│  ├─ ops/    │  │                                  │ │              │
│  ├─ guide.md│  │   << 활성 탭의 콘텐츠 영역 >>    │ │  [승인/거절] │
│  └─ data.xlsx  │                                  │ │              │
│             │  └──────────────────────────────────┘ │              │
└─────────────────────────────────────────────────────────────────┘
```

### 탭 동작 사양

| 기능 | 설명 |
|------|------|
| 탭 열기 | Tree Nav에서 파일 클릭 시 새 탭으로 열림 (이미 열려있으면 해당 탭으로 포커스) |
| 탭 닫기 | 탭의 ✕ 버튼 또는 Ctrl+W |
| 탭 순서 변경 | 드래그 앤 드롭으로 탭 순서 변경 |
| 수정 표시 | 변경사항 있는 탭에 ● 표시 (unsaved indicator) |
| 탭 상태 유지 | 탭 전환 시 스크롤 위치, 커서 위치 등 상태 보존 |

### 프론트엔드 상태 관리

```typescript
// Zustand store
interface Tab {
  id: string;
  filePath: string;
  fileType: FileType;       // "markdown" | "spreadsheet" | "presentation" | "pdf" | "image" | "unknown"
  title: string;
  isDirty: boolean;         // unsaved changes
  scrollPosition?: number;
}

interface WorkspaceState {
  tabs: Tab[];
  activeTabId: string | null;
  openTab: (filePath: string) => void;
  closeTab: (tabId: string) => void;
  setActiveTab: (tabId: string) => void;
  reorderTabs: (fromIndex: number, toIndex: number) => void;
}
```

### 핵심 컴포넌트 구조

```
frontend/src/components/workspace/
├── TabBar.tsx              # 탭 바 (드래그 정렬, 닫기, dirty 표시)
├── WorkspacePanel.tsx      # 활성 탭의 콘텐츠를 렌더링하는 컨테이너
├── FileRouter.tsx          # fileType에 따라 적절한 뷰어/에디터로 라우팅
├── editors/
│   ├── MarkdownEditor.tsx  # MD 편집기
│   ├── SpreadsheetViewer.tsx # Excel 뷰어/에디터
│   ├── PresentationViewer.tsx # PPT 뷰어
│   ├── PdfViewer.tsx       # PDF 뷰어
│   └── ImageViewer.tsx     # 이미지 뷰어
└── hooks/
    └── useWorkspaceStore.ts # 탭 상태 관리
```

---

## 2. Multi-Format 파일 지원 (오픈소스 라이브러리)

### 파일 타입별 라이브러리 선정

| 파일 타입 | 확장자 | 열람 라이브러리 | 수정 가능 여부 | 수정 라이브러리 |
|-----------|--------|----------------|--------------|----------------|
| **Markdown** | `.md` | Tiptap (ProseMirror) | ✅ 완전 수정 | Tiptap |
| **Excel** | `.xlsx`, `.xls`, `.csv` | Luckysheet / Univer | ✅ 수정 가능 | Luckysheet / Univer |
| **PowerPoint** | `.pptx` | pptxjs / 서버 변환 | 🔶 읽기 전용 (Phase 1) | - |
| **PDF** | `.pdf` | react-pdf (pdf.js 래핑) | 🔶 읽기 전용 | - |
| **이미지** | `.png`, `.jpg`, `.svg` | native `<img>` | 🔶 읽기 전용 | - |

### 라이브러리 상세 선정 기준

#### Markdown: **Tiptap** (1순위) 또는 Milkdown (대안)

- **Tiptap** (권장):
  - ProseMirror 기반, 문서화가 풍부하고 shadcn/ui와 궁합이 좋음
  - 공식 extension 생태계: table, image, placeholder, slash-command 등
  - React 바인딩 (`@tiptap/react`) 안정적
  - WYSIWYG + 소스 모드 토글 구현이 straightforward
- **Milkdown** (대안):
  - 역시 ProseMirror 기반이지만, 버전별 import 경로 변경이 잦아 호환성 리스크 있음
  - 플러그인 확장성 우수하나 문서화가 Tiptap 대비 부족

#### Excel: **Luckysheet** 또는 **Univer**
- **Luckysheet**: 순수 웹 스프레드시트, 엑셀 호환 UI, 수식/차트/피벗 지원
  - 장점: 완성도 높은 Excel 호환 UI, 활발한 커뮤니티
  - 단점: 번들 사이즈 큼, 유지보수 불규칙
- **Univer** (Luckysheet 후속): 최신 아키텍처, 플러그인 시스템
  - 장점: 모던 설계, 문서/스프레드시트/프레젠테이션 통합
  - 단점: 비교적 신규 프로젝트
- **파일 I/O**: SheetJS (`xlsx`) 라이브러리로 `.xlsx` ↔ JSON 변환

#### PowerPoint: **pptxjs** + 서버 변환 하이브리드
- 클라이언트: pptxjs로 기본 슬라이드 렌더링
- 서버 폴백: python-pptx로 슬라이드를 이미지로 변환 → 갤러리 뷰
- Phase 1에서는 읽기 전용

#### PDF: **react-pdf**
- pdf.js 공식 React 래퍼
- 페이지 네비게이션, 줌, 텍스트 선택 지원

### 백엔드 파일 API (바이너리 전용)

> **중요**: MD 파일은 기존 `/api/wiki/*` 엔드포인트를 사용한다 (frontmatter 파싱, 재색인 포함).
> `/api/files/*`는 **바이너리 파일 전용** (Excel, PPT, PDF, Image)으로 분리한다.

```python
# backend/api/files.py (신규) — 바이너리 파일 전용

@router.get("/api/files/{path:path}")
async def get_file(path: str):
    """바이너리 파일 원본 반환 (Excel, PPT, PDF, Image)"""
    ...

@router.post("/api/files/{path:path}/convert")
async def convert_file(path: str, target_format: str):
    """서버 사이드 파일 변환 (예: pptx → images)"""
    ...

@router.put("/api/files/{path:path}")
async def save_file(path: str, file: UploadFile):
    """수정된 바이너리 파일 저장 (Excel 등)"""
    ...

@router.post("/api/files/upload/image")
async def upload_image(file: UploadFile) -> ImageUploadResponse:
    """이미지를 wiki/assets/에 저장하고 상대 경로 반환"""
    ...

class ImageUploadResponse(BaseModel):
    path: str           # "assets/20250325_a1b2c3.png"
    markdown: str       # "![](assets/20250325_a1b2c3.png)"

class FileInfo(BaseModel):
    path: str
    name: str
    extension: str
    file_type: Literal["markdown", "spreadsheet", "presentation", "pdf", "image", "unknown"]
    size: int
    modified_at: datetime
```

### API 역할 구분 (프론트엔드 참조)

| 파일 타입 | 읽기 | 쓰기 | 비고 |
|-----------|------|------|------|
| `.md` | `GET /api/wiki/file/{path}` | `PUT /api/wiki/file/{path}` | frontmatter 파싱 + 재색인 포함 |
| `.xlsx`, `.pptx`, `.pdf`, 이미지 | `GET /api/files/{path}` | `PUT /api/files/{path}` | 바이너리 CRUD only |
| 이미지 업로드 (붙여넣기) | - | `POST /api/files/upload/image` | wiki/assets/에 저장 |

---

## 3. Markdown 편집 강화

### WYSIWYG 에디터 (Tiptap)

기존 계획의 CodeMirror를 **Tiptap**으로 교체한다.

| 기능 | 설명 |
|------|------|
| WYSIWYG 편집 | 리치 텍스트처럼 직접 편집 (볼드, 헤딩, 리스트 등) |
| 소스 모드 토글 | 원본 Markdown 소스 직접 편집 가능 |
| 실시간 저장 | 일정 간격(debounce) 자동 저장 또는 Ctrl+S 수동 저장 |
| 테이블 에디터 | GUI 테이블 삽입/편집 (행/열 추가·삭제) |
| 슬래시 명령어 | `/` 입력 시 블록 타입 선택 메뉴 (옵시디언 스타일) |

### Tiptap Extension 구성

```typescript
import { useEditor } from '@tiptap/react';
import StarterKit from '@tiptap/starter-kit';
import Table from '@tiptap/extension-table';
import TableRow from '@tiptap/extension-table-row';
import TableCell from '@tiptap/extension-table-cell';
import TableHeader from '@tiptap/extension-table-header';
import Image from '@tiptap/extension-image';
import Placeholder from '@tiptap/extension-placeholder';
import TaskList from '@tiptap/extension-task-list';
import TaskItem from '@tiptap/extension-task-item';
// + custom slash command extension
// + custom clipboard handler (Excel table paste)
```

---

## 4. 클립보드 붙여넣기 (엑셀 표 + 이미지)

### 4-A. 엑셀 표 → Markdown 테이블 변환

사용자가 Excel에서 셀 범위를 복사 후 MD 에디터에 Ctrl+V하면, 클립보드의 HTML 테이블을 Markdown 테이블로 자동 변환한다.

```
[사용자 흐름]
1. Excel에서 셀 범위 선택 → Ctrl+C
2. Tiptap 에디터에서 Ctrl+V
3. 클립보드 이벤트 가로채기:
   - clipboardData.getData("text/html")로 HTML 테이블 추출
   - HTML <table> → Tiptap Table 노드로 변환 (또는 MD 테이블)
   - 에디터에 삽입
```

#### 변환 로직

```typescript
// frontend/src/lib/clipboard/tableConverter.ts

/**
 * HTML 테이블을 Tiptap Table 노드 또는 Markdown 테이블 문자열로 변환
 *
 * Input (clipboard HTML):
 *   <table><tr><td>이름</td><td>수량</td></tr><tr><td>볼트</td><td>100</td></tr></table>
 *
 * Output (Markdown):
 *   | 이름 | 수량 |
 *   |------|------|
 *   | 볼트 | 100  |
 */
function htmlTableToMarkdown(html: string): string | null { ... }
```

### 4-B. 이미지 붙여넣기 → 자동 업로드

사용자가 스크린샷이나 이미지를 Ctrl+V하면, 백엔드에 자동 업로드 후 Markdown 이미지 링크로 삽입한다.

```
[사용자 흐름]
1. 스크린샷 또는 이미지 복사 (Ctrl+C 또는 캡처 도구)
2. Tiptap 에디터에서 Ctrl+V
3. 클립보드의 image/png blob 감지:
   - 백엔드 POST /api/files/upload/image로 전송
   - 서버에서 wiki/assets/{timestamp}_{random}.png로 저장
   - 응답으로 받은 경로를 ![](경로) 형태로 에디터에 삽입
```

#### 드래그 앤 드롭 지원

이미지 파일을 에디터 영역에 직접 드래그 앤 드롭해도 동일한 업로드 흐름을 탄다.

---

## 5. Metadata Tagging Pipeline (Backend + Frontend 통합)

### 개요

Wiki MD 문서의 YAML Frontmatter에 메타데이터(도메인, 프로세스, 에러코드, 태그)를 정의하고,
이를 ChromaDB 벡터 검색과 결합한 **Hybrid Search**를 구현한다.
프론트엔드에서는 직관적인 태그 입력 UI와 AI 자동 추천을 제공한다.

### 5-A. Backend: Metadata Pipeline

#### YAML Frontmatter 규격

```yaml
---
domain: "SCM"
process: "order-processing"
error_codes: ["DG320", "DG410"]
tags: ["KV캐시", "장애대응", "운영"]
author: "donghae"
created: "2025-03-20"
---

# KV 캐시 장애 대응 절차
...본문...
```

#### Pydantic 스키마 확장

> **마이그레이션 주의**: 현재 `WikiFile`에 `tags: list[str]`이 있고, `WikiSearchService.build_tag_index()`가
> `f.tags`를 직접 참조한다. `metadata` 필드를 추가하되, 기존 `tags` 필드와 호환성을 유지해야 한다.

```python
# backend/core/schemas.py (추가/수정)

class DocumentMetadata(BaseModel):
    """YAML frontmatter에서 파싱한 문서 메타데이터."""
    domain: str | None = None
    process: str | None = None
    error_codes: list[str] = []
    tags: list[str] = []
    author: str | None = None
    created: str | None = None

class WikiFile(BaseModel):
    path: str
    title: str
    content: str                     # frontmatter 제외한 본문
    raw_content: str = ""            # frontmatter 포함 원본
    metadata: DocumentMetadata = DocumentMetadata()
    links: list[str] = []

    @property
    def tags(self) -> list[str]:
        """하위 호환성: WikiSearchService 등이 f.tags로 접근하는 코드 유지."""
        return self.metadata.tags

class MetadataSuggestion(BaseModel):
    """LLM이 반환하는 메타데이터 자동 추천 결과."""
    domain: str | None = None
    process: str | None = None
    error_codes: list[str] = []
    tags: list[str] = []
    confidence: float = 0.0
    reasoning: str = ""
```

#### Frontmatter 파싱 위치: Storage Layer (단일 책임)

> **설계 결정**: Frontmatter 파싱은 `LocalFSAdapter._to_wiki_file()` 에서 **한 번만** 수행한다.
> `WikiIndexer`에서는 이미 파싱된 `wiki_file.metadata`만 참조한다.
> 현재 `local_fs.py`의 `_extract_tags()`는 `#tag` 정규식인데, YAML frontmatter 파싱으로 교체한다.

```python
# backend/infrastructure/storage/local_fs.py (수정)

import yaml

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)

def _parse_frontmatter(self, content: str) -> tuple[DocumentMetadata, str]:
    """YAML frontmatter 파싱 → (metadata, body without frontmatter).
    frontmatter가 없으면 기존 #tag 정규식으로 폴백."""
    match = FRONTMATTER_RE.match(content)
    if match:
        try:
            fm = yaml.safe_load(match.group(1)) or {}
        except yaml.YAMLError:
            fm = {}
        body = content[match.end():]
        return DocumentMetadata(**{k: v for k, v in fm.items() if k in DocumentMetadata.model_fields}), body
    # 폴백: 기존 #tag 추출 (하위 호환)
    tags = self._extract_tags(content)
    return DocumentMetadata(tags=tags), content

def _to_wiki_file(self, path: str, content: str) -> WikiFile:
    metadata, body = self._parse_frontmatter(content)
    return WikiFile(
        path=path,
        title=self._extract_title(body, path),
        content=body,
        raw_content=content,
        metadata=metadata,
        links=self._extract_links(content),
    )
```

#### WikiIndexer 수정 — metadata를 ChromaDB에 저장

`WikiIndexer`는 `wiki_file.metadata`를 읽어서 ChromaDB `metadatas`에 포함한다.
파싱 로직은 건드리지 않는다 (Storage Layer 책임).

> **ChromaDB list 타입 저장 전략**: ChromaDB metadata value는 `str|int|float|bool`만 지원.
> list 필드는 **파이프(`|`) 구분자로 감싸서 저장**하고, 검색 시 `$contains`로 `|tag|` 패턴 매칭.
> 예: `tags = "|KV캐시|장애대응|운영|"` → `where: {"tags": {"$contains": "|KV캐시|"}}`

```python
# backend/application/wiki/wiki_indexer.py (수정)

def _metadata_to_chroma(self, metadata: DocumentMetadata) -> dict:
    """DocumentMetadata → ChromaDB-compatible flat dict."""
    return {
        "domain": metadata.domain or "",
        "process": metadata.process or "",
        "error_codes": "|" + "|".join(metadata.error_codes) + "|" if metadata.error_codes else "",
        "tags": "|" + "|".join(metadata.tags) + "|" if metadata.tags else "",
        "author": metadata.author or "",
    }

async def index_file(self, wiki_file: WikiFile) -> int:
    chunks = self.chunk(wiki_file)
    if not chunks:
        return 0
    chroma_meta = self._metadata_to_chroma(wiki_file.metadata)
    self.chroma.upsert(
        ids=[c.id for c in chunks],
        documents=[c.content for c in chunks],
        metadatas=[
            {"file_path": c.file_path, "heading": c.heading, **chroma_meta}
            for c in chunks
        ],
    )
    ...
```

#### ChromaDB Hybrid Search — `where` 필터

```python
# backend/infrastructure/vectordb/chroma.py (메서드 추가)

def query_with_filter(
    self,
    query_text: str,
    n_results: int = 5,
    where: dict | None = None,
) -> dict:
    """벡터 유사도 검색 + 메타데이터 필터(ChromaDB where clause).

    사용 예:
      # 단일 필드 정확 매칭
      where={"domain": "SCM"}

      # 태그 포함 (파이프 구분자 패턴)
      where={"tags": {"$contains": "|KV캐시|"}}

      # 복합 조건
      where={"$and": [{"domain": "SCM"}, {"tags": {"$contains": "|장애대응|"}}]}
    """
    if not self.is_connected:
        return {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}
    kwargs = {"query_texts": [query_text], "n_results": n_results}
    if where:
        kwargs["where"] = where
    return self._collection.query(**kwargs)
```

#### RAG Agent 검색 도구 수정

```python
# backend/application/agent/rag_agent.py (수정)

class SearchToolInput(BaseModel):
    query: str
    metadata_filter: dict | None = None  # 예: {"domain": "SCM"} 또는 {"$and": [...]}

# Agent가 검색 시:
results = self.chroma.query_with_filter(
    query_text=tool_input.query,
    n_results=5,
    where=tool_input.metadata_filter,
)
```

#### 태그/카테고리 조회 API

```python
# backend/api/metadata.py (신규)

@router.get("/api/metadata/tags")
async def get_all_tags(wiki_service: WikiService = Depends(...)) -> AllMetadataResponse:
    """모든 Wiki 문서에서 사용된 고유 태그/도메인/프로세스 목록 반환.
    프론트엔드 TagInput 드롭다운을 populate하는 데 사용."""
    ...

class AllMetadataResponse(BaseModel):
    domains: list[str]       # 고유 domain 목록
    processes: list[str]     # 고유 process 목록
    error_codes: list[str]   # 고유 error_code 목록
    tags: list[str]          # 고유 tag 목록
```

### 5-B. Frontend UX: Smart Tagging

#### UI 레이아웃 — 에디터 상단 태그 바

```
┌── Tab: guide.md ──────────────────────────────────────────────┐
│ ┌─ Metadata Tag Bar ────────────────────────────────────────┐ │
│ │ Domain: [SCM ▼]  Process: [order-processing ▼]            │ │
│ │ Tags: [KV캐시 ✕] [장애대응 ✕] [+ 태그 추가...]           │ │
│ │ Error Codes: [DG320 ✕] [+ 추가...]    [✨ Auto-Tag]      │ │
│ └───────────────────────────────────────────────────────────┘ │
│ ┌─ Tiptap Editor ─────────────────────────────────────────┐   │
│ │                                                           │ │
│ │  # KV 캐시 장애 대응 절차                                 │ │
│ │  ...본문...                                               │ │
│ │                                                           │ │
│ └───────────────────────────────────────────────────────────┘ │
└───────────────────────────────────────────────────────────────┘
```

#### 컴포넌트 설계

```
frontend/src/components/workspace/editors/
├── MarkdownEditor.tsx          # Tiptap 에디터
└── metadata/
    ├── MetadataTagBar.tsx      # 태그 바 컨테이너 (에디터 상단)
    ├── TagInput.tsx            # shadcn Command/Combobox + Badge 기반 태그 입력
    ├── DomainSelect.tsx        # 도메인 셀렉트 드롭다운
    ├── ProcessSelect.tsx       # 프로세스 셀렉트 드롭다운
    └── AutoTagButton.tsx       # ✨ Auto-Tag 버튼 + 추천 결과 표시
```

#### Interactive Tag Input (shadcn/ui)

```typescript
// TagInput.tsx — shadcn Command + Badge 조합
//
// 동작 방식:
// 1. 입력 필드에 타이핑 시 → 기존 태그 목록에서 필터링 (자동 완성)
// 2. 드롭다운에서 선택하거나 Enter로 새 태그 생성
// 3. 선택된 태그는 Badge로 표시, ✕ 클릭으로 제거
// 4. 태그 목록은 GET /api/metadata/tags에서 fetch하여 드롭다운 populating

interface TagInputProps {
  value: string[];
  onChange: (tags: string[]) => void;
  suggestions: string[];         // 서버에서 가져온 기존 태그 목록
  placeholder?: string;
}
```

#### AI Auto-Tag 흐름

```
[사용자 흐름]
1. 사용자가 MD 문서 작성/편집 중
2. [✨ Auto-Tag] 버튼 클릭
3. 프론트엔드: 현재 에디터의 markdown 본문을 POST /api/metadata/suggest로 전송
4. 백엔드: LiteLLM으로 본문 분석 → MetadataSuggestion (Pydantic) 반환
5. 프론트엔드: 추천된 태그를 MetadataTagBar에 "추천" 상태로 표시
   - 추천 태그는 점선 테두리 Badge로 구분 (기존 확정 태그와 시각 차이)
   - 각 추천 태그에 [✓ 수락] [✕ 거절] 개별 액션
6. 사용자가 추천 태그를 수락/거절/수정 후 [Save] → Frontmatter 갱신 + 재색인

[에러 핸들링]
- LLM API timeout (30초 이상) → "추천 실패" 토스트 알림 + 수동 입력으로 폴백
- LLM 응답 파싱 실패 → 동일 폴백
- 네트워크 오류 → 재시도 버튼 표시
```

#### Auto-Tag 백엔드 API

```python
# backend/api/metadata.py (추가)

@router.post("/api/metadata/suggest")
async def suggest_metadata(request: MetadataSuggestRequest) -> MetadataSuggestion:
    """LLM을 사용하여 문서 본문 기반 메타데이터 자동 추천."""
    ...

class MetadataSuggestRequest(BaseModel):
    content: str               # 현재 MD 에디터의 본문
    existing_tags: list[str] = []  # 이미 적용된 태그 (중복 방지용)
```

#### LLM 프롬프트 (구조화 출력)

```python
# backend/application/metadata/metadata_service.py (신규)

SYSTEM_PROMPT = """You are a metadata tagger for manufacturing SCM wiki documents.
Analyze the document and suggest structured metadata.
Return ONLY the JSON matching the schema. Do not explain."""

async def suggest_metadata(content: str, existing_tags: list[str]) -> MetadataSuggestion:
    response = await litellm.acompletion(
        model=settings.LLM_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Document:\n{content}\n\nExisting tags: {existing_tags}"},
        ],
        response_format=MetadataSuggestion,  # Pydantic 구조화 출력
    )
    return MetadataSuggestion.model_validate_json(response.choices[0].message.content)
```

#### 저장 시 Frontmatter 동기화

```typescript
// frontend/src/lib/markdown/frontmatterSync.ts

/**
 * MetadataTagBar의 상태를 YAML frontmatter로 직렬화하여
 * 에디터 본문 최상단에 삽입/갱신한다.
 *
 * 저장 흐름:
 * 1. MetadataTagBar 상태 → YAML 문자열 생성
 * 2. 에디터 본문에서 기존 --- ... --- 블록 제거
 * 3. 새 frontmatter + 본문 결합
 * 4. PUT /api/wiki/{path} 로 저장 (주의: /api/files/ 아님!)
 * 5. 백엔드 LocalFSAdapter에서 frontmatter 파싱 → WikiFile.metadata 채움
 * 6. WikiIndexer에서 metadata를 ChromaDB metadatas에 저장
 */
function serializeMetadataToFrontmatter(metadata: DocumentMetadata): string { ... }
function stripFrontmatter(content: string): string { ... }
function mergeFrontmatterAndBody(metadata: DocumentMetadata, body: string): string { ... }
```

---

## 6. SSE 스트리밍 클라이언트 (AI Copilot)

> **누락 보완**: 백엔드 `POST /api/agent/chat`이 SSE 스트리밍을 반환하는데,
> 프론트엔드에서 이를 수신하는 클라이언트가 계획에 없었으므로 추가한다.

```typescript
// frontend/src/lib/api/sseClient.ts

/**
 * SSE 스트리밍 클라이언트.
 * POST 요청으로 SSE를 받아야 하므로 EventSource(GET 전용) 대신
 * fetch + ReadableStream을 사용한다.
 *
 * 이벤트 타입별 핸들러:
 * - content_delta: 실시간 토큰 표시
 * - sources: 출처 목록 업데이트
 * - approval_request: [승인/거절] UI 표시
 * - error: 에러 토스트
 * - done: 스트리밍 종료
 */
async function streamChat(
  message: string,
  sessionId: string,
  onEvent: (event: SSEEvent) => void,
): Promise<void> { ... }
```

---

## 수정된 아키텍처

```
┌───────────────────────────────────────────────────────────────────────────┐
│                        3-PANE FRONTEND (Next.js)                           │
│                                                                            │
│  [Tree Nav]    │  [Tab-based Workspace]                 │  [AI Copilot]    │
│                │  ┌─────────────────────────────────┐   │                  │
│  wiki/         │  │ Tab: guide.md │ data.xlsx │ ... │   │  SSE 스트리밍    │
│  ├── ops/      │  ├─────────────────────────────────┤   │  채팅 영역       │
│  ├── guide.md  │  │ ┌─ MetadataTagBar ───────────┐ │   │                  │
│  ├── data.xlsx │  │ │ Domain:[SCM▼] Tags:[...✕]  │ │   │  [승인 / 거절]  │
│  ├── report.pptx  │ │ [✨ Auto-Tag]              │ │   │                  │
│  └── assets/   │  │ └────────────────────────────┘ │   │                  │
│                │  │ ┌─ Editor/Viewer ────────────┐ │   │                  │
│                │  │ │  Tiptap / Luckysheet /     │ │   │                  │
│                │  │ │  pptxjs / react-pdf        │ │   │                  │
│                │  │ └────────────────────────────┘ │   │                  │
│                │  └─────────────────────────────────┘   │                  │
└───────────────────────────────────────────────────────────────────────────┘
          │ REST / SSE                                  │ POST + SSE
┌───────────────────────────────────────────────────────────────────────────┐
│                 BACKEND (FastAPI + LiteLLM)                                │
│                                                                            │
│  /api/wiki/*  ─── MD 전용 CRUD + frontmatter 파싱 + 재색인                │
│  /api/files/* ─── 바이너리 파일 CRUD + 변환 + 이미지 업로드               │
│  /api/metadata/* ─ 태그 조회 + AI Auto-Suggest                            │
│  /api/agent/*  ── Router → Agent 라우팅 (SSE 스트리밍)                    │
│  /api/approval/* ─ Human-in-the-loop 승인/거절                            │
│  /api/search/* ── 검색 인덱스 + 백링크 + 태그 인덱스                      │
└───────────────────────────────────────────────────────────────────────────┘
```

---

## 수정된 디렉토리 구조 (프론트엔드)

```
frontend/src/
├── app/
│   └── page.tsx                    # 3-Pane 메인 레이아웃
├── components/
│   ├── TreeNav.tsx                 # 좌측: Wiki 파일 트리
│   ├── AICopilot.tsx               # 우측: 채팅 + SSE 스트리밍 + 승인/거절
│   └── workspace/
│       ├── TabBar.tsx              # 탭 바 UI
│       ├── WorkspacePanel.tsx      # 탭 콘텐츠 컨테이너
│       ├── FileRouter.tsx          # 파일 타입별 뷰어/에디터 라우팅
│       └── editors/
│           ├── MarkdownEditor.tsx  # Tiptap WYSIWYG
│           ├── metadata/
│           │   ├── MetadataTagBar.tsx    # 에디터 상단 태그 바 컨테이너
│           │   ├── TagInput.tsx          # shadcn Command/Combobox + Badge
│           │   ├── DomainSelect.tsx      # 도메인 드롭다운
│           │   ├── ProcessSelect.tsx     # 프로세스 드롭다운
│           │   └── AutoTagButton.tsx     # ✨ Auto-Tag 버튼
│           ├── SpreadsheetViewer.tsx # Luckysheet/Univer
│           ├── PresentationViewer.tsx # pptxjs
│           ├── PdfViewer.tsx       # react-pdf
│           └── ImageViewer.tsx     # 이미지 뷰어
├── lib/
│   ├── api/
│   │   └── sseClient.ts          # SSE 스트리밍 클라이언트 (fetch + ReadableStream)
│   ├── clipboard/
│   │   ├── tableConverter.ts       # HTML 테이블 → MD 테이블 변환
│   │   └── imagePaste.ts          # 이미지 붙여넣기 → 업로드 → MD 삽입
│   ├── markdown/
│   │   └── frontmatterSync.ts     # Frontmatter ↔ MetadataTagBar 동기화
│   └── workspace/
│       └── useWorkspaceStore.ts   # Zustand 탭 상태 관리
└── types/
    └── workspace.ts               # Tab, FileType, DocumentMetadata 등 타입 정의
```

---

## 수정된 디렉토리 구조 (백엔드 추가분)

```
backend/
├── api/
│   ├── files.py                   # (신규) /api/files/* — 바이너리 파일 전용 CRUD + 이미지 업로드
│   ├── metadata.py                # (신규) /api/metadata/* — 태그 조회 + AI Auto-Suggest
│   └── ... (기존 wiki.py, agent.py, approval.py, search.py 유지)
├── application/
│   ├── files/
│   │   ├── file_service.py        # (신규) 파일 타입 감지, 변환 로직
│   │   └── image_service.py       # (신규) 이미지 저장, 경로 생성
│   └── metadata/
│       └── metadata_service.py    # (신규) LLM 기반 메타데이터 자동 추천
├── infrastructure/storage/
│   └── local_fs.py                # (수정) _parse_frontmatter() 추가, _to_wiki_file() 수정
└── ... (기존 유지)
```

---

## 수정된 구현 단계

### Phase 1 수정: 기존 완료 상태 반영

> **중요**: Step 2 (Wiki 인프라)와 Step 3 (Router + Registry)는 **이미 구현 완료**이다.
> frontmatter 파싱 통합은 Step 1-E에서 수행한다.

#### Step 0: 환경 세팅 (0.5h)
- [ ] Next.js 프로젝트 초기화 (`npx create-next-app@latest frontend --typescript --tailwind`)
- [ ] shadcn/ui 설치 + 필요 컴포넌트 추가 (Command, Badge, Button, Select, DropdownMenu, Popover)
- [ ] Next.js → 백엔드 프록시 설정 (`next.config.js` rewrites → `localhost:8001`)

#### Step 1-A: Tab Workspace 기반 레이아웃 (2h)
- [ ] Zustand 탭 상태 관리 (`useWorkspaceStore`)
- [ ] `TabBar` 컴포넌트 (열기, 닫기, 드래그 정렬, dirty 표시)
- [ ] `WorkspacePanel` + `FileRouter` (파일 타입별 분기)
- [ ] Tree Nav에서 파일 클릭 → 탭 열기 연동
- [ ] 3-Pane 레이아웃 (TreeNav + Workspace + AICopilot)

#### Step 1-B: Markdown Editor — Tiptap (2h)
- [ ] Tiptap 에디터 통합 (StarterKit + Table + Image + TaskList)
- [ ] WYSIWYG / 소스 모드 토글
- [ ] 슬래시 명령어 (`/`) 커스텀 extension
- [ ] 실시간 저장 (debounce + Ctrl+S)
- [ ] `PUT /api/wiki/{path}` 연동

#### Step 1-C: 클립보드 붙여넣기 (1.5h)
- [ ] 엑셀 표 붙여넣기 → HTML 테이블 → Tiptap Table 노드 변환
- [ ] 이미지 붙여넣기 → 백엔드 업로드 → `![](path)` 자동 삽입
- [ ] 이미지 드래그 앤 드롭 지원
- [ ] 백엔드 `POST /api/files/upload/image` 엔드포인트

#### Step 1-D: Multi-Format 뷰어 (2h)
- [ ] Excel 뷰어/에디터: Luckysheet 또는 Univer 통합
  - SheetJS로 `.xlsx` ↔ JSON 변환
  - 수정 후 저장 기능
- [ ] PPT 뷰어: pptxjs 기본 렌더링 (읽기 전용)
- [ ] PDF 뷰어: react-pdf 통합
- [ ] 이미지 뷰어: native `<img>` + 줌/패닝
- [ ] 백엔드 `/api/files/*` 바이너리 파일 CRUD 엔드포인트

#### Step 1-E: Metadata Tagging Pipeline (2.5h)
- [ ] **백엔드 — Storage Layer 수정**: `LocalFSAdapter._parse_frontmatter()` → `WikiFile.metadata` 채움
- [ ] **백엔드 — WikiFile 스키마 마이그레이션**: `tags` → `metadata.tags` property 호환
- [ ] **백엔드 — ChromaDB metadatas 확장**: 파이프 구분자 전략으로 list 필드 저장
- [ ] **백엔드 — Hybrid Search**: `ChromaWrapper.query_with_filter()` 메서드 (`where` clause)
- [ ] **백엔드 — 태그 조회 API**: `GET /api/metadata/tags` → 전체 고유 태그/도메인/프로세스 목록
- [ ] **백엔드 — AI Auto-Suggest API**: `POST /api/metadata/suggest` → LiteLLM 구조화 출력
- [ ] **프론트엔드 — MetadataTagBar**: 에디터 상단 태그 바 (shadcn Command + Badge)
- [ ] **프론트엔드 — TagInput**: 기존 태그 자동 완성 + 신규 태그 생성
- [ ] **프론트엔드 — AutoTagButton**: ✨ AI 추천 → 점선 Badge로 추천 표시 → 수락/거절
- [ ] **프론트엔드 — Frontmatter 동기화**: 저장 시 MetadataTagBar 상태 → YAML frontmatter 갱신

#### Step 1-F: AI Copilot + SSE 스트리밍 (1.5h)
- [ ] SSE 클라이언트 (`fetch` + `ReadableStream`)
- [ ] AICopilot 채팅 UI (메시지 목록 + 입력)
- [ ] 스트리밍 토큰 실시간 표시
- [ ] `[승인 / 거절]` 버튼 연동 (`POST /api/approval/resolve`)

#### Step 2: Wiki 인프라 → ✅ 이미 구현 완료
> WikiService, WikiIndexer, WikiSearchService, Storage 어댑터, ChromaDB 래퍼 모두 완성.
> frontmatter 파싱 통합은 Step 1-E에서 수행.

#### Step 3: Main Router + ToolRegistry → ✅ 이미 구현 완료
> 2-tier intent classification, ToolRegistry 플러그인 아키텍처, SSE 스트리밍 엔드포인트 완성.
> 검증: 다양한 자연어 입력으로 라우팅 테스트만 필요.

#### Step 4: Wiki 샘플 데이터 마이그레이션 + 통합 테스트 (1h)
- [ ] 기존 wiki 3개 문서에 YAML frontmatter 추가 (현재는 `#tag` 형식만 있음)
- [ ] 전체 재색인 후 Hybrid Search 검증
- [ ] 프론트엔드 ↔ 백엔드 E2E 검증 (3-Pane UI → 채팅 → 라우팅 → RAG 답변)

### Phase 1 전체 타임라인 (수정)

| Step | 내용 | 상태 | 예상 시간 |
|------|------|------|-----------|
| Step 0 | 프론트엔드 환경 세팅 (Next.js + shadcn/ui) | 미구현 | 0.5h |
| **Step 1-A** | **Tab Workspace 레이아웃** | 미구현 | **2h** |
| **Step 1-B** | **Tiptap MD 에디터** | 미구현 | **2h** |
| **Step 1-C** | **클립보드 붙여넣기** | 미구현 | **1.5h** |
| **Step 1-D** | **Multi-Format 뷰어** | 미구현 | **2h** |
| **Step 1-E** | **Metadata Tagging Pipeline** | 미구현 | **2.5h** |
| **Step 1-F** | **AI Copilot + SSE 스트리밍** | 미구현 | **1.5h** |
| Step 2 | Wiki 인프라 | ✅ 완료 | - |
| Step 3 | Main Router + ToolRegistry | ✅ 완료 | - |
| Step 4 | 샘플 데이터 마이그레이션 + 통합 테스트 | 미구현 | 1h |
| | **총 남은 작업** | | **~13.5h** |

---

## Phase 2-A: RAG 성능 고도화 (검색 품질 + 응답 속도)

> Phase 1 완료 후, 문서가 대량으로 증가했을 때도 사용자 체감 성능을 유지하기 위한 고도화.
> 우선순위 순서대로 진행. 각 Step은 독립적으로 배포 가능.

### 배경

현재 RAG 파이프라인은 **질문 1건당 LLM 최대 3회 호출** (라우팅 + 쿼리보강 + 명확화 + 답변)하며,
벡터 유사도만으로 검색하고, 전체 리인덱싱만 지원합니다.
문서 100건 이하에서는 문제없지만, 1,000~10,000건 이상이면 아래 병목이 발생합니다:

- **응답 지연**: 첫 글자까지 최악 7.5초 (LLM 직렬 호출)
- **검색 누락**: 이름/코드 등 정확 매칭에 벡터 유사도가 약함
- **리인덱싱 병목**: 전체 재처리로 문서 1만건 시 수십 분 소요
- **반복 질문 낭비**: 동일 질문도 매번 임베딩 + LLM 호출

### Step P2A-1: LLM 호출 병렬화 + 제거 (난이도: 낮, 효과: 대)

> 목표: 첫 글자까지 대기 시간 **7.5s → 3~4s** (약 50% 단축)

| # | Task | 의존 | 산출물 |
|---|------|------|--------|
| P2A-1-1 | 라우팅과 쿼리보강을 `asyncio.gather`로 병렬 실행 | - | `agent.py`, `rag_agent.py` |
| P2A-1-2 | 명확화 확인을 규칙 기반으로 전환 (LLM 호출 제거) — 검색 결과 관련도 + 질문 길이 + 히스토리 유무로 판단 | - | `rag_agent.py` |
| P2A-1-3 | 라우팅 Tier 1 키워드 매칭 커버리지 확대 → LLM 폴백 빈도 최소화 | - | `router.py` |
| P2A-1-4 | 성능 벤치마크 스크립트 — 각 단계별 소요 시간 로깅 + 리포트 | - | `tests/bench_rag_latency.py` |

### Step P2A-2: 하이브리드 검색 — 벡터 + BM25 (난이도: 중, 효과: 대)

> 목표: "김태헌", "DG320" 같은 **정확 매칭 검색 정확도 대폭 향상**

| # | Task | 의존 | 산출물 |
|---|------|------|--------|
| P2A-2-1 | BM25 인덱스 구축 — `rank_bm25` 라이브러리 도입, Wiki 문서 토큰화 + 인덱스 생성 | - | `infrastructure/search/bm25.py` |
| P2A-2-2 | 하이브리드 검색 모듈 — 벡터 결과 + BM25 결과를 RRF(Reciprocal Rank Fusion)로 병합 | P2A-2-1 | `infrastructure/search/hybrid.py` |
| P2A-2-3 | RAG Agent에서 기존 `chroma.query` → `hybrid_search` 교체 | P2A-2-2 | `rag_agent.py` |
| P2A-2-4 | BM25 인덱스 자동 갱신 — 문서 저장/삭제 시 동기화 | P2A-2-1 | `wiki_indexer.py`, `bm25.py` |
| P2A-2-5 | 검색 품질 비교 테스트 (벡터 only vs 하이브리드) | P2A-2-3 | `tests/test_hybrid_search.py` |

### Step P2A-3: 증분 인덱싱 (난이도: 낮, 효과: 중~대)

> 목표: 리인덱싱 **수분 → 수초** (1만건 기준)

| # | Task | 의존 | 산출물 |
|---|------|------|--------|
| P2A-3-1 | 파일 해시(content hash) 기반 변경 감지 — 해시 저장소 (SQLite or JSON) | - | `infrastructure/storage/file_hash.py` |
| P2A-3-2 | `index_file` 호출 전 해시 비교 → 변경 없으면 스킵 | P2A-3-1 | `wiki_indexer.py` |
| P2A-3-3 | `remove_file` 개선 — metadata `where` 필터 기반 삭제 (chunk ID 50개 고정 → 정확 삭제) | - | `wiki_indexer.py`, `chroma.py` |
| P2A-3-4 | 리인덱싱 API에 `force` 파라미터 추가 (force=false → 증분, force=true → 전체) | P2A-3-2 | `wiki.py` |

### Step P2A-4: 임베딩/검색 결과 캐싱 (난이도: 낮, 효과: 중)

> 목표: 반복 질문 **즉시 응답** + OpenAI API 비용 절감

| # | Task | 의존 | 산출물 |
|---|------|------|--------|
| P2A-4-1 | 쿼리 해시 기반 인메모리 LRU 캐시 (TTL 5분) — 검색 결과 캐싱 | - | `infrastructure/cache/query_cache.py` |
| P2A-4-2 | RAG Agent에서 벡터 검색 전 캐시 히트 확인 | P2A-4-1 | `rag_agent.py` |
| P2A-4-3 | 캐시 무효화 — 문서 저장/삭제 시 관련 캐시 클리어 | P2A-4-1 | `wiki_indexer.py`, `query_cache.py` |
| P2A-4-4 | 캐시 히트율 모니터링 로그 | P2A-4-2 | `query_cache.py` |

### Step P2A-5: 메타데이터 사전 필터링 (난이도: 중, 효과: 중)

> 목표: 1만건 → 수백건으로 **검색 범위 축소**, 노이즈 감소

| # | Task | 의존 | 산출물 |
|---|------|------|--------|
| P2A-5-1 | 질문에서 domain/process 키워드 자동 추출 — 규칙 기반 (LLM 미사용) | - | `application/agent/filter_extractor.py` |
| P2A-5-2 | 추출된 필터를 ChromaDB `where` 절로 변환 → `query_with_filter` 활용 | P2A-5-1 | `rag_agent.py` |
| P2A-5-3 | 필터링 결과 0건이면 필터 제거 후 재검색 (fallback) | P2A-5-2 | `rag_agent.py` |
| P2A-5-4 | 사용 중인 domain/process 목록 캐싱 (메타데이터 통계 API) | - | `wiki.py`, `chroma.py` |

### Step P2A-6: Cross-encoder 리랭킹 (난이도: 중, 효과: 중)

> 목표: 검색 상위 결과 **정확도 10~20% 향상**

| # | Task | 의존 | 산출물 |
|---|------|------|--------|
| P2A-6-1 | Cross-encoder 모델 선정 + 래퍼 구현 (sentence-transformers or LLM 기반) | - | `infrastructure/search/reranker.py` |
| P2A-6-2 | RAG Agent에서 벡터 검색 후 상위 N건 리랭킹 → 최종 컨텍스트 구성 | P2A-6-1 | `rag_agent.py` |
| P2A-6-3 | 리랭킹 on/off 설정 + 지연 시간 로깅 | P2A-6-2 | `config.py`, `reranker.py` |
| P2A-6-4 | A/B 비교 테스트 (리랭킹 유무별 답변 품질) | P2A-6-2 | `tests/test_reranker.py` |

### Phase 2-A 전체 타임라인

| Step | 내용 | Task 수 | 난이도 | 핵심 효과 |
|------|------|---------|--------|-----------|
| P2A-1 | LLM 호출 병렬화 + 제거 | 4 | 낮 | 응답속도 50%↑ |
| P2A-2 | 하이브리드 검색 (BM25) | 5 | 중 | 정확 매칭 정확도↑↑ |
| P2A-3 | 증분 인덱싱 | 4 | 낮 | 리인덱싱 수분→수초 |
| P2A-4 | 임베딩/검색 캐싱 | 4 | 낮 | 반복질문 즉시, 비용↓ |
| P2A-5 | 메타데이터 사전 필터링 | 4 | 중 | 대규모 노이즈 감소 |
| P2A-6 | Cross-encoder 리랭킹 | 4 | 중 | 정확도 10~20%↑ |
| | **합계** | **25 tasks** | | |

> **권장 순서**: P2A-1 → P2A-2 → P2A-3 → P2A-4 → P2A-5 → P2A-6
> P2A-1~3은 독립적이므로 병렬 진행 가능. P2A-5는 P2A-2 이후가 효과적.

---

## Phase 2-B: 문서 충돌 감지 & 해소 (사용자 의사결정 지원)

### 배경

사내 Wiki에서 같은 주제의 문서가 여러 버전으로 존재할 때, 사용자가 어떤 문서를 신뢰해야 할지 판단할 수 있도록 지원하는 시스템. RAG 답변부터 관리 도구까지 5단계에 걸쳐 점진적으로 구현.

### 아키텍처 개요

```
[P2B-1] 프롬프트 충돌 감지          ← RAG 답변에서 즉시 충돌 표시 (최소 변경)
    ↓
[P2B-2] 메타데이터 신뢰도           ← status 필드 + 소스 패널 개선 (판단 근거 제공)
    ↓
[P2B-3] 중복 감지 대시보드          ← 임베딩 유사도 기반 자동 탐지 (관리자 도구)
    ↓
[P2B-4] 인라인 비교 뷰             ← Side-by-side diff (상세 비교)
    ↓
[P2B-5] 문서 계보 시스템            ← supersedes/superseded_by/related (근본 해결)
```

### Step P2B-1: RAG 답변 충돌 감지 프롬프트 (4 tasks)

현재 RAG 답변 컨텍스트에는 문서 본문만 포함. 메타데이터(수정일/작성자)를 함께 주입하고, LLM이 문서 간 모순을 감지하면 사용자에게 경고.

- **P2B-1-1**: `_build_context_with_metadata()` — 각 문서 청크에 `[출처: path, 작성자: X, 수정일: Y]` 헤더 삽입
- **P2B-1-2**: `FINAL_ANSWER_SYSTEM_PROMPT` 충돌 감지 규칙 — "여러 문서가 다른 내용을 담고 있으면 ⚠️ 충돌 감지 섹션 추가, 최신 문서 권고"
- **P2B-1-3**: `COGNITIVE_REFLECT_PROMPT` — self_critique에 "CONFLICT CHECK" 항목 추가
- **P2B-1-4**: `ConflictWarningEvent` SSE 이벤트 + 프론트엔드 경고 배너

**핵심 변경**: `rag_agent.py`의 context 구성 로직에서 `relevant_docs`와 함께 `metadatas`도 보존해서 헤더 생성에 활용.

### Step P2B-2: 메타데이터 기반 신뢰도 표시 (5 tasks)

문서 생명주기 상태(draft → review → approved → deprecated)를 frontmatter로 관리하고, RAG 소스 패널에 신뢰도 시그널 표시.

- **P2B-2-1**: `DocumentMetadata.status` 필드 + 파싱/직렬화
- **P2B-2-2**: ChromaDB 인덱서에 `status` 반영
- **P2B-2-3**: `SourceRef` 확장 (updated, updated_by, status) + `_build_sources()` 주입
- **P2B-2-4**: 프론트엔드 소스 패널 — status 아이콘 (approved=✓, deprecated=⚠), 날짜 배지, "최신" 라벨
- **P2B-2-5**: MetadataTagBar에 status 드롭다운

### Step P2B-3: 문서 중복/충돌 감지 대시보드 (5 tasks)

ChromaDB 임베딩으로 문서 간 유사도를 계산해 중복/유사 문서 쌍을 자동 감지. 관리자가 병합/폐기/주석 처리.

- **P2B-3-1**: `ChromaWrapper.get_all_embeddings()` — collection.get(include=["embeddings", "metadatas"])
- **P2B-3-2**: `ConflictDetectionService` — 파일별 임베딩 평균 → 코사인 유사도 → threshold(0.85) 클러스터링
- **P2B-3-3**: `GET /api/conflict/duplicates` — 유사 문서 쌍 + 유사도 점수
- **P2B-3-4**: `POST /api/conflict/deprecate` — 문서 status 변경
- **P2B-3-5**: `ConflictDashboard` VirtualTab — 유사 문서 테이블, 비교/폐기/병합 액션

**신규 파일**: `backend/application/conflict/conflict_service.py`, `backend/api/conflict.py`, `frontend/ConflictDashboard.tsx`

### Step P2B-4: 인라인 비교 뷰 (5 tasks)

두 문서를 나란히 놓고 차이점을 하이라이트. 대시보드 또는 RAG 답변에서 "비교" 액션으로 접근.

- **P2B-4-1**: `GET /api/wiki/compare` — 두 문서 body + 메타데이터
- **P2B-4-2**: `DiffViewer` — diff npm 패키지, 추가(녹)/삭제(적)/변경(황) 하이라이트
- **P2B-4-3**: `"document-compare"` VirtualTab + `openCompareTab(pathA, pathB)`
- **P2B-4-4**: "이 문서가 최신" 버튼 → 상대 문서 deprecated + superseded_by 설정
- **P2B-4-5**: ConflictDashboard + RAG 답변 "비교" 액션 연동

### Step P2B-5: 문서 계보(Lineage) 시스템 (5 tasks)

frontmatter로 문서 간 관계를 추적. 대체된 문서는 RAG 검색에서 자동 감점.

- **P2B-5-1**: `DocumentMetadata`에 `supersedes`, `superseded_by`, `related` 필드
- **P2B-5-2**: RAG 검색 시 superseded 문서 패널티 (relevance × 0.5) + "새 버전 있음" 노트
- **P2B-5-3**: `GET /api/wiki/lineage/{path}` — 계보 트리 (ancestors/descendants/related)
- **P2B-5-4**: `LineageWidget` — 에디터 하단에 이전/새 버전, 관련 문서 링크
- **P2B-5-5**: 저장 시 자동 lineage 제안 — 유사 문서 감지 → "새 버전인가요?" 프롬프트

### Phase 2-B 전체 타임라인

| Step | 내용 | Tasks | 난이도 | 핵심 효과 |
|------|------|-------|--------|-----------|
| P2B-1 | RAG 충돌 감지 프롬프트 | 4 | 낮 | 즉시 충돌 인지 |
| P2B-2 | 메타데이터 신뢰도 표시 | 5 | 중 | 판단 근거 제공 |
| P2B-3 | 중복/충돌 감지 대시보드 | 5 | 중 | 사전 예방 관리 |
| P2B-4 | 인라인 비교 뷰 | 5 | 중 | 상세 비교 도구 |
| P2B-5 | 문서 계보 시스템 | 5 | 높 | 근본적 해결 |
| | **합계** | **24 tasks** | | |

> **권장 순서**: P2B-1 → P2B-2 → P2B-3 → P2B-4 → P2B-5
> P2B-1은 독립, P2B-4/5는 P2B-3 이후 병렬 가능.

---

## 핵심 npm 패키지 목록

```json
{
  "dependencies": {
    "@tiptap/react": "latest",          // Tiptap React 바인딩
    "@tiptap/starter-kit": "latest",    // 기본 extension 번들
    "@tiptap/extension-table": "latest",
    "@tiptap/extension-image": "latest",
    "@tiptap/extension-task-list": "latest",
    "@tiptap/extension-task-item": "latest",
    "@tiptap/extension-placeholder": "latest",
    "luckysheet": "latest",             // Excel 뷰어/에디터 (또는 @univerjs/core)
    "xlsx": "latest",                   // SheetJS — Excel 파일 파싱
    "pptxjs": "latest",                 // PPT 뷰어
    "react-pdf": "latest",             // PDF 뷰어
    "@dnd-kit/core": "latest",         // 탭 드래그 앤 드롭
    "zustand": "latest"                 // 상태 관리
  }
}
```

shadcn/ui 필요 컴포넌트: `Command`, `Badge`, `Button`, `Select`, `DropdownMenu`, `Popover`, `Dialog`, `Toast`

---

## 변경 이력

| 날짜 | 변경 내용 |
|------|----------|
| 2025-03-25 | 초기 작성 — Workspace 고도화 요구사항 4건 반영 |
| 2025-03-25 | Metadata Tagging Pipeline 요구사항 2건 추가 (#5, #6) |
| 2025-03-25 | **코드 검토 반영** — 아래 8건 수정: |
| | (A) WikiFile 스키마 호환성: `tags` property로 하위 호환 유지 |
| | (B) Frontmatter 파싱 위치: Storage Layer 단일 책임으로 통합 |
| | (C) ChromaDB list 저장: 파이프 구분자 전략 명시 (`\|tag\|` 패턴) |
| | (D) MD 에디터 라이브러리: Milkdown → Tiptap으로 변경 (문서화, shadcn 궁합) |
| | (E) API 역할 구분: `/api/wiki/*`(MD) vs `/api/files/*`(바이너리) 명시 |
| | (F) Step 2 (Wiki 인프라) 이미 완료 → 타임라인에서 제거 |
| | (G) Step 3 (Router) 이미 완료 → 타임라인에서 제거 |
| | (H) 누락 보완: shadcn/ui 패키지, SSE 클라이언트(Step 1-F), 에러 핸들링, 샘플 데이터 마이그레이션 |
| 2026-03-26 | **인증 추상화 레이어 추가** — Backend/Frontend Provider Pattern 도입: |
| | - Backend: `backend/core/auth/` (AuthProvider ABC, NoOpProvider, factory, deps) |
| | - Frontend: `frontend/src/lib/auth/` (AuthContext, useAuth, DevAuthProvider, useAuthFetch) |
| | - 전체 API 라우터에 router-level `Depends(get_current_user)` 적용 |
| | - 상세 가이드: `toClaude/reports/auth_abstraction_guide.md` |
| 2026-03-26 | **Phase 2-A: RAG 성능 고도화 계획 추가** — 6 Steps, 25 Tasks: |
| | - P2A-1: LLM 호출 병렬화 + 제거 (응답속도 50%↑) |
| | - P2A-2: 하이브리드 검색 BM25 + 벡터 (정확 매칭↑↑) |
| | - P2A-3: 증분 인덱싱 (리인덱싱 수분→수초) |
| | - P2A-4: 임베딩/검색 캐싱 (반복질문 즉시, 비용↓) |
| | - P2A-5: 메타데이터 사전 필터링 (대규모 노이즈 감소) |
| | - P2A-6: Cross-encoder 리랭킹 (정확도 10~20%↑) |
