# onTong 데모 가이드 (Step 0 ~ Skill System 고도화)

---

## 사전 준비

### 1. Node 20 확인

```bash
export NVM_DIR="$HOME/.nvm" && [ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"
nvm use 20
node -v  # v20.x.x 이어야 함
```

### 2. 백엔드 실행

```bash
cd /Users/donghae/workspace/ai/onTong

# Docker (ChromaDB) — 필수
docker compose up -d chroma

# Python 가상환경 + 백엔드
source venv/bin/activate
uvicorn backend.main:app --port 8001 --reload
```

> 백엔드가 정상이면 `curl http://localhost:8001/health` 에서 `"chroma_connected": true` 확인.
> 만약 `chroma_docs: 0`이면 `curl -X POST http://localhost:8001/api/wiki/reindex` 실행.

### 3. 프론트엔드 실행 (새 터미널)

```bash
cd /Users/donghae/workspace/ai/onTong/frontend
export NVM_DIR="$HOME/.nvm" && [ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"
nvm use 20
npm run dev
```

> `http://localhost:3000` 에서 앱이 뜹니다.

---

## 데모 시나리오

### A. 3-Pane 레이아웃 확인 (Step 1-A)

1. 브라우저에서 `http://localhost:3000` 접속
2. **3개 영역** 확인: 좌측(Wiki 트리) | 중앙(Workspace) | 우측(AI Copilot)
3. 패널 경계선을 **드래그**해서 너비 조절 해보기
4. 중앙에 "파일을 선택하세요" 빈 상태 메시지 확인

### B. 파일 트리 + 탭 (Step 1-A)

1. 좌측 트리에서 `getting-started.md` 클릭 → **탭 1개 생성**
2. `order-processing-rules.md` 클릭 → **탭 2개**
3. 첫 번째 탭 클릭 → **콘텐츠 전환**
4. 탭을 **드래그**해서 순서 변경
5. 두 번째 탭의 **✕** 클릭 → 탭 닫힘
6. 마지막 탭의 **✕** 클릭 → "파일을 선택하세요" 빈 상태

### B-1.5. 빈 공간 우클릭 (Step 1-A)

1. 사이드바에서 **파일/폴더가 없는 빈 공간**을 **우클릭**
2. 컨텍스트 메뉴에 **새 문서** / **새 폴더** 두 항목 표시
3. **새 문서** 클릭 → 루트 레벨에 인라인 입력란 → 파일명 입력 → Enter
4. **새 폴더** 클릭 → 루트 레벨에 인라인 입력란 → 폴더명 입력 → Enter
5. 파일/폴더 위에서 우클릭하면 기존처럼 이름 변경/삭제 메뉴도 함께 표시

### B-2. 파일 생성/삭제 (Step 1-A)

1. 사이드바 헤더의 **📄+ 새 문서** 버튼 클릭 → 인라인 입력란 표시
2. 파일명 입력 (예: `테스트문서`) → **Enter** → 파일 생성 + 트리 새로고침 + 탭 자동 열림
3. `.md` 확장자는 자동 추가됨 확인
4. 생성된 파일을 **우클릭** → 컨텍스트 메뉴에서 **삭제** 클릭
5. 확인 다이얼로그 → 확인 → 파일 삭제 + 트리 새로고침 + 열린 탭 자동 닫힘

### B-3. 폴더 생성/삭제 (Step 1-A)

1. 사이드바 헤더의 **📁+ 새 폴더** 버튼 클릭 → 인라인 입력란 표시
2. 폴더명 입력 (예: `매뉴얼`) → **Enter** → 폴더 생성 + 트리 새로고침
3. 생성된 폴더를 **우클릭** → 컨텍스트 메뉴에서 **새 문서** 클릭 → 폴더 안에 파일 생성
4. 폴더 **우클릭** → **새 폴더** 클릭 → 하위 폴더 생성
5. 빈 폴더 **우클릭** → **폴더 삭제** → 삭제 확인
6. 파일이 있는 폴더 삭제 시도 → "폴더가 비어있지 않습니다" 에러 표시
7. **↻ 새로고침** 버튼으로 트리 갱신 확인

### B-4. 드래그앤드롭 이동 (Step 1-A)

1. 파일을 클릭한 채로 **드래그** (약 8px 이상 이동해야 드래그 활성화됨)
2. 폴더 위로 끌어다 놓기 → **파란색 하이라이트** 확인 → 드롭
3. "📄 파일명 이동됨" Toast 확인 + 트리 새로고침
4. **루트 레벨**로 이동: 트리 빈 공간(하단)으로 드롭
5. 폴더도 다른 폴더 안으로 드래그앤드롭 가능

> 드래그 중에는 **반투명 원본 + 부유 칩**이 함께 표시됩니다.

### B-5. 이름 변경 (Step 1-A)

1. 파일 또는 폴더를 **우클릭** → 컨텍스트 메뉴에서 **이름 변경** 클릭
2. 인라인 입력란에 현재 이름이 선택된 상태로 표시됨 (확장자 앞까지 선택)
3. 새 이름 입력 → **Enter**
4. `.md` 확장자 없이 입력해도 자동으로 `.md` 추가됨
5. 해당 파일이 탭에 열려있었다면 **탭 경로도 자동 업데이트** 됨

### C. Markdown 에디터 (Step 1-B)

1. 트리에서 `.md` 파일 클릭 → **에디터에 콘텐츠 로드**
2. 텍스트를 선택하고 **Ctrl+B** → 굵은 글씨 토글
3. 빈 줄에서 `# ` 입력 → Heading 1 스타일 적용
4. 툴바의 **테이블 버튼** (격자 아이콘) 클릭 → 3x3 테이블 삽입

### D. WYSIWYG ↔ 소스 모드 (Step 1-B)

1. 툴바 우측의 **`< >` 아이콘** 클릭 → Markdown 소스 텍스트 표시
2. 소스에서 `**테스트**` 추가
3. 다시 **눈 아이콘** 클릭 → WYSIWYG로 돌아오면 "테스트"가 굵게 표시

### E. 슬래시 명령어 (Step 1-B)

1. 에디터에서 **빈 줄 시작**에 `/` 입력 → 드롭다운 메뉴 표시
2. `/h` 타이핑 → Heading 항목만 필터링
3. `Heading 2` 선택 → 블록 삽입
4. **Escape** → 메뉴 닫힘
5. 줄 중간에서 `/` 입력 → 메뉴가 **뜨지 않음** (정상)

### F. 저장 (Step 1-B)

1. 에디터에서 텍스트 추가 → 탭에 **주황색 ●** 표시 (dirty)
2. **Ctrl+S** → "저장 완료" Toast 메시지 + ● 사라짐
3. 브라우저 **새로고침** → 같은 파일 열기 → 수정 내용 유지 확인
4. (선택) 편집 후 3초간 입력 안 하면 **자동 저장** 동작

### G. 클립보드 테이블 붙여넣기 (Step 1-C)

1. **Excel** 또는 **Google Sheets**에서 셀 범위를 선택하고 **Ctrl+C**
2. 에디터에서 빈 줄에 **Ctrl+V** → Tiptap 테이블 노드로 삽입
3. 첫 행이 **헤더(굵은 글씨)**로 표시되는지 확인
4. 표에서 **우클릭** → 행/열 추가, 셀 병합/분할 등 컨텍스트 메뉴 확인
5. 일반 텍스트 붙여넣기는 기존처럼 동작하는지도 확인

### H. 이미지 붙여넣기 (Step 1-C)

1. 화면 스크린샷 캡처: **macOS** `Cmd+Ctrl+Shift+4` → 영역 선택 (클립보드에 복사됨)
2. 에디터에서 **Ctrl+V** (또는 Cmd+V) → 이미지 업로드 후 에디터에 이미지 표시
3. 이미지가 보이면 성공 — 실제 파일은 `wiki/assets/` 디렉토리에 저장됨

> ⚠️ 이미지 테스트는 **백엔드가 실행 중**이어야 합니다 (`POST /api/files/upload/image` 필요)

### I. 이미지 드래그 앤 드롭 (Step 1-C)

1. Finder에서 **PNG/JPG 이미지 파일**을 에디터 영역으로 **드래그**
2. 드롭하면 이미지 업로드 후 에디터에 이미지 표시
3. `wiki/assets/`에 업로드된 파일 확인: `ls wiki/assets/`

### J. Excel 뷰어 (Step 1-D)

> ⚠️ 테스트하려면 `wiki/` 디렉토리에 `.xlsx` 파일이 필요합니다.
> 없으면 아무 Excel 파일을 `wiki/` 폴더에 복사하세요: `cp ~/Downloads/sample.xlsx wiki/`

1. 좌측 트리에서 `.xlsx` 파일 클릭 → **스프레드시트 뷰어** 열림
2. 행번호(1, 2, 3…)와 열 헤더(A, B, C…) 확인
3. 셀을 **더블클릭** → 값 수정 → Enter 또는 다른 셀 클릭
4. 여러 시트가 있으면 상단 **시트 탭** 클릭으로 전환
5. **Ctrl+S** 또는 **저장 버튼** → "저장 완료" Toast
6. 브라우저 새로고침 후 같은 파일 열기 → 수정 내용 유지 확인

### K. 이미지 뷰어 (Step 1-D)

> ⚠️ 테스트하려면 `wiki/` 디렉토리에 이미지 파일이 필요합니다.
> 없으면: `cp ~/Downloads/sample.png wiki/`

1. 좌측 트리에서 `.png`/`.jpg` 등 이미지 파일 클릭 → **이미지 뷰어** 열림
2. **마우스 휠** → 줌 인/아웃 (0.1x ~ 5x)
3. **마우스 드래그** → 이미지 패닝 (이동)
4. 툴바 **+/−** 버튼 → 줌 조절
5. **1:1** 버튼 → 원래 크기 + 위치 초기화

### L. Metadata TagBar (Step 1-E)

1. 트리에서 `.md` 파일 클릭 → 에디터 **상단에 Metadata 바** 표시
2. **"Metadata"** 텍스트 클릭 → 접기/열기 토글
3. **Domain** 드롭다운에서 값 선택 (기본 옵션: SCM, QC, 생산, 물류, 영업, 회계, IT, HR)
4. **Process** 드롭다운에서 값 선택 (기본 옵션: 주문처리, 입고, 출고, 검수, 재고관리, 배송, 정산)
5. **Tags** 영역에 태그 입력 → Enter로 태그 추가 (자동 완성은 기존 태그가 있을 때 표시)
6. 태그 Badge의 **✕** 클릭 → 태그 제거
7. `.xlsx` 파일 열기 → MetadataTagBar가 **표시되지 않음** (정상)

### M. Auto-Tag AI 추천 (Step 1-E)

> ⚠️ OpenAI API 키가 `.env`에 설정되어 있어야 합니다 (`OPENAI_API_KEY`)

1. `.md` 파일을 열고 본문에 내용이 있는 상태에서 **✨ Auto-Tag** 버튼 클릭
2. 로딩 스피너 → 추천 태그가 **점선 테두리 Badge**로 표시
3. 각 Badge의 **✓** (초록) → 수락 → 실선 Badge로 전환
4. 각 Badge의 **✕** (빨강) → 거절 → Badge 제거
5. **"모두 수락"** 클릭 → 모든 추천 태그 일괄 수락

### N-0. 문서 이력 자동 관리 (생성일/수정일/작성자)

> 저장 시 백엔드가 자동으로 타임스탬프와 작성자 정보를 frontmatter에 주입합니다.

1. 새 문서를 생성하고 내용 작성 후 **Ctrl+S** 저장
2. MetadataTagBar 하단에 **작성자**, **생성일**, **최종 수정자**, **최종 수정일** 표시 확인
3. 터미널에서 `head -15 wiki/{파일명}.md` → frontmatter에 자동 추가된 필드 확인:
   ```yaml
   ---
   created_by: 개발자
   updated_by: 개발자
   created: '2026-03-26T12:00:00Z'
   updated: '2026-03-26T12:00:00Z'
   ---
   ```
4. 내용을 수정하고 다시 **Ctrl+S** → `updated` 시간만 변경되고 `created`는 유지 확인
5. (사내 도입 후) 다른 사용자가 수정하면 `updated_by`가 해당 사용자 이름으로 변경됨

### N. Frontmatter 저장/로드 (Step 1-E)

1. Metadata 수정 후 **Ctrl+S** → 저장
2. 터미널에서 `head -15 wiki/{파일명}.md` → YAML frontmatter 확인:
   ```yaml
   ---
   domain: SCM
   process: 주문처리
   tags:
     - 주문 처리
     - 재고 관리
   error_codes:
     - DG320
   ---
   ```
3. 브라우저 **새로고침** → 같은 파일 열기 → MetadataTagBar에 저장한 값 유지

### O. AI Copilot 채팅 (Step 1-F)

> ⚠️ 백엔드 실행 + ChromaDB 연결 + 인덱싱 완료 필요
> `curl http://localhost:8001/health` → `chroma_connected: true, chroma_docs: 10+` 확인

1. 우측 **AI Copilot** 패널에 "Wiki에 대해 질문해보세요" 안내 확인
2. 입력란에 **"주문 처리 규칙 알려줘"** 입력 → Enter (또는 전송 버튼)
3. **스트리밍 답변** 확인: 토큰이 하나씩 나타남 + 커서 깜빡임
4. 답변 상단에 **출처 문서** 링크 확인 (예: `order-processing-rules.md`)
5. 출처 링크 **클릭** → 중앙 Workspace에 해당 파일 탭이 열림
6. 다른 질문 시도: **"DG320 에러 어떻게 해결했어?"**

### P. AI Copilot 스트리밍 중지 (Step 1-F)

1. 질문을 입력하고 전송
2. 답변이 스트리밍되는 동안 **빨간 ■ 중지 버튼** 클릭
3. 스트리밍이 즉시 중단됨

### Q. AI Copilot 문서 생성 + 승인 (Step 1-F)

