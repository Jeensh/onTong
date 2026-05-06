# OD-11-D2-1 Step Summary — Manual Ingest 5-Format Parsers

**완료일** : 2026-04-20
**범위** : `backend/modeling/manual_ingest/` 신규 패키지. 5 포맷 파서 (md/pdf/docx/pptx/image) + `ManualParser` Protocol + `ManualParseResult` DTO + FQN/checksum helpers.
**Spec** : `toClaude/modeling/round3-manual-gap.html` rev.2 §6-1.
**선행** : D1.6 (parser_protocol Round 3 concept kinds 등록).
**다음** : D2-2 (`pipeline.py` + `manual_registry.py` + 업로드 REST/SSE API) → D2-3 (watch folder + git hook + 프런트 업로드 UI).

---

## 1. 왜 3 서브로 나눴는가 (D2 분할)

사용자 승인 (`응 진행해`) 이후에도 D2 umbrella 의 범위가 과다 (deps 4종 + 파서 5종 + pipeline + UI + watch + git hook). 1 스텝에 묶으면 검증 지연과 회귀 리스크. 따라서 :

- **D2-1 (이 스텝)** : 포맷 → `ManualParseResult` 변환 (이 스텝 완료).
- **D2-2** : checksum dedup → chromadb 임베딩 → Neo4j 기록 + 업로드 API.
- **D2-3** : 3 트리거 wiring (UI 업로드 + watch folder + git hook, Q7=E).

각 서브는 독립 검증 가능 + 중간 데모 가능.

---

## 2. 산출물 (6 신규 + 1 편집)

### 편집

- **`pyproject.toml`** — `[tool.poetry.dependencies]` 에 `pypdf ^5.0` / `pdfplumber ^0.11` / `python-docx ^1.2` / `python-pptx ^1.0` 추가. `python -m ensurepip` 으로 venv pip 복구 후 `python -m pip install` 로 실제 venv 에 설치.

### 신규 (backend)

- **`backend/modeling/manual_ingest/__init__.py`** — 패키지 진입점. Protocol + helpers 재노출.
- **`backend/modeling/manual_ingest/parser_protocol.py`** (~115 LOC) :
  - `_slugify(value)` — 영숫자 외 `-` 치환 + 빈 문자열 `section` fallback
  - `make_document_fqn(path)` → `manual.<stem slug>`
  - `make_section_fqn(doc_fqn, heading_path, order_index)` → `<doc>#<h-slug>/.../<n>`
  - `make_fragment_fqn(section_fqn, order_index)` → `<sec>:f<n>`
  - `compute_checksum(path, chunk_size=65536)` → SHA-256 hex
  - `ManualParseResult` (frozen Pydantic : document / sections / fragments / warnings)
  - `@runtime_checkable ManualParser(Protocol)` (`format: str` + `parse(path) -> ManualParseResult`)
- **`md_parser.py`** (~175 LOC) — heading-stack 기반 섹션 분할. `_chunk_body()` 로 paragraph / code fence / table 모드 전환 (TEXT / TABLE Fragment 분리). heading 없으면 doc stem 으로 단일 섹션 fallback.
- **`pdf_parser.py`** (~95 LOC) — `pypdf.PdfReader` 로 페이지별 `extract_text()` → 1 페이지 = 1 Section (`Page N`) + TEXT Fragment 1개. 추출 예외는 warning 누적.
- **`docx_parser.py`** (~120 LOC) — `Heading N` 스타일 정규식 (`^Heading\s+(\d+)$`) 으로 섹션 분할 + blank line 기준 TEXT Fragment 분리. 문서 타이틀은 첫 `Heading 1` 텍스트 > `path.stem` fallback.
- **`pptx_parser.py`** (~95 LOC) — `python-pptx` 슬라이드 순회. 1 슬라이드 = 1 Section (`slide.shapes.title.text` 없으면 `Slide N`). 타이틀 외 shape.text_frame 을 `\n\n` 으로 합쳐 TEXT Fragment 1개.
- **`image_parser.py`** (~95 LOC) — `ImageParser(ocr_engine=None)` 주입 constructor (None → `OCREngine()` 기본). `asyncio.run(ocr.extract_text(path))` 호출 — dict/str 양쪽 허용하는 파서 경계 어댑터. 성공 시 OCR_TEXT Fragment 1개 (`image_ref=str(path)`), 실패 (Exception) 시 Fragment 생략 + warning 누적.

### 신규 (tests)