1. **"캐시 장애 대응 문서 만들어줘"** 입력
2. AI가 문서 내용을 생성하고 **미리보기**를 표시
3. 점선 테두리 박스에 **경로** + **미리보기 내용** + **승인/거절 버튼** 확인
4. **승인** 클릭 → "문서가 생성되었습니다" Toast + 좌측 트리에 새 파일 표시 (트리 새로고침 필요 시 F5)
5. **거절** 클릭 → "요청이 거절되었습니다" Toast

### R. AI Copilot 명확화 질문 (Step 1-F)

> 질문이 모호하거나 관련 문서의 유사도가 낮으면, AI가 바로 답변하지 않고 되물어봅니다.

1. **"알려줘"** 또는 **"도와줘"** 같은 짧고 모호한 질문 입력
2. AI가 "더 정확한 답변을 위해 확인이 필요합니다" 라는 명확화 질문을 표시
3. 명확화 질문에 대한 **구체적인 답변** 입력 (예: "주문 처리 규칙이 궁금해")
4. 이번에는 대화 히스토리를 참고하여 **정상적인 RAG 답변**이 생성됨

### S. AI Copilot 대화 히스토리 (Step 1-F)

> 같은 세션 내에서 이전 대화 맥락을 기억합니다.

1. **"주문 처리 규칙 알려줘"** 입력 → 답변 확인
2. 이어서 **"거기서 FIFO 원칙에 대해 더 자세히 알려줘"** 입력
3. AI가 이전 대화 맥락(주문 처리 규칙)을 참고하여 FIFO 관련 답변 생성

### T. AI Copilot 에러 처리 (Step 1-F)

1. 백엔드를 **중지**한 상태에서 질문 입력
2. "서버 연결 실패" Toast 메시지 확인
3. 백엔드 재시작 후 다시 질문 → 정상 응답 확인

### U. AI Copilot 일반 질문 라우팅 (세션 5 고도화)

> "포스코 OJT 진행중인 사람" 같은 일반 검색 질문도 WIKI_QA로 라우팅됩니다.

1. Wiki에 인사 정보 등 일반 문서가 있는 상태에서 시작
2. **"포스코 ojt 진행중인 사람을 찾아줘"** 입력
3. 라우팅 결과가 **WIKI_QA**로 표시되는지 확인 (이전: UNKNOWN)
4. RAG가 관련 문서를 검색하여 **구체적인 답변** 생성
5. 추가 테스트: **"누가 담당자야?"**, **"재고 관련 내용 알려줘"** 등 일반 질문

### V. AI Copilot 구조화 데이터 검색 + 후속 질문 (세션 5 고도화)

> 인사정보 같은 구조화된 문서에서도 정보를 정확히 추출합니다.

1. Wiki에 인사 정보 문서 (이름/소속/직책 등) 저장
2. **"후판 공정계획 관련 질문 누구에게 해야해?"** 입력
3. **김태헌** 등 해당 담당자 이름과 소속이 구체적으로 답변되는지 확인
4. 후속 질문: **"담당자 누구 있는지 좀 찾아줘"** 입력
5. 이전 맥락(후판 공정계획)을 반영하여 관련 인물 정보를 답변하는지 확인

> 인덱싱 변경 후에는 `curl -X POST http://localhost:8001/api/wiki/reindex` 실행 필요

### W-0. Self-Reflective Cognitive Pipeline (세션 5)

> 에이전트가 답변을 그대로 내보내지 않고, 내부적으로 분석→초안→자기검토를 거쳐 최종 답변을 생성합니다.

1. 아무 질문 입력 (예: **"후판 공정계획 담당자 알려줘"**)
2. UI 탐색 과정에 **🧠 의도 분석 및 답변 검토 중** 단계가 표시됨
3. 최종 답변이:
   - **결론을 첫 문장에** 제시하는지 확인 (Minto Pyramid)
   - **공감 표현**이 포함되는지 확인 ("후판 공정계획 관련 담당자를 찾으시는군요")
   - **실행 가능한 다음 단계**를 제안하는지 확인 ("XX에게 직접 연락해보시겠어요?")
4. 백엔드 터미널에서 `COGNITIVE PIPELINE — INTERNAL LOG` 확인:
   - `🧠 INTERNAL THOUGHT`: 영문 의도 분석
   - `📝 DRAFT RESPONSE`: 한국어 초안
   - `🔍 SELF-CRITIQUE`: 영문 자기 검토

> **중요**: UI에는 최종 답변만 표시됨. 내부 사고/초안/검토는 절대 프론트엔드에 노출되지 않음.

### W. RAG 탐색 과정 시각화 (세션 5)

> 에이전트가 답변을 생성하는 과정을 실시간으로 볼 수 있습니다.

1. 아무 질문이나 입력 (예: **"후판 공정계획 담당자 알려줘"**)
2. 답변 생성 전에 **탐색 과정** 패널이 나타남:
   - `🔍 관련 문서 검색 중...` → `✅ 문서 검색 완료 — 8건 (최고 관련도 72%)`
   - `✏️ 답변 생성 중...` → `✅ 답변 생성 완료`
3. 답변이 완료되면 탐색 과정이 **자동 접힘** → `▶ 탐색 과정 (3단계 완료)` 클릭으로 다시 펼침
4. 후속 질문 시 **쿼리 보강** 단계도 추가로 표시됨:
   - `⚡ 검색 쿼리 보강 중...` → `✅ 쿼리 보강 완료 — "후판 공정계획 담당자"`

---

## 인증 추상화 (Auth Abstraction)

> 현재는 NoOp/Dev provider로 인증 없이 동작합니다.
> 사내 도입 시 provider만 교체하면 됩니다.

### 현재 동작 확인

1. 별도 로그인 없이 앱이 정상 동작하는 것 확인 (NoOp provider)
2. 백엔드 로그에 `Auth provider: noop` 메시지 확인

### 인증 교체 시 변경 포인트

| 위치 | 파일 | 변경 내용 |
|------|------|----------|
| Backend | `backend/core/auth/{name}_provider.py` | AuthProvider 구현 |
| Backend | `backend/core/auth/factory.py` | elif 분기 추가 |
| Backend | `.env` | `AUTH_PROVIDER={name}` |
| Frontend | `frontend/src/lib/auth/{name}-provider.ts` | AuthProvider 구현 |
| Frontend | `frontend/src/components/Providers.tsx` | provider 교체 |

> 상세 가이드: `toClaude/reports/auth_abstraction_guide.md`

---

## 문제가 생겼을 때

| 증상 | 원인 | 해결 |
|------|------|------|
| 트리가 "트리 로드 실패" | 백엔드 미실행 | `uvicorn backend.main:app --port 8001` 실행 |
| 트리가 비어있음 | wiki 디렉토리 없음 | `ls wiki/` 확인 — `.md` 파일 있어야 함 |
| 에디터 "로드 실패" | API 프록시 문제 | 프론트 `npm run dev` 재시작, 백엔드 포트 8001 확인 |
| `nvm: command not found` | nvm 미로드 | `export NVM_DIR="$HOME/.nvm" && . "$NVM_DIR/nvm.sh"` |
| `npm run dev` 실패 | Node 18 사용 중 | `nvm use 20` 먼저 실행 |
| 이미지 붙여넣기 안됨 | 백엔드 미실행 | `uvicorn backend.main:app --port 8001` 확인 |
| 이미지 업로드 에러 | 파일 타입 미지원 | PNG, JPEG, GIF, WebP, SVG만 허용 (최대 10MB) |
| 테이블 붙여넣기 안됨 | 일반 텍스트로 복사됨 | Excel/Sheets에서 셀을 선택 후 Ctrl+C (텍스트 복사 아님) |
| xlsx 파일이 트리에 안보임 | wiki/에 xlsx 없음 | `cp ~/Downloads/sample.xlsx wiki/` 후 새로고침 |
| xlsx 수정 후 저장 안됨 | 브라우저 캐시 | 강력 새로고침 (Cmd+Shift+R) 후 재시도 |
| MetadataTagBar 안보임 | .md가 아닌 파일 | .md 파일에서만 표시됨 (정상 동작) |
| Auto-Tag "추천 실패" | LLM API 키 미설정 | `.env`에 `OPENAI_API_KEY` 설정 확인 |
| Domain/Process 드롭다운 비어있음 | - | 기본 옵션이 항상 표시됨. 안 보이면 프론트 재시작 |
| 태그 입력 시 글자 쪼개짐 | 한국어 IME 이슈 | 최신 코드 확인 (isComposing 체크 추가됨) |
| AI Copilot "관련 문서 없음" | ChromaDB 인덱스 없음 | `curl -X POST http://localhost:8001/api/wiki/reindex` 실행 |
| AI Copilot "서버 연결 실패" | 백엔드 미실행 | 백엔드 재시작, `curl http://localhost:8001/health` 확인 |
| 드래그앤드롭이 클릭으로 반응함 | 드래그 거리 미달 | 8px 이상 드래그해야 DnD 모드 활성화 |
| 이름 변경 후 탭 경로 안바뀜 | updateTabPath 미작동 | 프론트 재시작 (`npm run dev`) |
| 폴더 이동 후 하위 파일 인덱스 오류 | 전체 reindex 필요 | `curl -X POST http://localhost:8001/api/wiki/reindex` 실행 |
| AI Copilot 답변이 안나옴 | ChromaDB 미연결 | `docker compose up -d chroma` → 백엔드 재시작 |
| AI Copilot "LLM 호출 실패" | OpenAI API 키 문제 | `.env`의 `OPENAI_API_KEY` 확인, 잔액 확인 |
| AI Copilot 명확화 질문이 너무 자주 나옴 | LOW_RELEVANCE_THRESHOLD가 낮음 | `rag_agent.py`에서 `LOW_RELEVANCE_THRESHOLD` 값 조정 (기본 0.55) |
| AI Copilot 대화 맥락을 모름 | 세션 미연결 | 같은 브라우저 탭에서 대화해야 히스토리 유지 |
| 승인 후 파일 안보임 | 트리 자동 갱신 미구현 | 브라우저 새로고침 (F5) |

---

## Step 4 통합 테스트 시나리오

### U. 전체 E2E 흐름 (Step 4-5)

> Phase 1 전체 기능을 한 번에 검증하는 통합 시나리오

1. `http://localhost:3000` 접속 → 3-Pane 레이아웃 확인
2. 좌측 트리에서 `getting-started.md` 클릭 → 탭 생성 + 에디터 로드
3. MetadataTagBar에 기존 태그 (인사/직원정보/포스코) 표시 확인
4. 우측 AI Copilot에 **"주문 처리 규칙 알려줘"** 입력 → 스트리밍 답변
5. 답변 하단 출처 `order-processing-rules.md` 링크 클릭 → 새 탭으로 열림
6. 해당 파일의 Domain: SCM, Process: 주문처리 메타데이터 확인

### V. Auto-Tag + 저장 + 검색 흐름 (Step 4-6)

1. `getting-started.md` 탭 선택
2. **✨ Auto-Tag** 버튼 클릭 → 점선 Badge로 추천 태그 표시
3. **"모두 수락"** 클릭 → 실선 Badge로 전환 + ● dirty 표시
4. **Ctrl+S** → 저장 완료
5. 터미널에서 `head -15 wiki/getting-started.md` → 새 태그가 frontmatter에 포함 확인
6. `curl -X POST http://localhost:8001/api/wiki/reindex` → 재인덱싱
7. AI Copilot에서 관련 질문 → RAG 답변 정상 확인

### W. Multi-Format 뷰어 통합 (Step 4-7)

1. 좌측 트리에서 `신규1` 폴더 펼치기 → `예제모음.xlsx` 클릭
2. 스프레드시트 뷰어 열림 → 시트 탭 (기본화면, 엑셀데이터 등) 전환
3. `assets` 폴더 펼치기 → `.png` 파일 클릭 → 이미지 뷰어 열림
4. 줌 (+/−/1:1) 버튼 동작 확인

### X. PDF 뷰어 (Phase 1.5)

1. wiki 디렉토리에 샘플 PDF 파일 업로드 (또는 `assets/` 폴더에 배치)
2. 좌측 트리에서 `.pdf` 파일 클릭 → PDF 뷰어 열림
3. 페이지 네비게이션: ◀ ▶ 버튼 또는 키보드 ←→ 화살표
4. 페이지 번호 직접 입력하여 이동
5. 줌: − / + 버튼으로 50%~200% 조절
6. 50페이지 이상 PDF: 하단 페이지 그룹(50개 단위) 전환 버튼 확인

### Y. 프레젠테이션 뷰어 (Phase 1.5)

1. 좌측 트리에서 `onTong-프로젝트-소개.pptx` ���릭 → PPTX 뷰어 열림
2. 슬라이드 네비게이션: ◀ ▶ 버튼 또는 키보드 ←→ 화살표
3. Home/End 키로 첫/마지막 슬라이드 이동, Space로 다음 슬라이드
4. Bold/Italic/색상 텍스트, 이미지가 정상 표시되는지 확인
5. 백엔드 python-pptx 파싱 → 프론트엔드 HTML/CSS 렌더링 방식

### Z. 사이드바 섹션 전환 + 메타데이터 관리 (Phase 2)

1. 사이드바 상단에 3개 아이콘 탭 확인: 파일 트리 / 태그 브라우저 / 관리
2. **태그 브라우저**: Tags 아이콘 클릭 → Domain/Process/Tags 목록 표시
3. 태그 클릭 → 해당 태그가 달린 문서 목록 표시 → 문서 클릭 시 탭으로 열림
4. **관리**: Settings 아이콘 클릭 → "메타데이터 템플릿" / "미태깅 문서" 메뉴
5. "메타데이터 템플릿" 클릭 → Workspace에 관리 탭 열림 → Domain/Process/Tags 추가·삭제
6. "미태깅 문서" 클릭 → 미태깅 목록 + 태그 통계 → "일괄 자동 태깅" 버튼
7. 에러코드 자동 추출: DG320 등이 본문에 있는 문서 저장 시 frontmatter에 자동 주입 확인

### AA. RAG 성능 고도화 — LLM 호출 병렬화 + 제거 (Phase 2-A Step 1)

#### AA-1. 키워드 라우팅 속도 체감 (브라우저)

1. `http://localhost:3000` 접속 → AI Copilot (On-Tong Agent) 열기
2. **한글 질문 입력**: "출장 경비 규정 알려줘"
   - ✅ 기대: thinking step의 첫 단계(라우팅)가 거의 즉시 넘어감 (키워드 매칭 ~0ms)
3. **다양한 한글 질문 테스트** — 아래 모두 키워드 라우팅 되어야 함 (빠른 응답 시작):
   - "재고관리 프로세스 설명해줘"
   - "OJT 진행 절차"
   - "서버 점검 안내"
   - "김태헌"  (이름 검색)
4. **영어 질문 테스트**: "What is onTong?"
   - ✅ 기대: LLM 폴백으로 ~1-2초 더 걸림 (라우팅 단계에서 체감 가능)

#### AA-2. 후속 질문 병렬화 확인 (브라우저)

1. 새 세션 시작 (세션 목록에서 + 버튼)
2. 첫 질문: "캐시 장애 대응 매뉴얼 알려줘"
   - 답변이 오면 thinking step 확인 (일반적인 flow)
3. **후속 질문**: "담당자가 누구야?"
   - ✅ 기대: thinking step에 **"쿼리 보강 완료 (병렬)"** 표시
   - 라우팅과 쿼리보강이 동시에 실행되어 기존보다 빠른 응답 시작

#### AA-3. 모호한 질문 → 규칙 기반 명확화 (브라우저)

1. 새 세션에서 매우 짧은 질문 입력: "뭐야"
   - ✅ 기대: 검색 결과가 poor할 경우 규칙 기반으로 즉시 명확화 질문 제시
   - LLM 호출 없이 "Wiki에서 관련 문서를 찾았습니다..." + 선택지 목록
   - (검색 결과가 있을 경우에만 발동, 없으면 "관련 문서를 찾지 못했습니다" 메시지)

#### AA-4. 벤치마크 스크립트 실행 (터미널)

```bash
cd ~/workspace/ai/onTong
source venv/bin/activate
python -m tests.bench_rag_latency
```

확인 포인트:
- **Keyword hits**: 11/12 이상 (한글 쿼리 전부 키워드 매칭)
- **LLM fallbacks**: 1/12 이하 (영어 쿼리만)
- **Routing mean**: 키워드 매칭 쿼리는 ~0ms
- **Parallel vs Sequential**: 후속 질문에서 병렬이 순차보다 빠른지 비교 출력

#### AA-5. 트러블슈팅

| 증상 | 원인 | 해결 |
|------|------|------|
| thinking step에 "병렬" 표시 안 됨 | 첫 질문임 (후속 아님) | 같은 세션에서 2번째 질문부터 병렬 작동 |
| 영어 질문도 즉시 응답 | 키워드에 매칭되는 영단어 포함 | 정상 — SCM, ERP 등은 키워드 매칭됨 |
| 벤치마크에서 vector_search 0건 | ChromaDB 인덱싱 안 됨 | `curl -X POST http://localhost:8001/api/wiki/reindex` 실행 후 재시도 |
| 백엔드 재시작 안 됨 | 포트 점유 | `lsof -ti :8001 \| xargs kill -9` 후 재시작 |

### AB. RAG 검색 고도화 (Phase 2-A Step 2~6)

#### AB-1. 하이브리드 검색 확인 (브라우저)

1. AI Copilot에서 "출장 경비 규정 알려줘" 입력
   - ✅ thinking step에 "문서 검색 완료 — N건 (**하이브리드**, 최고 관련도 XX%)" 표시
2. "캐시 장애 대응 매뉴얼" 입력 → 동일하게 "하이브리드" 표시 확인
3. 동일한 질문 다시 입력 → "**캐시**" 모드 표시 (검색 결과 캐싱 작동)

#### AB-2. 증분 인덱싱 확인 (터미널)

```bash
# 1차: force 전체 재인덱싱
curl -X POST "http://localhost:8001/api/wiki/reindex?force=true"
# → {"total_chunks": 90}  (전체 인덱싱)

# 2차: 증분 인덱싱 (변경 없으면 스킵)
curl -X POST "http://localhost:8001/api/wiki/reindex"
# → {"total_chunks": 0}  (모두 스킵)
```

#### AB-3. 메타데이터 필터링 확인 (브라우저)

1. "재고관리 프로세스 알려줘" → 백엔드 로그에 `Filter extracted: process=재고관리` 표시
2. "IT 시스템 보안 정책" → `Filter extracted: domain=IT`
3. 필터 매칭 안 되는 질문 ("김태헌") → 필터 없이 전체 검색

#### AB-4. 리랭킹 확인 (터미널)

```bash
source venv/bin/activate
python -m tests.test_reranker
```
- 리랭킹 전/후 순위 비교, 소요 시간 표시
- `config.py`에서 `enable_reranker=False`로 끄기 가능

#### AB-5. 검색 품질 비교 (터미널)

```bash
python -m tests.test_hybrid_search
```
- Vector vs BM25 vs Hybrid 결과 비교 (각 쿼리별 top-3)

#### AB-6. 트러블슈팅

| 증상 | 원인 | 해결 |
|------|------|------|
| "하이브리드" 대신 "벡터"만 표시 | BM25 인덱스가 비어있음 | `reindex?force=true` 실행 |
| 캐시 히트 안 됨 | 5분 TTL 만료 또는 문서 변경 | 정상 — 문서 저장 시 캐시 자동 무효화 |
| 리랭킹 느림 | LLM 호출 추가 | `enable_reranker=false`로 비활성화 가능 |

---

## Phase 2-B: 문서 충돌 감지 & 해소

> Phase 2-B 전체 기능을 순서대로 테스트하는 통합 데모입니다.
> BA-0에서 샘플 데이터를 준비하면, BA-1~BA-5를 **순서대로** 진행할 수 있습니다.

### BA-0. 데모용 샘플 데이터 준비

> 이미 Wiki에 문서가 있는 경우 기존 문서를 활용해도 됩니다.
> 아래는 **충돌/중복/계보** 기능을 모두 테스트하기 위한 최소 샘플입니다.

#### 방법 1: 터미널에서 샘플 문서 생성

```bash
cd ~/workspace/ai/onTong

# 1) 같은 주제 + 다른 내용 → 충돌 감지용
cat > wiki/출장비-기준-총무팀.md << 'EOF'
---
domain: GENERAL
process: 출장비
status: approved
tags:
  - 출장
  - 경비
---

# 출장비 기준 (총무팀 버전)

## 국내 출장
- 일비: **30,000원/일**
- 숙박비 상한: **100,000원/박**
- 교통비: 실비 정산 (KTX 일반석 기준)

## 해외 출장
- 일비: 국가별 차등 적용
- 항공: 이코노미 클래스 (부장급 이상 비즈니스)
EOF

cat > wiki/출장비-기준-재무팀.md << 'EOF'
---
domain: GENERAL
process: 출장비
tags:
  - 출장
  - 경비
---

# 출장비 기준 (재무팀 버전)

## 국내 출장
- 일비: **50,000원/일**
- 숙박비 상한: **150,000원/박**
- 교통비: 실비 정산 (KTX 특실 가능)

## 해외 출장
- 일비: 국가별 차등 적용
- 항공: 비즈니스 클래스 (임원 퍼스트)
EOF

# 2) 관련 문서 연결 테스트용
cat > wiki/재고관리-기준-v1.md << 'EOF'
---
domain: SCM
process: 재고관리
status: approved
tags:
  - 재고
  - 안전재고
related:
  - 재고관리-프로세스가이드.md
---

# 재고관리 기준 v1

## 안전재고 기준
- 일반 자재: **100개**
- 핵심 자재: **300개**
- 발주점(ROP): 안전재고 + 리드타임 소요량
EOF

cat > wiki/재고관리-기준-v2.md << 'EOF'
---
domain: SCM
process: 재고관리
tags:
  - 재고
  - 안전재고
related:
  - 재고관리-프로세스가이드.md
---

# 재고관리 기준 v2 (2026년 개정)

## 안전재고 기준
- 일반 자재: **200개** (기존 100개에서 상향)
- 핵심 자재: **500개** (기존 300개에서 상향)
- 발주점(ROP): 안전재고 × 1.2 + 리드타임 소요량

> 2026년 3월부터 적용. 기존 v1 기준은 폐기 예정.
EOF

# 3) 인덱싱
curl -X POST "http://localhost:8001/api/wiki/reindex?force=true"
```

#### 방법 2: 앱 UI에서 생성

1. `http://localhost:3000` 접속
2. 사이드바 **+** 버튼으로 위 4개 문서를 하나씩 생성
3. 내용 입력 후 **Ctrl+S** 저장 (저장 시 자동 인덱싱)

---

### BA-1. RAG 답변 충돌 감지 (P2B-1)

> AI에게 질문했을 때, 검색된 문서 간 **모순되는 내용**이 있으면 경고를 표시합니다.

#### 테스트 1: 충돌 감지 확인

1. On-Tong Agent에서 질문: **"출장비 기준이 어떻게 돼?"**
2. 확인사항:
   - 탐색 과정에 **"의도 분석 및 답변 검토 중"** 단계 표시
   - `출장비-기준-총무팀.md` (일비 3만원)과 `출장비-기준-재무팀.md` (일비 5만원) 모두 검색됨
   - 답변에 **문서 간 내용 차이** 언급 (금액 차이)
   - 충돌 감지 시: 답변과 소스 사이에 **amber 색상 경고 배너** 표시
3. 소스 링크 클릭 → 해당 문서 탭 열림

#### 테스트 2: 충돌 없는 경우

1. **"사내식당 이용 안내 알려줘"** 입력 (단일 주제)
2. 충돌 경고 배너가 **표시되지 않아야** 함

#### 테스트 3: 백엔드 로그 확인 (터미널)

```
# 백엔드 터미널에서 확인할 내용:
COGNITIVE PIPELINE — INTERNAL LOG
🧠 INTERNAL THOUGHT: ...
📝 DRAFT RESPONSE: ...
🔍 SELF-CRITIQUE: ...
```
- 각 청크 앞에 `[출처: ...]`, `[작성자: ... | 최종수정: ...]` 헤더
- `has_conflict: true`이면 `conflict_details`에 충돌 설명

#### BA-1 트러블슈팅

| 증상 | 원인 | 해결 |
|------|------|------|
| 충돌 경고가 안 나옴 | LLM이 충돌로 판단 안 함 | 두 문서의 숫자를 더 크게 차이나게 수정 |
| amber 배너 안 보임 | SSE 이벤트 미수신 | DevTools Network 탭 → EventStream에서 `conflict_warning` 확인 |
| 문서가 검색 안 됨 | 인덱싱 안 됨 | `curl -X POST http://localhost:8001/api/wiki/reindex?force=true` |

---

### BA-2. 메타데이터 신뢰도 표시 (P2B-2)

> 문서의 **status** (draft/review/approved/deprecated)가 소스 패널과 에디터에 시각적으로 표시됩니다.

#### 테스트 1: Status 드롭다운 설정

1. `출장비-기준-총무팀.md` 열기 → MetadataTagBar 클릭하여 펼치기
2. **Status** 드롭다운 확인 → `Approved` 선택 (이미 approved면 다른 값으로 변경 테스트)
3. **Ctrl+S** 저장
4. MetadataTagBar 접으면 → **녹색 `approved` 뱃지** 표시

#### 테스트 2: 소스 패널 status 아이콘

1. On-Tong Agent에서 **"출장비 기준 알려줘"** 질문
2. 답변 하단 소스 패널에서:
   - `approved` 문서: **녹색 체크 아이콘** + 녹색 테두리
   - 일반 문서 (status 미설정): 기존 파일 아이콘
   - 각 소스에 **마우스 hover** → tooltip에 작성자/수정일/status 표시
   - **날짜 뱃지** (MM-DD 형식) 표시

#### 테스트 3: Frontmatter 확인

```bash
head -5 wiki/출장비-기준-총무팀.md
# → status: approved 확인
```

#### BA-2 트러블슈팅

| 증상 | 원인 | 해결 |
|------|------|------|
| Status 드롭다운 안 보임 | MetadataTagBar 접혀있음 | 클릭하여 펼치기 |
| 소스에 status 아이콘 없음 | status 미설정 + reindex 안 됨 | status 설정 → 저장 → reindex |
| 저장 후 status 사라짐 | 직렬화 버그 | 소스 모드로 전환하여 frontmatter 직접 확인 |

---

### BA-3. 문서 중복/충돌 감지 대시보드 (P2B-3, CR 리팩토링)

> 문서 저장 시 ChromaDB HNSW 쿼리로 **증분 감지** → 대시보드 즉시 로드 (< 50ms).
> 리팩토링 완료: Batch O(n^2) 79초 → Incremental ~50ms/save.

#### 테스트 1: 대시보드 열기 (즉시 로드)

1. 사이드바 하단 **관리 탭** (Settings 아이콘, 세 번째 아이콘) 클릭
2. **"문서 충돌 감지"** (AlertTriangle 아이콘) 클릭
3. Workspace에 **충돌 감지 대시보드** 즉시 열림 (스피너 없음, store에서 읽기)
4. 상단에 **유사도 임계값** (기본 0.95) + **"새로고침"** + **"전체 스캔"** 버튼

#### 테스트 2: 저장 시 자동 감지

1. 유사한 내용의 문서 저장 (예: 출장비 관련)
2. 저장 완료 후 대시보드 **"새로고침"** 클릭
3. 새로 감지된 충돌 쌍이 표시됨 (별도 스캔 불필요)

#### 테스트 3: 전체 스캔

1. **"전체 스캔"** 버튼 클릭
2. 프로그레스 바 표시 (X / Y 파일)
3. 스캔 완료 시 "전체 스캔 완료" 토스트 + 자동 새로고침

#### 테스트 4: 액션 버튼