- **`tests/_manual_ingest_fixtures.py`** — fixture helper 3종 :
  - `make_pdf(path, pages_text)` — `pypdf.PdfWriter.add_blank_page` + `DecodedStreamObject` 에 Helvetica Type1 폰트 참조 + content stream (`BT /F1 12 Tf 72 720 Td (text) Tj ET`). reportlab 없이 결정적 생성.
  - `make_docx(path, title, headings)` — python-docx `Document.add_heading(level)` + `add_paragraph`.
  - `make_pptx(path, slides)` — python-pptx Title-and-Content 레이아웃.
- **6 테스트 파일 총 48 tests** :
  - `test_manual_ingest_parser_protocol.py` 11 (FQN helpers 한글/공백 포함, checksum 결정성/차이/SHA-256 hex 형식, ParseResult frozen)
  - `test_manual_ingest_md_parser.py` 13 (heading path 계층, TEXT/TABLE/CODE fragment 분리, fragment order_index per-section 재시작, no-heading fallback, empty file)
  - `test_manual_ingest_pdf_parser.py` 6 (single/multi-page, section/fragment 참조, checksum hex, doc_fqn stem)
  - `test_manual_ingest_docx_parser.py` 6 (단일 heading, 계층 depth, TEXT fragment, section_fqn 참조 무결성, stem)
  - `test_manual_ingest_pptx_parser.py` 6 (1/다중 슬라이드, body fragment, section 참조, order_index 슬라이드 순서)
  - `test_manual_ingest_image_parser.py` 7 (`_FakeOCREngine` dataclass 스텁 주입, 단일 section + OCR_TEXT fragment, 실패 시 warning + fragment 생략, OCR 빈 문자열 시 fragment 존재 + text 비어있음, default constructor OCREngine 인스턴스)

---

## 3. 설계 결정

### 3.1 DI + Protocol (ImageParser)

`ImageParser.__init__(ocr_engine=None)` — 테스트는 `_FakeOCREngine` 주입, 프로덕션은 `OCREngine()` 기본. 이는 tesseract 바이너리 없어도 단위 테스트 결정적이도록 보장. 실제 OCREngine 반환 타입은 `str` 이지만 테스트 스텁은 `dict` 를 반환 — 이 불일치는 **파서 경계 어댑터 (isinstance 분기)** 로 흡수해 pipeline 이 아닌 parser 안에서 표준화.

### 3.2 FQN 계층 설계

`manual.<stem>#<h-slug>/<h-slug>:<n>:f<n>` — 3-level 구조 :
- `manual.` 접두어로 코드/개념 FQN 과 격리.
- heading path 가 slug 단계에 녹아있어 LLM 이 URL-safe 하게 다룰 수 있음.
- `:<n>` order_index 로 안정 정렬 (동일 heading 반복 허용).
- `:f<n>` fragment 접미사로 섹션 내 프래그먼트 식별.

### 3.3 pypdf 저수준 PDF fixture

reportlab 등 고수준 PDF 생성 라이브러리를 추가하지 않고 `pypdf` 만으로 fixture 생성. `DecodedStreamObject` 에 직접 content stream 기록 + Helvetica 폰트 참조로 pypdf 역-round-trip 검증. 이유 : D2-2 이후에도 pypdf 만 사용 예정이라 fixture 가 동일 스택에서 결정적으로 동작해야 검증 신뢰도 확보.

### 3.4 D2 3-subphase 분할

D2 umbrella 범위가 너무 크다는 판단. D2-1 (파서) → 데모 가능, D2-2 (pipeline + UI), D2-3 (트리거) 로 점진 완성. 사용자 승인 `응 진행해` 이후에도 부담 관리 위해 subscope 분리.

### 3.5 ManualFragmentKind 할당 규칙

- MD : 일반 단락/코드펜스 → `TEXT`, 파이프 테이블 → `TABLE`
- PDF : 페이지 전체 → `TEXT` (표/이미지는 D2-2 또는 D2-3 pdfplumber 확장에서 분리)
- DOCX : paragraph → `TEXT` (docx 테이블/이미지 분리는 D2-2 에서)
- PPTX : 슬라이드 body → `TEXT`
- IMAGE : OCR 결과 → `OCR_TEXT` (빈 문자열이어도 Fragment 존재, `image_ref` 로 원본 참조)

D1.5 ManualFragmentKind enum 5종 중 이번 스텝에서 3종 사용 (`TEXT`/`TABLE`/`OCR_TEXT`). `IMAGE`/`FORMULA` 는 D2-2 pdfplumber/pandoc 파이프에서 사용 예정.

---

## 4. 검증

### 4.1 단위 (D2-1 범위)

```
.venv/bin/python -m pytest tests/test_manual_ingest_parser_protocol.py \
    tests/test_manual_ingest_md_parser.py \
    tests/test_manual_ingest_pdf_parser.py \
    tests/test_manual_ingest_docx_parser.py \
    tests/test_manual_ingest_pptx_parser.py \
    tests/test_manual_ingest_image_parser.py -v
```