1. 문서 쌍에서 **"열기"** 클릭 → 해당 문서 에디터 탭 열림
2. **"나란히 비교"** 클릭 → 비교 뷰 탭 열림 (BA-4로 이어짐)
3. **"폐기(deprecated) 처리"** 클릭 → Toast + 해결됨 상태 즉시 반영

#### BA-3 트러블슈팅

| 증상 | 원인 | 해결 |
|------|------|------|
| 유사 문서 0건 | 아직 문서 저장 안 됨 (InMemory store 빈 상태) | "전체 스캔" 버튼 클릭하여 일괄 감지 |
| 유사 문서 0건 | 임계값이 너무 높음 | 임계값을 0.7~0.8로 낮추기 |
| 유사 문서 0건 | ChromaDB 인덱스 없음 | `curl -X POST http://localhost:8001/api/wiki/reindex?force=true` |
| 새로고침 반응 없음 | API 연결 실패 | 백엔드 실행 확인, `curl http://localhost:8001/api/conflict/duplicates` 테스트 |
| 전체 스캔 ~25초 소요 | 정상 (ChromaDB HNSW 파일 순회) | 백그라운드 실행, UI 차단 없음 |
| 서버 재시작 후 데이터 없음 | InMemory store 초기화됨 | 재인덱싱 중 자동 채워짐, 또는 "전체 스캔" 클릭 |

---

### BA-4. 인라인 비교 뷰 — Side-by-side Diff (P2B-4)

> 두 문서를 **나란히 비교**하고, 어느 쪽이 최신인지 지정할 수 있습니다.

#### 테스트 1: Side-by-side Diff 확인

1. BA-3 대시보드에서 `출장비-기준-총무팀.md` ↔ `출장비-기준-재무팀.md` 쌍의 **"나란히 비교"** 클릭
   (또는 다른 유사 문서 쌍)
2. Workspace에 비교 탭 열림: **좌측(A)** | **우측(B)**
3. **색상 코딩** 확인:
   - **녹색 배경**: B에만 있는 줄 (추가)
   - **빨간 배경**: A에만 있는 줄 (삭제)
   - **황색(amber) 배경**: 양쪽 다 있지만 내용이 다른 줄 (변경)
4. 상단 헤더: 파일명 + **status 뱃지** (approved/draft 등) + 수정일
5. 상단 우측: **"N줄 차이"** 표시

#### 테스트 2: 최신 문서 지정 (Deprecate + Lineage)

1. **"A가 최신 (B를 deprecated)"** 버튼 클릭
2. Toast: `출장비-기준-재무팀.md → deprecated`
3. 비교 뷰 자동 새로고침:
   - B 파일명 옆에 **(deprecated)** 빨간색 표시
   - B의 "B가 최신" 버튼 **비활성화** (이미 deprecated)
4. 터미널에서 확인:
   ```bash
   head -8 wiki/출장비-기준-재무팀.md
   # → status: deprecated
   # → superseded_by: 출장비-기준-총무팀.md

   head -8 wiki/출장비-기준-총무팀.md
   # → supersedes: 출장비-기준-재무팀.md
   ```
   (양방향 lineage 자동 설정)

#### BA-4 트러블슈팅

| 증상 | 원인 | 해결 |
|------|------|------|
| 비교 탭이 빈 화면 | API 실패 | `curl "http://localhost:8001/api/wiki/compare?path_a=출장비-기준-총무팀.md&path_b=출장비-기준-재무팀.md"` |
| "최신" 버튼 비활성화 | 이미 deprecated 상태 | 정상 동작 — 이중 deprecate 방지 |
| diff가 정확하지 않음 | line-by-line 방식 | 삽입/삭제가 많으면 줄 매칭이 어긋날 수 있음 (정상) |

---

### BA-5. 문서 계보(Lineage) 시스템 (P2B-5)

> 문서 간 **이전/새 버전** 관계와 **관련 문서** 링크를 자동으로 표시합니다.

#### 테스트 1: Lineage 위젯 — 폐기 문서 경고

> BA-4 테스트 2에서 `출장비-기준-재무팀.md`를 deprecated 처리한 상태에서 진행

1. `출장비-기준-재무팀.md` 열기
2. MetadataTagBar 아래에 **amber 경고 배너** 확인:
   - **"이 문서는 폐기되었습니다. 새 버전:"** + 클릭 가능한 링크
3. 링크 클릭 → `출장비-기준-총무팀.md` 탭 열림

#### 테스트 2: Lineage 위젯 — 이전 버전 링크

1. `출장비-기준-총무팀.md` 열기 (BA-4에서 "최신"으로 지정한 문서)
2. MetadataTagBar 아래에 **녹색 "이전 버전"** 링크 확인:
   - **"이전 버전:"** + `출장비-기준-재무팀.md` 링크 + **(deprecated)** 빨간 태그
3. 링크 클릭 → 폐기된 문서 탭 열림

#### 테스트 3: Related 문서 링크

> BA-0에서 `재고관리-기준-v1.md`, `v2.md`를 `related`로 연결한 상태에서 진행

1. `재고관리-기준-v1.md` 열기
2. MetadataTagBar 아래에 **"관련 문서:"** 링크 표시:
   - `재고관리-프로세스가이드.md` 링크
3. 링크 클릭 → 해당 문서 탭 열림

#### 테스트 4: RAG 검색에서 deprecated 문서 패널티

1. 인덱싱: `curl -X POST http://localhost:8001/api/wiki/reindex?force=true`
2. On-Tong Agent에서 **"출장비 기준 알려줘"** 질문
3. 확인사항:
   - `deprecated` 문서가 소스 패널에서 **하위 순위**로 밀림
   - deprecated 소스: **빨간 X 아이콘** + **취소선** + 빨간 테두리
   - `approved` 소스: **녹색 체크 아이콘** + 녹색 테두리
   - 답변이 최신(approved) 문서 내용을 우선 인용

#### 테스트 5: Frontmatter lineage 확인

1. deprecated 처리된 문서 열기 → 우측 하단 **소스 모드** 버튼 클릭
2. frontmatter 확인:
   ```yaml
   ---
   status: deprecated
   superseded_by: 출장비-기준-총무팀.md
   ---
   ```
3. 최신 문서 열기 → 소스 모드:
   ```yaml
   ---
   supersedes: 출장비-기준-재무팀.md
   ---
   ```
4. WYSIWYG 모드로 다시 전환 → Lineage 위젯 정상 표시 확인

#### BA-5 트러블슈팅

| 증상 | 원인 | 해결 |
|------|------|------|
| Lineage 위젯 안 보임 | lineage 필드 미설정 | BA-4 테스트 2를 먼저 실행하거나, frontmatter에 `superseded_by` 수동 추가 |
| "새 버전" 링크 클릭 안 됨 | 파일 경로 불일치 | `superseded_by` 값이 실제 wiki 내 파일 경로와 정확히 일치하는지 확인 |
| deprecated 문서가 상위 랭킹 | 패널티 미적용 | `reindex?force=true` 실행 (status가 ChromaDB에 반영되어야 함) |
| related 링크 안 보임 | lineage API 실패 | `curl http://localhost:8001/api/wiki/lineage/재고관리-기준-v1.md` 테스트 |

---

### BA-E2E. Phase 2-B 전체 E2E 흐름 (한 번에 테스트)

> 위 BA-1~5를 하나의 스토리로 이어서 테스트하는 시나리오입니다.

1. **[BA-0] 준비**: 샘플 문서 4개 생성 + reindex
2. **[BA-2] Status 설정**: `출장비-기준-총무팀.md` → Status `Approved` 설정 → Ctrl+S
3. **[BA-1] 충돌 감지**: On-Tong Agent에 "출장비 기준 알려줘" → 충돌 경고 확인
4. **[BA-3] 대시보드**: 관리 탭 → 문서 충돌 감지 → 유사 문서 쌍 검색
5. **[BA-4] 비교 뷰**: 출장비 문서 쌍 "나란히 비교" → diff 확인 → **"A가 최신"** 클릭
6. **[BA-5] 계보 확인**: deprecated 문서 열기 → amber 경고 배너 확인 → 최신 문서 링크 클릭
7. **[BA-6] RAG 재확인**: reindex → "출장비 기준 알려줘" 다시 질문 → **deprecated 소스가 아예 안 뜸** (소스 패널에서 완전 제외)
8. **[BA-7] 대시보드 해결 상태**: 문서 충돌 감지 탭 → 기본 "미해결" 탭에 deprecated 처리된 쌍이 사라짐 → "해결됨" 탭에서 확인 가능 → "전체" 탭에서 초록색 "해결됨" 뱃지 확인

> 전체 흐름 예상 소요 시간: 10~15분

### BA-6. RAG deprecated 필터링 (P2B-6)

> deprecated 문서가 검색 결과와 소스 패널에서 완전히 제외되는지 확인합니다.

**사전 조건**: BA-5까지 완료 (deprecated 문서 + 최신 문서가 존재하는 상태)

**테스트 1: deprecated 문서 소스 제외**
1. 관리 탭 → 인덱싱 → Reindex All
2. On-Tong Agent에 "출장비 기준 알려줘" 질문
3. 소스 패널에 deprecated 문서 (`출장비-기준-총무팀.md` 등)가 나타나지 않는지 확인
4. 최신 문서만 소스로 표시되어야 함

**테스트 2: superseded_by 체인 확인**
1. `재고관리-기준-v1.md` (deprecated, superseded_by: v2) 상태에서 재고 관련 질문
2. v1이 아닌 v2 문서가 소스로 표시되는지 확인

#### BA-6 트러블슈팅
- **deprecated 문서가 소스에 계속 보임**: reindex 후 다시 시도 (해시가 변경되어야 인덱싱 반영)
- **검색 결과 0건**: ChromaDB where 필터가 모든 문서를 제외했을 수 있음 → 필터 없이 재시도하는 fallback 로직 확인

### BA-7. 충돌 대시보드 해결 상태 (P2B-7)

> deprecated 처리로 해결된 충돌 쌍이 대시보드에서 올바르게 분류되는지 확인합니다.

**사전 조건**: BA-5까지 완료 (일부 문서 쌍이 deprecated → superseded_by 관계 설정됨)

**테스트 1: 미해결 탭 (기본)**
1. 관리 탭 → 문서 충돌 감지
2. 기본 "미해결" 탭이 선택됨
3. deprecated 처리로 해결된 쌍이 보이지 않아야 함
4. 아직 처리 안 된 쌍만 표시

**테스트 2: 해결됨 탭**
1. "해결됨" 탭 클릭
2. deprecated 처리된 쌍이 표시됨
3. 각 쌍에 초록색 체크 아이콘 + "해결됨" 뱃지 확인

**테스트 3: 전체 탭**
1. "전체" 탭 클릭
2. 미해결 + 해결됨 모든 쌍 표시
3. 해결된 쌍에만 "해결됨" 뱃지가 붙어있음

#### BA-7 트러블슈팅
- **해결됨 탭에 아무것도 없음**: 문서의 frontmatter에 `superseded_by` / `supersedes` 필드가 정확히 설정되었는지 확인
- **모든 쌍이 미해결로 표시**: `is_pair_resolved()` 함수가 파일 경로를 정확히 비교하는지 확인 (경로 형식 일치 필요)

---

## Phase 3: 문서 검색 + 문서 관계 그래프

---

### BA-8: 문서 검색 (커맨드 팔레트)

**테스트 1: Ctrl+K 키워드 검색**
1. `Ctrl+K` (Mac: `Cmd+K`) 누르기
2. 커맨드 팔레트가 오버레이로 열림
3. "주문" 입력 → 즉시 검색 결과 표시 (키워드 모드)
4. 결과에서 제목 하이라이트, 경로, 스니펫, 태그 뱃지 확인
5. 결과 클릭 → 해당 문서가 탭으로 열림
6. ESC로 팔레트 닫기

**테스트 2: 의미 검색**
1. 팔레트 열기 → "의미 검색" 버튼 클릭
2. "재고가 맞지 않을 때 어떻게 해야 하나요" 입력
3. 서버 사이드 하이브리드 검색 결과 표시 (로딩 스피너 → 결과)
4. 키워드 정확 매칭이 아닌 의미적으로 관련된 문서가 나오는지 확인

**테스트 3: TreeNav 검색 버튼**
1. 사이드바 헤더에 검색(돋보기) 아이콘 확인
2. 클릭 시 팔레트 열림

#### BA-8 트러블슈팅
- **인덱스 로딩 실패**: 백엔드 `/api/search/index` 응답 확인, reindex 실행
- **의미 검색 결과 없음**: ChromaDB 연결 + 인덱싱 상태 확인

---

### BA-9: 문서 관계 그래프 (검색 우선 UX)

**테스트 1: 검색 랜딩 페이지**
1. 사이드바 → 관리(설정) 탭 → "문서 관계 그래프" 클릭
2. 검색 입력창이 중앙에 표시됨 (전체 그래프 대신)
3. "문서를 검색하세요" 안내 텍스트 확인

**테스트 2: 문서 검색 → 그래프 진입**
1. 검색창에 키워드 입력 (예: "출장")
2. 200ms 디바운스 후 검색 결과 목록 표시 (제목, 경로, status 색상, 도메인)
3. 검색 결과 클릭 → 해당 문서 중심의 관계 그래프 표시
4. Enter키 → 첫 번째 결과 자동 선택

**테스트 3: 그래프 탐색**
1. 노드 클릭 → 해당 문서가 새 탭으로 열림
2. 노드 우클릭 → 컨텍스트 메뉴 ("새 탭에서 열기", "이 문서 중심으로 보기")
3. "이 문서 중심으로 보기" → 해당 문서 중심으로 그래프 재렌더링

**테스트 4: 인라인 문서 전환**
1. 그래프 뷰 상단 툴바에서 검색 입력창 사용
2. 다른 문서명 입력 → 드롭다운에서 선택 → 중심 문서 변경
3. "다른 문서 검색" 버튼 → 검색 랜딩 페이지로 복귀

**테스트 5: 호버 툴팁**
1. 노드 위에 마우스 올리기
2. 제목, 경로, status 뱃지, 도메인, 태그, 연결 수 표시

**테스트 6: 유사도 엣지**
1. 툴바에서 "유사도" 토글 클릭
2. 임베딩 유사도 기반 dotted 빨간 엣지가 추가되는지 확인

**테스트 7: 깊이 조절**
1. 깊이 드롭다운을 1 → 3으로 변경
2. 더 많은 노드/엣지가 표시됨

#### BA-9 트러블슈팅
- **검색 결과 없음**: 백엔드 `/api/search/quick` 확인, BM25 인덱스가 빌드되었는지 확인
- **그래프에 노드가 없음**: 중심 문서 경로가 올바른지 확인, `/api/search/graph?center_path=...` 응답 확인
- **엣지가 없음**: 문서에 `[[wiki-link]]`, `supersedes`, `related` 필드가 있는지 확인
- **유사도 엣지 없음**: ChromaDB 연결 확인, 충돌 감지 store에 데이터 있는지 확인

---

### BA-10: WikiLink (문서 링크 복사 + 인라인 링크)

**테스트 1: 문서 링크 복사**
1. 사이드바에서 `.md` 문서를 우클릭
2. "문서 링크 복사" 클릭
3. 토스트: "문서 링크 복사됨: [[문서이름]]"
4. 비-md 파일(예: .pdf)을 우클릭 → "문서 링크 복사" → 경로가 복사됨

**테스트 2: 붙여넣기로 WikiLink 생성**
1. 테스트 1에서 복사한 `[[문서이름]]`을 에디터에 붙여넣기
2. 파란색 칩/뱃지 형태의 클릭 가능한 `[[문서이름]]` 링크가 생성됨
3. 일반 텍스트가 아닌 인라인 노드로 표시되는지 확인

**테스트 3: 직접 타이핑으로 WikiLink 생성**
1. 에디터에서 `[[` 입력 후 문서 이름 입력 후 `]]` 입력
2. 자동으로 WikiLink 인라인 노드로 변환됨
3. 변환 후 커서가 노드 뒤로 이동하여 계속 타이핑 가능

**테스트 4: WikiLink 클릭으로 문서 열기**
1. 에디터에 표시된 WikiLink를 클릭
2. 해당 문서가 새 탭으로 열림
3. 존재하지 않는 문서 이름의 WikiLink 클릭 → "문서를 찾을 수 없습니다" 에러 토스트

**테스트 5: 소스 모드 라운드트립**
1. WikiLink가 포함된 문서에서 소스 모드(코드 아이콘) 전환
2. 소스에 `[[문서이름]]` 텍스트가 그대로 보존됨
3. WYSIWYG 모드로 다시 전환 → WikiLink 칩이 복원됨

#### BA-10 트러블슈팅
- **WikiLink가 일반 텍스트로 표시**: 에디터에 WikiLinkNode 확장이 등록되었는지 확인 (MarkdownEditor.tsx)
- **클릭해도 문서 안 열림**: 검색 인덱스 로드 여부 확인 (`/api/search/index` 응답 확인)
- **붙여넣기 시 변환 안 됨**: PasteHandlerExtension이 wikiLink 노드를 감지하는지 확인

---

## Phase 4: 프로덕션 준비 검증

### BA-11: 에어갭 대응 (Phase 4-A)

**테스트 1: PDF 뷰어 로컬 worker**
1. PDF 문서 열기 → 정상 렌더링
2. 브라우저 DevTools Network 탭에서 `unpkg.com` 요청 없음 확인
3. `pdf.worker.min.mjs`가 로컬(`/pdf.worker.min.mjs`)에서 로드됨

**테스트 2: 폰트 로컬화**
1. 앱 로드 → UI 폰트 정상 표시
2. Network 탭에서 `fonts.googleapis.com`, `fonts.gstatic.com` 요청 없음

**테스트 3: 외부 의존성 점검**
```bash
cd frontend && npm run build
cd .. && bash scripts/check-external-deps.sh frontend/.next
# → PASS 확인
```

### BA-12: Docker 배포 (Phase 4-B)

**테스트 1: Docker Compose 전체 기동**
```bash
docker compose up -d
# 코어: backend + frontend + chroma
# 모니터링 포함: docker compose --profile monitoring up -d
```

**테스트 2: 헬스체크**
```bash
curl http://localhost:8001/health  # → {"status":"healthy",...}
curl http://localhost:3000         # → HTML 응답
```

**테스트 3: 서비스 시작 순서**
- chroma → backend → frontend 순서대로 기동됨 (depends_on + healthcheck)

### BA-13: 스토리지 추상화 (Phase 4-C)

**테스트 1: 로컬 스토리지 (기본)**
```bash
# .env: STORAGE_BACKEND=local
# 백엔드 시작 → "Wiki storage: local -> ..." 로그 확인
```

**테스트 2: NAS 스토리지 (마운트 경로)**
```bash
# .env: STORAGE_BACKEND=nas, NAS_WIKI_DIR=/path/to/nas/mount
# 해당 경로가 없으면 FileNotFoundError 발생 → 마운트 필요 알림
```

#### BA-11~13 트러블슈팅
- **PDF 로드 실패**: `public/pdf.worker.min.mjs` 파일 존재 여부 확인
- **Docker build 실패**: `.dockerignore`에 불필요한 파일이 포함되었는지 확인
- **NAS 연결 실패**: NFS/SMB 마운트가 정상인지 `ls /mnt/nas/...` 확인

### BA-14: 편집 잠금 (Phase 4-D)

**테스트 1: 잠금 획득**
1. 브라우저 A에서 문서 열기 → 편집 가능
2. 브라우저 B(다른 시크릿 창)에서 같은 문서 열기
3. "○○ 님이 편집 중입니다 (읽기 전용)" 배너 표시

**테스트 2: 잠금 해제**
1. 브라우저 A에서 문서 탭 닫기
2. 브라우저 B에서 문서 다시 열기 → 편집 가능

**테스트 3: TTL 만료**
```bash
# Lock 상태 확인
curl "http://localhost:8001/api/lock/status?path=test.md"
# 5분 후 자동 만료
```

### BA-15: 보안 강화 (Phase 4-F)

**테스트 1: Path traversal 차단**
```bash
curl http://localhost:8001/api/wiki/file/../../etc/passwd
# → 400 Bad Request
```

**테스트 2: CORS 검증**
- 허용된 origin (localhost:3000)에서만 API 호출 가능

**테스트 3: 요청 ID 추적**
```bash
curl -v http://localhost:8001/health 2>&1 | grep X-Request-ID
# → X-Request-ID 헤더 포함
```

#### BA-14~15 트러블슈팅
- **잠금 안 풀림**: `DELETE /api/lock?path=...&user=...` 수동 해제
- **세션 사용자 ID**: sessionStorage의 `ontong_user` 키로 관리 (시크릿 창마다 다름)

### BA-16: 권한 관리 RBAC (Phase 4-E)

**테스트 1: ACL 설정**
1. 사이드바 → 관리 → 접근 권한 관리 클릭
2. 새 규칙 추가: 경로 `hr/`, 읽기 `all`, 쓰기 `hr-team, admin`
3. 테이블에 규칙 표시됨

**테스트 2: API 권한 확인**
```bash
# ACL 전체 조회
curl http://localhost:8001/api/acl
# ACL 설정
curl -X PUT http://localhost:8001/api/acl \
  -H "Content-Type: application/json" \
  -d '{"path":"hr/","read":["all"],"write":["hr-team","admin"]}'
```

### BA-17: 대규모 대응 (Phase 4-G)

**테스트 1: 트리 지연 로딩**
```bash
# 전체 트리
curl http://localhost:8001/api/wiki/tree
# 1단계만
curl "http://localhost:8001/api/wiki/tree?depth=1"
# 폴더 하위만
curl http://localhost:8001/api/wiki/tree/subfolder
```

**테스트 2: 검색 인덱스 페이지네이션**
```bash
# 전체
curl http://localhost:8001/api/search/index
# 페이지네이션
curl "http://localhost:8001/api/search/index?offset=0&limit=10"
```

**테스트 3: ETag 캐싱**
```bash
ETAG=$(curl -si http://localhost:8001/api/wiki/tree | grep -i etag | cut -d' ' -f2 | tr -d '\r')
curl -H "If-None-Match: $ETAG" -o /dev/null -w "%{http_code}" http://localhost:8001/api/wiki/tree
# → 304 (변경 없음)
```

---

### BA-18. Phase 5-A: 프론트엔드 생존 (Lazy Tree + 서버 검색)

> 100K 파일 규모에서 브라우저 크래시를 방지하는 프론트엔드 최적화

**테스트 1: 트리 Lazy Loading (P5A-1)**
```bash
# depth=1: 최상위 항목만 반환, 폴더는 has_children 플래그 포함
curl -s "http://localhost:8001/api/wiki/tree?depth=1" | python3 -m json.tool | head -20
# → 폴더 노드에 "has_children": true, "children": [] 확인

# subtree: 특정 폴더의 자식만 반환
curl -s "http://localhost:8001/api/wiki/tree/폴더명" | python3 -m json.tool
# → 해당 폴더의 1단계 자식 목록
```

**UI 확인:**
1. 브라우저에서 트리 확인 — 최상위 폴더/파일만 표시
2. 폴더 클릭 → 로딩 스피너 → 하위 항목 표시 (첫 확장 시)
3. 두 번째 클릭 → 접기/펼치기 즉시 (캐시됨)

**테스트 2: 서버 사이드 검색 (P5A-2)**
```bash
# 빠른 키워드 검색 (BM25 only, ~5ms)
curl -s "http://localhost:8001/api/search/quick?q=테스트&limit=5" | python3 -m json.tool

# 위키링크 해석
curl -s "http://localhost:8001/api/search/resolve-link?target=파일명" | python3 -m json.tool
# → {"path": "폴더/파일명.md"} 또는 {"path": null}
```

**UI 확인:**
1. `Ctrl+K` (또는 `Cmd+K`)로 검색 열기
2. 검색어 입력 → 결과 즉시 표시 (네트워크 탭에서 `/api/search/quick` 요청 확인)
3. `/api/search/index` 요청이 없음 확인 (MiniSearch 인덱스 다운로드 제거됨)

**테스트 3: 낙관적 트리 업데이트 (P5A-3)**

1. 파일 생성: 우클릭 → "새 파일" → 이름 입력 → 네트워크에 `/api/wiki/tree` 재조회 없음 확인
2. 폴더 생성: 우클릭 → "새 폴더" → 네트워크에 재조회 없음, 트리 즉시 반영
3. 파일 삭제: 우클릭 → "삭제" → 트리에서 즉시 제거
4. 이름 변경: 우클릭 → "이름 변경" → 트리 즉시 반영
5. 수동 새로고침: 새로고침 버튼 → `/api/wiki/tree?depth=1` 요청 확인

**테스트 4: ETag 캐싱 (P5A-4)**
```bash
# 첫 요청 → 200 + ETag
curl -si "http://localhost:8001/api/wiki/tree?depth=1" | head -5

# 같은 ETag로 재요청 → 304
ETAG=$(curl -si "http://localhost:8001/api/wiki/tree?depth=1" | grep -i etag | cut -d' ' -f2 | tr -d '\r')
curl -H "If-None-Match: $ETAG" -o /dev/null -w "%{http_code}" "http://localhost:8001/api/wiki/tree?depth=1"
# → 304
```

**트러블슈팅:**
- 트리가 비어있으면: 백엔드의 `WIKI_ROOT` 디렉토리에 파일이 있는지 확인
- 검색 결과가 0건이면: `curl -X POST http://localhost:8001/api/wiki/reindex`로 인덱스 재구축
- 폴더 확장 시 에러: 백엔드 로그에서 경로 인코딩 문제 확인

---

### BA-19. Phase 5-B: 백엔드 동시성 + 비동기 인덱싱

> 저장 즉시 반환, 검색 병렬화, 멀티코어 활용

**테스트 1: 비동기 인덱싱 (P5B-2)**
```bash
# 파일 저장 — 즉시 반환 (인덱싱은 백그라운드)
time curl -X PUT http://localhost:8001/api/wiki/file/test_async.md \
  -H "Content-Type: application/json" \
  -d '{"content": "# Async Test\n\nBackground indexing test"}'
# → 100ms 이내 반환

# 인덱싱 상태 확인
curl -s http://localhost:8001/api/wiki/index-status | python3 -m json.tool
# → pending_count: 0 (or 1 if indexing still in progress)
```

**테스트 2: 인덱싱 관리 API (P5B-2a)**
```bash
# 특정 파일 재인덱싱
curl -X POST http://localhost:8001/api/wiki/reindex/test_async.md

# 미반영 전체 재인덱싱
curl -X POST http://localhost:8001/api/wiki/reindex-pending
```

**UI 확인:**
1. 파일 저장 후 에디터 우하단에 "검색 반영 대기 중..." 배너 확인
2. 배너가 있어도 편집/검색 정상 동작 확인
3. 인덱싱 완료 시 배너 자동 소멸

**테스트 3: 백그라운드 시작 인덱싱 (P5B-5)**
```bash
# 서버 재시작 후 즉시 health check 가능
curl http://localhost:8001/health
# → indexing_pending: N (인덱싱 진행 중이면 > 0)
```

**테스트 4: 검색 병렬화 (P5B-4)**
```bash
# 하이브리드 검색 — vector + BM25 병렬 실행
time curl -s "http://localhost:8001/api/search/hybrid?q=test&n=5" | python3 -m json.tool
# → 기존 대비 더 빠른 응답
```

---

## BA-20. Phase 5-C: Redis 기반 상태 공유

### 테스트 1: Redis Lock 동작 (P5C-1)

```bash
# Lock 획득
curl -X POST http://localhost:8001/api/lock \
  -H "Content-Type: application/json" \
  -d '{"path": "test.md", "user": "user-a"}'
# → {"locked": true, "user": "user-a", ...}

# 다른 사용자가 같은 파일 잠금 시도
curl -X POST http://localhost:8001/api/lock \
  -H "Content-Type: application/json" \
  -d '{"path": "test.md", "user": "user-b"}'
# → {"locked": false, "message": "Document is being edited by user-a"}

# Lock 해제
curl -X DELETE "http://localhost:8001/api/lock?path=test.md&user=user-a"
```