→ **48 passed in 0.35s** (PASS).

### 4.2 회귀 (모델링 범위)

```
.venv/bin/python -m pytest tests/ -k "modeling or manual or concept_resolver or parser or ontology or graph_writer or neo4j_adapter or business_term or business_rule or domain_rule" -q
```

→ **251 passed, 1110 deselected in 4.12s** (PASS).

### 4.3 회귀 (전체 suite)

전체 1340 PASS / 21 FAIL. 실패 21건은 전부 Section 1 wiki/RAG/skill 영역 (`test_ag23_skill_feedback` / `test_ag33_hooks` / `test_auto_tag_quality` / `test_confidence` / `test_lineage_validation` / `test_p2b6_deprecated_filter` / `test_pydantic_ai_migration` / `test_rag_tag_boost` / `test_skill_api`). D2-1 이 추가한 회귀 없음. Section Isolation 규칙에 따라 wiki 영역은 본 세션 범위 밖.

### 4.4 데모 (demo_guide.md)

`toClaude/modeling/demo_guide.md` 에 `D-OD-11-D2-1` 섹션 추가 : 5 REPL 시나리오 (MD / PDF / DOCX / PPTX / Image 성공+실패+기본 OCR) + pytest 명령 + 체크리스트 10행 + 트러블슈팅 5행.

---

## 5. 미해결 / 다음 스텝 메모

- **pdfplumber 미사용** : 이번 스텝에선 pypdf 만 사용. pdfplumber 는 D2-2 또는 D2-3 에서 표 심화 추출 (MES 설비보전 점검표 등) 에 쓸 예정.
- **DOCX 표 파싱 미구현** : python-docx 의 `document.tables` 접근은 D2-2 에 추가 (현재는 paragraph 기반 TEXT 만).
- **PDF 이미지 분리 미구현** : 현재는 페이지 전체 텍스트만. D2-2/D2-3 에서 pdfplumber + embedded image 분리 + OCR 재귀 검토.
- **MD frontmatter (YAML) 처리 미구현** : Obsidian 스타일 `---` frontmatter 는 TEXT Fragment 로 흘러감. D2-2 pipeline 에서 `ManualDocument.version` 등 메타 추출 로직 추가 예정.
- **asyncio.run 경계** : ImageParser.parse() 는 sync 가정. D2-2 pipeline 이 async 컨텍스트에서 호출할 경우 `asyncio.to_thread` 로 감싸야 함.

---

## 6. 커밋 준비 파일 목록

```
backend/modeling/manual_ingest/__init__.py       [신규]
backend/modeling/manual_ingest/parser_protocol.py [신규, D2-1 이전 D1.7 로 편입 가능하나 편의상 동반]
backend/modeling/manual_ingest/md_parser.py       [신규]
backend/modeling/manual_ingest/pdf_parser.py      [신규]
backend/modeling/manual_ingest/docx_parser.py     [신규]
backend/modeling/manual_ingest/pptx_parser.py     [신규]
backend/modeling/manual_ingest/image_parser.py    [신규]
tests/_manual_ingest_fixtures.py                  [신규]
tests/test_manual_ingest_parser_protocol.py       [신규]
tests/test_manual_ingest_md_parser.py             [신규]
tests/test_manual_ingest_pdf_parser.py            [신규]
tests/test_manual_ingest_docx_parser.py           [신규]
tests/test_manual_ingest_pptx_parser.py           [신규]
tests/test_manual_ingest_image_parser.py          [신규]
pyproject.toml                                    [편집: deps 4 추가]
toClaude/modeling/TODO.md                         [편집: D2-1 [x] + D2 서브로우 분할]
toClaude/modeling/CHANGES.md                      [편집: D2-1 엔트리 추가]
toClaude/modeling/HANDOFF.md                      [편집: D2-1 완료 반영 + 다음 세션 D2-2 안내]
toClaude/modeling/demo_guide.md                   [편집: D2-1 REPL + 체크리스트 + 트러블슈팅]
toClaude/modeling/log/step_d2_1_summary.md        [신규 (이 파일)]
```

---

## 7. 다음 스텝 진입 조건 (D2-2)

- 사용자 승인 (`응 진행해` 등) 필요.
- 선행 확인 : D2-1 48 tests PASS, 모델링 회귀 251 PASS.
- 신규 의존성 불필요 (chromadb / neo4j 클라이언트는 Section 1 + Round 1 에 이미 존재).
- 기존 `graph_writer.py` 를 재사용 (D1.6 에서 concept 레지스트리에 Manual* kinds 등록 완료 → 화이트리스트 자동 통과).