**Redis 영속성 확인 (Redis 설정 시):**
1. Lock 획득 → 백엔드 재시작 → Lock 상태 유지 확인
2. `docker exec redis redis-cli KEYS "ontong:lock:*"` 로 Redis에 키 존재 확인

### 테스트 2: Redis 쿼리 캐시 (P5C-2)

```bash
# 동일 검색 2회 실행
curl -s "http://localhost:8001/api/search/hybrid?q=test&n=5" > /dev/null
curl -s "http://localhost:8001/api/search/hybrid?q=test&n=5" > /dev/null
# 두 번째 요청이 캐시 히트로 더 빠름
```

**Redis 설정 시:** 다른 워커에서도 동일 쿼리 캐시 적중 확인

### 테스트 3: Lock Batch Refresh (P5C-3)

```bash
# 배치 리프레시 API
curl -X POST http://localhost:8001/api/lock/batch-refresh \
  -H "Content-Type: application/json" \
  -d '{"paths": ["test1.md", "test2.md"], "user": "user-a"}'
# → {"refreshed": 2, "total": 2}
```

**UI 확인:**
1. 여러 파일 탭 열기 → DevTools Network 탭에서 2분 후 `/api/lock/batch-refresh` 1건만 전송 (개별 refresh 없음)

### 테스트 4: ACL 캐싱 + 핫 리로드 (P5C-4)

```bash
# ACL 파일 수정 (서버 재시작 없이)
echo '{"wiki/hr/": {"read": ["hr-team"], "write": ["hr-team"]}}' > wiki/.acl.json

# 30초 후 자동 반영 확인
curl http://localhost:8001/api/acl
# → 새 ACL 규칙 적용됨
```

**캐싱 확인:** 동일 권한 체크 반복 시 60초 이내 캐시 적중 (로그 없음)

---

## BA-21. Phase 5-D: 수평 확장 + 리소스 거버넌스

### 테스트 1: Nginx 리버스 프록시 (P5D-1)

```bash
# Docker Compose로 전체 스택 기동
docker compose up -d

# Nginx (포트 80) 경유 접근 확인
curl http://localhost/health
# → {"status": "healthy", ...}

# 백엔드 스케일 아웃
docker compose up -d --scale backend=3
# → 3인스턴스 × 4워커 = 12 워커
```

### 테스트 2: SSE 실시간 이벤트 (P5D-5)

```bash
# 터미널 1: SSE 스트림 구독
curl -N http://localhost:8001/api/events
# → event: connected
# → data: {}

# 터미널 2: 파일 저장 → SSE 이벤트 수신 확인
curl -X PUT http://localhost:8001/api/wiki/file/sse_test.md \
  -H "Content-Type: application/json" \
  -d '{"content": "# SSE Test"}'
# 터미널 1에서 확인:
# → event: tree_change
# → data: {"action": "update", "path": "sse_test.md"}
# → event: index_status
# → data: {"action": "done", "path": "sse_test.md"}
```

**UI 확인:**
1. 브라우저 DevTools → Network → EventStream 탭에서 `/api/events` 연결 확인
2. 다른 브라우저/탭에서 파일 생성/삭제 → 트리가 자동 업데이트되는지 확인

### 테스트 3: get_all_embeddings 페이지네이션 (P5D-4)

```bash
# 100K 파일 환경에서 충돌 감지 실행
curl http://localhost:8001/api/conflict/similar
# → 메모리 4G 이내에서 정상 완료 (기존: 1-2GB 스파이크)
```

### 테스트 4: Health 엔드포인트 확인

```bash
curl http://localhost:8001/health | python3 -m json.tool
# → sse_subscribers: 0 (또는 연결된 클라이언트 수)
```

---

## BA-22. Phase 5-E: LLM 처리량 최적화

### 테스트 1: Reflection 캐싱 (P5E-1, P5E-2)

1. AI Copilot에서 **"출장 경비 규정 알려줘"** 질문 → 답변 확인
2. 동일 질문 다시 입력
   - ✅ thinking step에 **"답변 검토 완료 — 캐시 적중"** 표시
   - 응답 시작이 첫 번째보다 빠름 (cognitive_reflect LLM 호출 스킵)
3. 10분 후 동일 질문 → 캐시 만료로 다시 "자기 검토 통과" 표시

### 테스트 2: LLM 동시 처리 (P5E-3)

```bash
# 동시 5개 RAG 요청
for i in $(seq 1 5); do
  curl -s -X POST http://localhost:8001/api/agent/stream \
    -H "Content-Type: application/json" \
    -d '{"message": "재고관리 기준 알려줘", "session_id": "test-'$i'"}' &
done
wait
# → 모든 요청이 15초 이내 완료 (세마포어가 순차 제어)
```

### 테스트 3: 검색 인덱스 캐싱 (P5E-4)

```bash
# 첫 요청 (캐시 미스)
time curl -s http://localhost:8001/api/search/backlinks > /dev/null
# → 수백 ms (파일 전체 스캔)

# 즉시 두 번째 요청 (캐시 적중)
time curl -s http://localhost:8001/api/search/backlinks > /dev/null
# → < 10ms (60초 TTL 캐시)
```

### 테스트 4: 메타데이터 엔드포인트 최적화 (P5E-5)

```bash
# 사이드바 태그 목록 (frontmatter-only 읽기 + 캐시)
time curl -s http://localhost:8001/api/metadata/tags > /dev/null
# 첫 요청: ~1.8초 (frontmatter만 읽기, 기존 ~2.6초에서 개선)

time curl -s http://localhost:8001/api/metadata/tags > /dev/null
# 두 번째: < 10ms (60초 TTL 캐시)

# 태그별 파일 목록
time curl -s "http://localhost:8001/api/metadata/files-by-tag?field=tags&value=출장" > /dev/null
# → 캐시 적중 시 < 10ms

# 미태깅 문서
time curl -s http://localhost:8001/api/metadata/untagged > /dev/null
# → 캐시 적중 시 < 10ms
```

---

## Skill System 기반 구축 (세션 17)

> Skill System은 백엔드 인프라 변경으로, 기존 기능이 동일하게 동작하는지 검증하는 것이 핵심입니다.

### 테스트 1: 백엔드 기동 + 스킬 등록 확인

```bash
# 백엔드 시작
cd /Users/donghae/workspace/ai/onTong
source venv/bin/activate
uvicorn backend.main:app --port 8001 --reload
```

**확인 사항:**
- 시작 로그에 `Registered skills: 7 skills` 출력 확인
- 시작 로그에 `Registered agents: ['WIKI_QA', 'SIMULATOR', 'TRACER']` 출력 확인

```bash
# health API에서 agent 목록 확인
curl -s http://localhost:8001/health | python3 -m json.tool
# "agents": ["WIKI_QA", "SIMULATOR", "TRACER"] 이어야 함
```

### 테스트 2: 스킬 Import + 스키마 검증 (Python)

```bash
cd /Users/donghae/workspace/ai/onTong
./venv/bin/python3 -c "
from backend.application.agent.skill import skill_registry
from backend.application.agent.skills import register_all_skills
register_all_skills()

# 등록된 스킬 목록
print('Skills:', skill_registry.list_skills())

# 각 스킬의 tool schema 출력 (LLM tool-use용)
import json
for schema in skill_registry.to_tool_schemas():
    print(json.dumps(schema, indent=2, ensure_ascii=False))
"
```

**기대 결과:**
- 7개 스킬: `query_augment`, `wiki_search`, `wiki_read`, `wiki_write`, `wiki_edit`, `llm_generate`, `conflict_check`
- 각 스킬마다 OpenAI function-calling 호환 schema 출력

### 테스트 3: 기존 Q&A 기능 회귀 테스트 (UI)

> Skill System 적용 후에도 기존 Q&A가 동일하게 동작하는지 확인

1. 브라우저에서 `http://localhost:3000` 접속
2. 우측 AI Copilot 패널에서 질문 입력:

**단순 질문:**
```
출장비 규정 알려줘
```
- thinking step 표시: 쿼리 보강 → 문서 검색 → 의도 분석 → 답변 생성
- 출처(sources) 패널에 관련 문서 표시
- 마크다운 형식의 답변 스트리밍

**후속 질문 (멀티턴):**
```
담당자가 누구야?
```
- "쿼리 보강 완료" thinking step 표시 (이전 대화 맥락 반영)
- 적절한 검색 결과 반환

### 테스트 4: 문서 수정 기능 회귀 테스트 (UI)

1. AI Copilot에서 수정 요청:
```
getting-started.md 문서에 '시작하기 전에' 섹션을 추가해줘
```
- thinking step: 수정 대상 문서 검색 → 문서 수정
- 수정 내용 요약 표시
- **승인 요청 팝업** 표시 (승인/거절 버튼)

2. 파일 첨부 후 수정 요청:
- 📎 버튼으로 파일 첨부 후 "이 문서에서 날짜를 오늘로 바꿔줘" 입력
- 첨부된 파일을 직접 대상으로 수정

### 테스트 5: 문서 생성 기능 회귀 테스트 (UI)

```
새 문서 만들어줘 - Docker 컨테이너 관리 가이드
```
- "Wiki 문서 작성을 준비하고 있습니다..." 메시지
- 생성될 문서 미리보기
- **승인 요청 팝업** 표시

### 테스트 6: 기존 테스트 스위트 실행

```bash
cd /Users/donghae/workspace/ai/onTong
./venv/bin/python3 -m pytest tests/ -v
```

**기대 결과:** 145/145 PASSED (기존 68 + Skill 시스템 77)

#### Skill 시스템 테스트만 실행

```bash
./venv/bin/python3 -m pytest tests/test_skill_loader.py tests/test_skill_matcher.py tests/test_skill_api.py -v
```

**기대 결과:** 77/77 PASSED
- `test_skill_loader.py` (39): frontmatter 파싱, 카테고리, 6-Layer, 캐시, wikilink
- `test_skill_matcher.py` (18): 토큰화, substring/Jaccard, priority, pinned
- `test_skill_api.py` (20): CRUD, toggle, move, match, context API

### 트러블슈팅

| 증상 | 원인 | 해결 |
|------|------|------|
| `Registered skills: 0 skills` | `register_all_skills()` 미호출 | `main.py`에서 import 확인 |
| Q&A 응답 없음 | ChromaDB 미연결 | `docker compose up -d chroma` 후 재시작 |
| `Skill 'xxx' not found` | 스킬 미등록 | 백엔드 로그에서 skill 등록 확인 |
| 문서 수정/생성 시 500 에러 | storage 미전달 | `agent_api.init(wiki_service, chroma=chroma, storage=storage)` 확인 |
| `ModuleNotFoundError: pydantic` | venv 미활성화 | `source venv/bin/activate` 후 재시작 |

---

## User-Facing Skill System (사용자 스킬 관리)

### 사전 데이터

데모용 샘플 스킬 3개가 미리 생성되어 있습니다:

| 스킬 | 파일 | 범위 | 트리거 키워드 | 참조 문서 |
|------|------|------|-------------|----------|
| ✈️ 출장비 정산 도우미 | `_skills/출장비-정산-도우미.md` | 공용 | 출장비, 출장 정산, 해외출장 경비 | 출장-경비-규정, 출장비_정산_체크리스트, 해외출장-가이드 |
| 🎒 신규입사자 온보딩 | `_skills/신규입사자-온보딩.md` | 공용 | 신규입사, 온보딩, 입사 절차 | 신규입사자-온보딩현황, 인사규정-총칙, 사내식당-이용안내, 보안정책-가이드 |
| 📦 구매발주 안내 | `_skills/@개발자/구매발주-안내.md` | 개인 | 구매발주, 발주 절차, 납품 검수 | 구매발주-프로세스, 납품검수-절차, 주문처리-비즈니스규칙, 대금지급-정책 |

---

### 시나리오 1: 사이드바에서 스킬 목록 확인

1. 브라우저에서 `http://localhost:3000` 열기
2. 좌측 사이드바에서 ⚡ (번개) 아이콘 클릭
3. **공용 스킬** 섹션에 "✈️ 출장비 정산 도우미", "🎒 신규입사자 온보딩" 2개 표시
4. **내 스킬** 섹션에 "📦 구매발주 안내" 표시 (개인 스킬)
5. 각 스킬 카드에 설명 + 트리거 키워드 뱃지 표시

**기대 결과:** 3개 스킬이 공용/개인으로 분류되어 표시

> **참고:** "내 스킬"은 현재 로그인 사용자 이름이 `개발자`일 때만 표시됩니다. 다른 이름이면 `_skills/@{사용자이름}/` 폴더를 생성해야 합니다.

---

### 시나리오 2: 스킬 클릭 → 에디터에서 열기 + 링크 탐색

1. ⚡ 탭에서 "✈️ 출장비 정산 도우미" 클릭
2. 에디터 탭에서 스킬 파일 열림 — frontmatter + 지시사항 + 참조 문서 확인
3. 본문의 `[[출장-경비-규정]]` 링크 클릭 → 해당 문서가 새 탭에서 열림
4. 에디터 상단 **LinkedDocsPanel** 확인:
   - "참조: 출장-경비-규정, 출장비_정산_체크리스트, 해외출장-가이드" 표시
5. "그래프에서 보기" 클릭 → 스킬 노드(보라색 다이아몬드)와 참조 문서 연결 시각화

**기대 결과:** 스킬은 일반 위키 문서처럼 편집 가능. [[wikilink]] 클릭으로 참조 문서 이동. 그래프에서 보라색 다이아몬드로 구분.

---

### 시나리오 3: 스킬 수동 선택 (Copilot ⚡ 피커)

1. 우측 AI Copilot 패널에서 입력창 왼쪽의 ⚡ (번개) 버튼 클릭
2. 스킬 목록 팝업에서 "✈️ 출장비 정산 도우미" 클릭
3. 입력창 위에 보라색 pill 표시: `✈️ 출장비 정산 도우미 ✕`
4. 입력: `해외 출장 숙박비 한도가 얼마야?`
5. Enter 전송
6. 확인 사항:
   - thinking step: "✈️ 출장비 정산 도우미 · 스킬 적용"
   - thinking step: "참조 문서 로딩 완료 · 3건"
   - 출장-경비-규정, 출장비_정산_체크리스트, 해외출장-가이드 내용 기반 답변
   - sources 패널에 참조 문서 3개 표시

**기대 결과:** 스킬 지시사항에 따른 구조화된 답변. sources에 참조 문서 표시.

> **Ollama 필요:** LLM 답변을 받으려면 Ollama가 실행 중이어야 합니다. 미실행 시 thinking step까지만 표시됩니다.

---

### 시나리오 4: 스킬 자동 제안 (트리거 키워드 매칭)

1. Copilot 입력창에 `출장비 정산 어떻게 해?` 입력 (아직 전송하지 마세요)
2. 약 0.5초 후 입력창 위에 자동 제안 배너 표시:
   ```
   ✈️ 출장비 정산 도우미  [사용]  [무시]
   ```
3. **[사용]** 클릭 → pill 표시 + 해당 스킬로 질문 전송
4. 또는 **[무시]** 클릭 → 배너 닫힘, 같은 세션에서 같은 스킬 재제안 안 함
5. 다른 트리거로도 테스트: `온보딩 절차 알려줘` → 🎒 신규입사자 온보딩 제안

**기대 결과:** trigger 키워드가 입력에 포함되면 자동 제안. [사용] 시 스킬 적용.

---

### 시나리오 5: 새 스킬 만들기 (사이드바)

1. ⚡ 탭에서 **+** 버튼 클릭 → 인라인 생성 폼 표시
2. 입력:
   - 이름: `회의록 작성 도우미`
   - 설명: `회의록을 양식에 맞게 정리합니다`
   - 트리거: `회의록, 회의 정리`
   - 아이콘: `📝`
   - 범위: 개인
3. "생성" 클릭
4. 에디터에서 새 스킬 파일 열림 (`_skills/@{username}/회의록-작성-도우미.md`)
5. `## 지시사항` 아래에 원하는 지시 추가
6. `## 참조 문서` 아래에 `- [[회의록-2026-03-25]]` 추가
7. Ctrl+S 저장
8. Copilot에서 `회의록 정리해줘` 입력 → 자동 제안 확인

**기대 결과:** 스킬 파일 생성 → 에디터 열림 → 편집 → 저장 후 즉시 사용 가능

---

### 시나리오 6: API 직접 테스트 (curl)

```bash
# 1. 스킬 목록 조회
curl -s http://localhost:8001/api/skills/ | python3 -m json.tool

# 기대: system에 2개(출장비, 온보딩), personal에 1개(구매발주)

# 2. 스킬 매칭 테스트
curl -s "http://localhost:8001/api/skills/match?q=출장비%20정산" | python3 -m json.tool

# 기대: match.skill.title = "출장비 정산 도우미", confidence ≥ 0.9

# 3. 매칭 안 되는 경우
curl -s "http://localhost:8001/api/skills/match?q=날씨%20어때" | python3 -m json.tool

# 기대: match = null

# 4. 스킬 단건 조회
curl -s http://localhost:8001/api/skills/_skills/출장비-정산-도우미.md | python3 -m json.tool

# 기대: SkillMeta 전체 필드 (path, title, trigger, icon, referenced_docs 등)

# 5. 새 스킬 생성 (API)
curl -s -X POST http://localhost:8001/api/skills/ \
  -H "Content-Type: application/json" \
  -d '{"title":"테스트 스킬","description":"API로 만든 테스트","trigger":["테스트","시험"],"icon":"🧪"}' \
  | python3 -m json.tool

# 기대: path = "_skills/@개발자/테스트-스킬.md" 생성

# 6. 생성한 스킬 삭제
curl -s -X DELETE http://localhost:8001/api/skills/_skills/@개발자/테스트-스킬.md | python3 -m json.tool

# 기대: {"deleted": "_skills/@개발자/테스트-스킬.md"}
```

---

### 시나리오 7: 그래프에서 스킬 노드 확인

1. 사이드바 설정(톱니) 탭 → "문서 관계 그래프" 클릭
2. 검색창에 "출장비 정산 도우미" 검색 → 클릭
3. 그래프에서 확인:
   - 중심 노드: 출장비 정산 도우미 (보라색 다이아몬드 ◇)
   - 연결 노드: 출장-경비-규정, 출장비_정산_체크리스트, 해외출장-가이드 (원형 ○)
   - 엣지: wiki-link 타입
4. 하단 범례에 보라색 "스킬" 항목 확인

**기대 결과:** 스킬 노드가 일반 문서와 시각적으로 구분됨 (다이아몬드 + 보라색)

---

---

### 시나리오 8: 카테고리 기반 스킬 관리

1. 사이드바 ⚡ 탭 클릭
2. 확인 사항:
   - **검색바** 상단에 표시됨
   - "내 스킬" 섹션: ▸ SCM (1) 접이식 그룹 → 펼치면 📦 구매발주 안내
   - "공용 스킬" 섹션: ▸ HR (1), ▸ Finance (1) 접이식 그룹
3. 검색바에 "출장" 입력 → Finance/출장비 정산 도우미만 필터링
4. 검색 지우기 → 전체 복원

**기대 결과:** 카테고리별로 접이식 그룹, 검색 필터링 동작

---

### 시나리오 9: 스킬 토글(활성/비활성) + 복제

1. ⚡ 탭에서 스킬에 마우스 호버 → 👁 아이콘, 📋 복사 아이콘 표시
2. 👁(Eye) 클릭 → 스킬이 반투명(비활성) 처리
3. 비활성 스킬은 Copilot 자동 제안 대상에서 제외
4. 다시 👁 클릭 → 활성 복원
5. 📋(Copy) 클릭 → "(사본)" 접미사로 복제된 스킬 에디터 열림

**기대 결과:** 토글/복제가 즉시 반영, 목록 새로고침 자동

---

### 시나리오 10: 카테고리 포함 스킬 생성

1. ⚡ 탭 → "+" 클릭
2. 생성 폼에 카테고리 필드(combobox)와 우선순위(1~10) 입력 확인
3. 스킬 이름: "예산 조회", 카테고리: "Finance", 우선순위: 8, scope: 개인
4. "생성" 클릭 → 파일 경로: `_skills/@{user}/Finance/예산-조회.md`
5. ⚡ 탭에서 Finance 카테고리 안에 스킬 표시 확인

**기대 결과:** 카테고리 + 우선순위가 폴더 경로와 frontmatter에 반영

---

### 시나리오 11: Copilot 피커 카테고리 그룹핑

1. Copilot 패널에서 ⚡ 버튼 클릭 → 스킬 피커 드롭다운
2. 카테고리 헤더(HR, Finance, SCM 등)로 그룹핑 확인
3. 스킬 5개 이상이면 상단에 검색 input 표시
4. 검색에 "온보딩" 입력 → HR/신규입사자 온보딩만 필터링
5. 스킬 선택 → 입력창에 pill 표시 → 메시지 전송 시 스킬 적용

**기대 결과:** 카테고리별 그룹 + 검색 필터 동작

---

### 시나리오 12: API 카테고리/우선순위 확인

```bash
# 카테고리 + categories 필드 확인
curl http://localhost:8001/api/skills/ | python3 -m json.tool
# categories: ["Finance", "HR", "SCM"], 각 스킬에 category/priority/pinned 필드

# 카테고리 포함 스킬 생성
curl -X POST http://localhost:8001/api/skills/ \
  -H "Content-Type: application/json" \
  -d '{"title":"테스트 스킬","category":"HR","priority":8,"trigger":["테스트"]}'
# 파일 경로: _skills/HR/테스트-스킬.md

# 토글 API
curl -X PATCH http://localhost:8001/api/skills/_skills/HR/테스트-스킬.md/toggle
# {"path": "_skills/HR/테스트-스킬.md", "enabled": false}
```

---

### 시나리오 13: 참조 문서 탐색 시각화 (핵심 데모)

> 스킬이 내부 [[wikilink]] 참조 문서를 하나씩 타고 들어가며 컨텍스트를 수집하는 과정이 실시간으로 보이는 시나리오

1. Copilot에서 ⚡ 버튼 → "구매발주 프로세스 안내" 스킬 선택
2. 입력: "구매발주에서 납품 검수까지 전체 절차를 표로 요약해줘"
3. thinking step 관찰:
   ```
   📦 구매발주 프로세스 안내 — 스킬 적용
   참조 문서 로딩 중 — 4건 탐색
   📄 구매발주-프로세스 — 1/4
   📄 납품검수-절차 — 2/4
   📄 주문처리-비즈니스규칙 — 3/4
   📄 대금지급-정책 — 4/4
   참조 문서 로딩 완료 — 4건 적용
   답변 생성 중
   ```
4. 답변에서 확인:
   - 4개 참조 문서의 내용이 **교차 인용**된 답변 (발주→검수→대금 흐름)
   - 구체적 수치 포함 (승인 한도 100만/500만, 수량 오차 ±2% 등)
   - DG320 장애 사례 언급 가능
5. 답변 하단 출처 영역에 참조 문서 4개 표시 → 클릭 시 해당 문서 탭 열림

**기대 결과:** 스킬이 4개 문서를 순차 탐색하는 과정이 시각적으로 보이고, 답변이 다수 문서를 종합하여 작성됨

**추가 질문 예시 (후속 대화):**
- "긴급 발주 시 절차가 다른 부분 알려줘" → 구매발주-프로세스의 긴급발주 + 납품검수의 선입고 규칙 교차 답변
- "검수 불합격이면 어떻게 되지?" → 납품검수-절차의 반품 처리 + 반품처리-규정 참조

---

### 시나리오 14: 6-Layer 스킬 포맷 비교

**목적:** 기본 스킬 vs 6-layer 고급 스킬의 답변 품질 차이 확인

1. **기본 스킬 테스트:**
   - Copilot에서 "출장비 정산 어떻게 해?" 입력
   - 기본 형식 (지시사항 + 참조문서만) → 자유 텍스트 답변 확인

2. **6-Layer 스킬 테스트:**
   - Copilot에서 "신규 입사자 온보딩 절차 알려줘" 입력
   - **역할:** "인사팀 온보딩 담당자" 톤으로 답변하는지 확인
   - **워크플로우:** "입사 유형(신입/경력/인턴) 확인" 질문부터 시작하는지 확인
   - **체크리스트:** 수습 기간, 편의시설, 보안교육 포함 / 연봉 정보 미포함 확인
   - **출력 형식:** 요약 → 타임라인(표) → 서류 목록 → FAQ 구조로 답변하는지 확인
   - **제한사항:** 1000자 이내, 추측 없이 참조 문서 기반 답변인지 확인

3. **Preamble 확인:**
   - 서버 로그에서 시스템 프롬프트 확인
   - `## 컨텍스트` 블록에 날짜, 사용자, 참조문서 현황 포함 확인

4. **누락 문서 경고:**
   - `wiki/_skills/HR/신규입사자-온보딩.md`의 참조 문서 중 실제 없는 문서가 있을 때
   - thinking step에서 ⚠️ 아이콘 + "(없음)" 표시 확인

5. **하위 호환:**
   - 출장비 스킬은 기존 형식 그대로 → 기존과 동일하게 동작 확인

### 시나리오 15: 6-Layer 스킬 생성 (API)

1. **새 6-layer 스킬 생성:**
   ```bash
   curl -X POST http://localhost:8001/api/skills/ \
     -H "Content-Type: application/json" \
     -d '{
       "title": "회의실 예약 안내",
       "trigger": ["회의실", "예약"],
       "icon": "🏢",
       "scope": "shared",
       "instructions": "사내 회의실 예약 절차를 안내하세요.",
       "role": "총무팀 시설관리 담당자입니다.\n- 톤: 간결하고 실용적",
       "checklist": "### 반드시 포함\n- 예약 가능 시간대\n- 취소 규정\n\n### 언급 금지\n- 다른 팀 예약 현황",
       "output_format": "1. 예약 방법\n2. 주의사항\n3. 문의처",
       "self_regulation": "- 답변 길이: 최대 300자"
     }'
   ```
2. 생성된 마크다운 파일에서 `## 역할`, `## 체크리스트`, `## 출력 형식`, `## 제한사항` 섹션 확인

3. **템플릿 모드 확인 (instructions 비어있을 때):**
   ```bash
   curl -X POST http://localhost:8001/api/skills/ \
     -H "Content-Type: application/json" \
     -d '{"title": "템플릿-테스트", "trigger": ["테스트"]}'
   ```
   - 생성된 파일에 역할/워크플로우/체크리스트/출력형식/제한사항 가이드 템플릿 포함 확인

---

### 시나리오 16: 후속 질문 스킬 유지

**목적:** 첫 질문에서 적용된 스킬이 후속 대화에서도 유지되는지 확인

1. **명시적 선택 후 후속 질문:**
   - Copilot에서 ⚡ 피커로 "신규입사자 온보딩 도우미" 선택
   - "온보딩 절차 알려줘" 입력 → 전송
   - pill에 "🎒 신규입사자 온보딩 도우미 **(유지 중)**" 표시 확인
   - 후속: "경력직이야" 입력 → 전송
   - thinking step에 "🎒 신규입사자 온보딩 도우미 스킬 적용" 표시 확인
   - 답변이 경력직 온보딩에 맞게 나오는지 확인

2. **자동 매칭 후 유지:**
   - 새 대화 시작 → "출장비 정산 어떻게 해?" 입력
   - 자동 매칭으로 ✈️ 출장비 스킬 적용 → pill "(유지 중)" 표시 확인
   - 후속: "해외출장인데" → 스킬 계속 적용 확인

3. **스킬 해제:**
   - pill의 X 버튼 클릭 → pill 사라짐
   - 후속 질문 → 스킬 없이 일반 RAG 모드로 동작 확인

4. **세션 전환:**
   - 새 대화 버튼 클릭 → pill 사라짐 (sessionSkill 초기화)

---

### 트러블슈팅

| 증상 | 원인 | 해결 |
|------|------|------|
| ⚡ 탭에 스킬 목록이 비어있음 | `_skills/` 폴더 없음 or 파일에 `type: skill` frontmatter 없음 | `wiki/_skills/` 폴더 확인, frontmatter 확인 |
| "내 스킬"이 안 보임 | 로그인 사용자 이름과 `@` 폴더명 불일치 | `_skills/@{사용자이름}/` 폴더 확인 |
| 자동 제안 배너가 안 뜸 | trigger 키워드 매칭 안 됨 (threshold 0.5 미만) | trigger에 더 구체적인 키워드 추가 |
| 스킬 기반 답변이 에러 | Ollama 미실행 or LLM_MODEL 미설정 | `ollama serve` 실행, `.env`의 `LLM_MODEL` 확인 |
| 그래프에서 스킬 안 보임 | 스킬 파일에 [[wikilink]] 없음 (연결 없으면 그래프 노드 안 됨) | 참조 문서 링크 추가 후 저장 |
| 스킬 생성 시 409 에러 | 같은 이름 파일 이미 존재 | 다른 이름 사용 or 기존 파일 삭제 |
| `Skill scan complete: 0 skills` 로그 | 서버 캐시 30초 TTL | 30초 대기 후 재요청, 또는 서버 재시작 |
| 카테고리 그룹이 안 보임 | 스킬이 _skills/ 루트에만 있음 (하위 폴더 없음) | 하위 폴더로 이동 or frontmatter에 category 명시 |
| 토글 후 변화 없음 | 캐시 미갱신 | 서버 로그에서 invalidate 확인, 30초 대기 |
| 복제 실패 | 같은 이름 파일 존재 | "(사본)" 접미사 파일 삭제 후 재시도 |
| 6-layer 섹션 무시됨 | `## 역할` 등 헤딩 오타 | 정확한 한국어 헤딩 사용: 역할, 워크플로우, 체크리스트, 출력 형식, 제한사항 |
| Preamble 날짜 누락 | api/agent.py에서 preamble 미주입 | 서버 재시작 후 확인 |
| 후속 질문에 스킬 미적용 | sessionSkill 미저장 | AICopilot.tsx에서 sessionSkill state 확인 |
| "(유지 중)" 라벨 안 보임 | selectedSkill이 null이 아님 | 전송 후 selectedSkill이 null로 리셋되는지 확인 |

---

## 시나리오 15: FE 고급 설정 UI (스킬 생성 6-Layer 폼)

### 15-1. 고급 모달로 스킬 생성

1. 사이드바 스킬 탭 → + 버튼 → 인라인 폼 열림
2. "생성" 버튼 오른쪽 ⚙️ 아이콘 클릭 → **고급 설정 모달** 열림
3. 기본 필드 입력:
   - 스킬 이름: "테스트 고급 스킬"
   - 설명: "고급 설정 테스트"
   - 트리거: "테스트, 고급"
   - 카테고리: "HR"
4. "고급 설정 (6-Layer)" 펼치기
5. 역할: "친절한 HR 담당자 역할로 답변합니다"
6. 지시사항: "참조 문서 기반으로 정확히 답변하세요"
7. 워크플로우: "### 1단계: 질문 파악\n### 2단계: 문서 검색\n### 3단계: 답변 생성"
8. 참조 문서: "추가" 클릭 → 문서 검색 → 선택 → 뱃지 표시 확인
9. "생성" 클릭 → 스킬 생성 + 탭 열림
10. 생성된 마크다운에 6-Layer 섹션(역할/지시사항/워크플로우 등) 반영 확인

### 15-2. 스킬 복제 시 6-Layer 복사

1. 시나리오 15-1에서 생성한 스킬의 우클릭 → 복제
2. "(사본)" 스킬이 생성되고 탭 열림
3. 복제된 마크다운에 **역할/지시사항/워크플로우** 등 6-Layer 내용이 모두 포함된 것 확인
4. 참조 문서 `[[문서이름]]` 포함 확인

### 15-3. 빠른 생성 (회귀 확인)

1. 사이드바 인라인 폼에서 "간단 스킬" 입력 → "생성" 클릭
2. 정상 생성 확인 (기존 동작 변경 없음)
3. 생성된 마크다운에 기본 템플릿 섹션 포함 확인

### 트러블슈팅

| 증상 | 원인 | 해결 |
|------|------|------|
| 모달이 안 열림 | ⚙️ 버튼 미노출 (인라인 폼 닫힌 상태) | + 버튼으로 인라인 폼 먼저 열기 |
| 참조 문서 검색 결과 없음 | 문서가 인덱싱 안 됨 | 문서 저장 후 인덱싱 완료 대기 |
| 복제 시 6-layer 누락 | context API 실패 | 서버 로그 확인, skill.py context 엔드포인트 확인 |

---

## 시나리오 16: 스킬 관리 편의 기능 (우클릭 + 드래그앤드롭)

### 16-1. 우클릭 컨텍스트 메뉴

1. 사이드바 스킬 탭에서 아무 스킬 **우클릭**
2. 컨텍스트 메뉴 표시: 편집 / 복제 / 활성화(비활성화) / 삭제
3. **편집** 클릭 → 해당 스킬 마크다운이 탭에서 열림
4. 다시 우클릭 → **복제** → "(사본)" 스킬 생성 확인
5. 다시 우클릭 → **비활성화** → 스킬 반투명 + (비활성) 표시
6. 메뉴 바깥 클릭 → 메뉴 닫힘

### 16-2. 스킬 삭제

1. 스킬 우클릭 → **삭제** 클릭
2. confirm 다이얼로그: "XX 스킬을 삭제하시겠습니까?"
3. 확인 → 스킬 삭제 + 목록에서 즉시 사라짐 + 토스트 메시지
4. 취소 → 아무 일 없음

### 16-3. 드래그앤드롭으로 카테고리 이동

1. 카테고리가 2개 이상인 상태 (예: HR, Finance)
2. HR 카테고리의 스킬에 마우스 hover → 왼쪽에 ≡ 드래그 핸들 표시
3. 드래그 핸들을 잡고 Finance 카테고리 영역으로 드래그
4. Finance 영역 하이라이트 (파란색 배경)
5. 드롭 → "XX → Finance 이동 완료" 토스트
6. 스킬이 Finance 카테고리로 이동 확인 (파일 경로도 변경됨)

### 트러블슈팅

| 증상 | 원인 | 해결 |
|------|------|------|
| 우클릭 시 브라우저 기본 메뉴 뜸 | preventDefault 미동작 | 페이지 새로고침 |
| 드래그가 안 됨 | 드래그 핸들이 아닌 카드 영역 드래그 | hover 시 나타나는 ≡ 아이콘 드래그 |
| 카테고리 이동 실패 | 대상 경로에 같은 이름 파일 존재 | 이름 변경 후 재시도 |
| 삭제 후 목록 안 바뀜 | 캐시 | refreshSkills 호출 확인, 서버 재시작 |

---

## Pydantic AI 마이그레이션 (PA-1 ~ PA-8)

> **내부 구조 변경** — 사용자 대면 동작 변화 없음. SSE 이벤트 시퀀스, API 계약, 스킬 프로토콜 모두 기존과 동일.

### 검증 방법

```bash
# 전체 테스트 (174개 통과 확인)
cd /Users/donghae/workspace/ai/onTong
source venv/bin/activate
pytest tests/ -v

# litellm 직접 호출 제거 확인 (llm_generate.py만 남아야 함)
grep -r "import litellm" backend/application/agent/
# 결과: backend/application/agent/skills/llm_generate.py 만 출력

# Pydantic AI 마이그레이션 전용 테스트
pytest tests/test_pydantic_ai_migration.py -v
```

### 트러블슈팅

| 증상 | 원인 | 해결 |
|------|------|------|
| `ModuleNotFoundError: pydantic_ai` | 의존성 미설치 | `pip install -e ".[dev]"` 또는 `pip install pydantic-ai-slim[litellm]` |
| `Agent` 생성 시 model validation 에러 | litellm 미설치 | `pip install litellm` |
| 기존 채팅/위키 동작 변화 | 발생하면 안 됨 | `pytest tests/ -v`로 전체 테스트 확인, 이슈 리포트 |

---

## 세션 24 추가 기능 데모 시나리오

### 1. 충돌 감지 테스트

**시나리오**: 동일 주제를 다르게 설명하는 문서 2개가 있을 때 충돌 경고가 뜨는지 확인

1. 위키에 같은 절차를 서로 다르게 설명하는 문서가 2개 있는 상태에서
2. 채팅에서 해당 주제로 질문 (예: "서버 점검 절차 알려줘")
3. **기대 결과**: `conflict_warning` SSE 이벤트 발생 → 채팅에 충돌 경고 배너 표시
4. 충돌 설명이 **한국어**로 나오는지 확인 (어떤 문서가 어떻게 다른지)

**트러블슈팅**:
| 증상 | 원인 | 해결 |
|------|------|------|
| 충돌 경고 안 뜸 | 문서가 1건만 검색됨 | 관련 문서가 2건 이상 검색되도록 질문을 구체적으로 |
| 충돌 설명이 영어 | LLM이 프롬프트 무시 | 로그에서 cognitive reflection 결과 확인 |

### 2. 문서 생성 (워크스페이스 직접 작업)

**시나리오**: 채팅으로 문서 생성 요청 → 워크스페이스에서 미리보기 + 승인

1. 채팅에 "서버 점검 체크리스트 만들어줘" 입력
2. **기대 결과**:
   - 채팅: `"문서를 생성했습니다. 워크스페이스에서 확인하세요"` 한 줄만 표시
   - 워크스페이스: 새 탭이 자동 열림 → 렌더링된 미리보기 + 상단 바
3. 상단 바 버튼 테스트:
   - **[저장]**: 파일 저장 → 트리에 새 파일 추가됨
   - **[직접 편집]**: 파일 저장 후 에디터 모드로 전환 → 직접 수정 가능
   - **[취소]**: 파일 미저장 → 탭 닫힘

### 3. 문서 수정 (워크스페이스 DiffView 직접 작업)

**시나리오**: 채팅으로 기존 문서 수정 요청 → 워크스페이스에서 Diff 확인 + 적용

1. 기존 문서를 📎으로 첨부하고 "이 문서에 롤백 절차 섹션 추가해줘" 입력
2. **기대 결과**:
   - 채팅: `"문서 수정안을 생성했습니다. 워크스페이스에서 확인하세요"` 한 줄만 표시
   - 워크스페이스: DiffView 자동 열림 (변경 전/후 비교)
3. DiffView 조작 테스트:
   - 개별 hunk 체크박스로 선택적 적용
   - **[전체 적용]**: 모든 변경사항 저장
   - **[되돌리기]**: 변경 취소 (원본 유지)
   - **[직접 편집]**: 수정안 저장 후 에디터에서 직접 수정

### 4. Lineage 동기화 테스트

**시나리오**: deprecated 문서의 status를 미설정으로 되돌렸을 때 그래프 연결이 사라지는지

1. 문서 A의 메타데이터에 `status: deprecated`, `superseded_by: B` 설정
2. 문서 관계 그래프에서 A→B 연결선 확인
3. 문서 A의 status를 미설정으로 변경 후 저장
4. **기대 결과**: 그래프에서 A→B 연결선 사라짐, 문서 B의 `supersedes` 필드도 자동 정리됨

### 5. 채팅 입력 히스토리 테스트

1. 채팅에서 여러 질문을 순서대로 입력 (예: "장애 대응 절차", "서버 점검 방법", "배포 절차")
2. 입력창에서 **↑ 방향키** 누르기
3. **기대 결과**: "배포 절차" → "서버 점검 방법" → "장애 대응 절차" 순서로 이전 질문 복원
4. **↓ 방향키**로 최근 질문 방향으로 이동, 끝에 도달하면 원래 입력 복원

### 6. 충돌 비교 해결 테스트 (나란히 비교)

**시나리오**: 채팅에서 충돌 감지 → "나란히 비교" 버튼으로 DiffViewer 열고 해결

1. 동일 주제의 문서 2개가 있는 상태에서 채팅 질문
2. **기대 결과 — 충돌 배너**:
   - 페어별 카드 표시 (파일명 A ↔ 파일명 B + 유사도 %)
   - 충돌 요약 텍스트 (한국어)
   - **"나란히 비교"** 버튼
3. "나란히 비교" 클릭:
   - 워크스페이스에 DiffViewer 탭 열림 (기존 비교 탭과 동일)
   - side-by-side diff + "A가 최신 / B가 최신" 버튼
4. "A가 최신 (B를 deprecated)" 클릭:
   - B 문서가 deprecated 처리
   - 채팅 배너의 해당 페어에 **녹색 "해결됨"** 표시
5. **다중 충돌 테스트**: 3개 이상 문서가 충돌할 때 모든 조합 페어 표시되는지 확인
6. **ConflictDashboard 동기화**: 채팅에서 감지된 충돌이 관리 탭 → 문서 충돌 감지에도 나타나는지 확인

**트러블슈팅**:
| 증상 | 원인 | 해결 |
|------|------|------|
| "나란히 비교" 버튼 안 보임 | conflict_pairs 비어있음 | 문서 2개 이상 검색되는 질문 사용 |
| "해결됨" 표시 안 됨 | DiffViewer에서 deprecation 실패 | 네트워크 탭에서 /api/conflict/deprecate 응답 확인 |
| ConflictDashboard에 안 나옴 | conflict_store 미연결 | 백엔드 로그에서 conflict_store 관련 에러 확인 |

### 검증 방법

```bash
# 전체 테스트 (177개 통과 확인)
cd /Users/donghae/workspace/ai/onTong
source venv/bin/activate
pytest tests/ -v
```
