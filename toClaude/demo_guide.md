# onTong 데모 가이드 (Wiki 완성 + Section 2 Modeling MVP + ACL Domain Scoping)

---

## Mapping Workbench (2026-04-16)

> 소스 코드 뷰어 + 도메인 그래프 캔버스 + 분할 패널 워크벤치.
> **브랜치**: `main`

### 사전 준비
```bash
# Backend
cd /Users/donghae/workspace/ai/onTong
source .venv/bin/activate && set -a && source .env && set +a
uvicorn backend.main:app --host 0.0.0.0 --port 8001

# Frontend (별도 터미널)
cd frontend && npm run dev

# 데모 데이터 시드
curl -s -X POST http://localhost:8001/api/modeling/seed/scm-demo | python3 -m json.tool
```

### 시나리오 1: 소스 파일 트리 탐색
1. `http://localhost:3000` → Modeling 탭 → "SCM 데모 프로젝트 로드"
2. 사이드바에서 **"매핑 워크벤치"** 클릭
3. 오른쪽 패널에 파일 트리 표시됨
4. Java 파일 클릭 → Monaco 에디터에 구문 강조 소스 표시
5. **확인**: 파일 검색 필터로 "Safety" 입력 → 해당 파일만 표시

### 시나리오 2: 도메인 그래프 탐색
1. 왼쪽 패널에 SCOR 도메인 그래프 표시 (React Flow)
2. 초록색 노드 = 코드 매핑 있음, 회색 = 매핑 없음
3. 노드 클릭 → 하단 엔티티 패널에 연결된 코드 엔티티 표시

### 시나리오 3: 양방향 연동
1. 왼쪽 캔버스에서 도메인 노드 클릭 → 오른쪽 뷰어가 해당 엔티티 파일 열고 스크롤
2. 오른쪽 뷰어에서 엔티티 라인 클릭 → 왼쪽 캔버스에서 도메인 노드 하이라이트

### 시나리오 4: 드래그-드롭 매핑 생성
1. 하단 엔티티 패널에서 빨간 점(미매핑) 엔티티를 도메인 노드로 드래그
2. 매핑 생성 후 노드 색상 변경 확인

### API 직접 테스트
```bash
# 파일 트리
curl -s http://localhost:8001/api/modeling/source/tree/scm-demo | python3 -m json.tool

# 파일 내용 + 엔티티 위치
curl -s "http://localhost:8001/api/modeling/source/file/scm-demo?path=src/main/java/com/ontong/scm/inventory/SafetyStockCalculator.java" | python3 -m json.tool

# 엔티티 위치 조회
curl -s http://localhost:8001/api/modeling/source/entity/scm-demo/com.ontong.scm.inventory.SafetyStockCalculator | python3 -m json.tool
```

### 트러블슈팅
- **워크벤치 빈 화면**: SCM 데모 프로젝트가 로드되었는지 확인 (시드 API 호출)
- **파일 트리 에러**: sample-repos/scm-demo 디렉토리 존재 확인
- **그래프 노드 없음**: 온톨로지 트리가 시드되었는지 확인
- **드래그 매핑 실패**: Neo4j 연결 상태 확인

---

## ACL Domain Scoping (2026-04-14)

> 기업용 접근 권한 시스템. 개인 공간, 세밀한 ACL, ChromaDB access_scope, 사이드바 구조화.  
> **브랜치**: `feat/acl-domain-scoping`

### 사전 준비
```bash
# 기존 환경 + ACL 마이그레이션 (최초 1회)
python scripts/migrate_acl.py
curl -X POST http://localhost:8001/api/wiki/reindex  # access_scope 반영
```

### 시나리오 1: 사용자 전환 + 트리 ACL 필터링
1. 기본 사용자(donghae, admin)로 접속 → 모든 폴더 보임 (manage 권한)
2. `X-User-Id: kim` 헤더로 API 호출:
   ```bash
   curl -s http://localhost:8001/api/wiki/tree -H "X-User-Id: kim"
   ```
3. **확인**: kim은 ACL이 `read=all`인 폴더 + 자신의 `@kim` 개인 공간만 보임
4. donghae의 개인 공간(`@donghae/`)은 kim에게 안 보임

### 시나리오 2: ACL 설정 (관리자)
1. 관리자로 인프라 폴더에 ACL 설정:
   ```bash
   curl -X PUT "http://localhost:8001/api/acl/인프라/" \
     -H "X-User-Id: donghae" -H "Content-Type: application/json" \
     -d '{"read":["인프라팀"],"write":["인프라팀"],"manage":["@donghae"]}'
   ```
2. **확인**: 인프라팀이 아닌 사용자(kim)는 인프라 폴더 접근 불가
3. ACL 해제하면 다시 접근 가능

### 시나리오 3: 그룹 관리
1. 그룹 생성:
   ```bash
   curl -X POST http://localhost:8001/api/groups \
     -H "X-User-Id: donghae" -H "Content-Type: application/json" \
     -d '{"id":"infra-team","name":"인프라팀","type":"department","members":["kim","lee"]}'
   ```
2. 그룹 목록 확인: `curl http://localhost:8001/api/groups -H "X-User-Id: donghae"`
3. 멤버 추가/제거: PUT `/api/groups/infra-team/members`

### 시나리오 4: 개인 공간
1. `curl http://localhost:8001/api/wiki/tree/personal -H "X-User-Id: kim"`
2. **확인**: `@kim/` 폴더만 반환됨
3. donghae가 `@kim/` 접근 시도 → admin이므로 접근 가능
4. lee가 `@kim/` 접근 시도 → 거부 (개인 공간은 본인+admin만)

### 시나리오 5: 인증 확인
1. `curl http://localhost:8001/api/auth/me -H "X-User-Id: donghae"`
2. **확인**: `{"id":"donghae","name":"동해","roles":["admin"],"groups":[]}`

### 시나리오 6: 엔드포인트 권한 (Part 3)
1. **reindex는 admin만**:
   ```bash
   curl -s -X POST http://localhost:8001/api/wiki/reindex -H "X-User-Id: kim"
   # → {"detail":"Admin access required"}
   curl -s -X POST http://localhost:8001/api/wiki/reindex -H "X-User-Id: donghae"
   # → {"total_chunks": N}
   ```
2. **읽기전용 폴더에서 생성 거부**:
   ```bash
   # 인사/ 폴더를 read-only로 설정
   curl -X PUT "http://localhost:8001/api/acl/인사/" -H "X-User-Id: donghae" \
     -H "Content-Type: application/json" -d '{"read":["all"],"write":["admin"]}'
   # kim이 폴더 생성 시도 → 403
   curl -X POST "http://localhost:8001/api/wiki/folder/인사/test" -H "X-User-Id: kim"
   ```
3. **에디터 읽기전용 배너**: write 권한 없는 문서 열면 "편집 권한이 없습니다" 배너 표시

### 트러블슈팅
- **트리가 비어 보임**: 마이그레이션 미실행 → `python scripts/migrate_acl.py` 실행
- **ACL 변경 미반영**: 서버의 ACL 파일 감시 주기 30초 → 최대 30초 대기 또는 서버 재시작
- **ChromaDB 검색에서 권한 필터 미적용**: `curl -X POST http://localhost:8001/api/wiki/reindex` 실행

---

## Section 2: Modeling MVP (2026-04-12)

> Section 2는 코드 분석 → 도메인 매핑 → 영향분석 도구입니다. 아래 시나리오는 Neo4j가 실행 중이어야 합니다.

### 사전 준비
```bash
docker compose up -d neo4j   # Neo4j 시작 (7474/7687 포트)
# 백엔드/프론트엔드 시작 (기존과 동일)
```

### 시나리오 1: Java 프로젝트 파싱
1. 왼쪽 SectionNav에서 "Modeling" 클릭
2. "Code Graph" 탭 선택
3. Git URL 입력 (Java 프로젝트) → "Parse" 클릭
4. **확인**: 클래스, 메서드, 필드, 호출관계가 그래프로 표시

### 시나리오 2: SCOR 도메인 온톨로지 로드
1. "Domain Ontology" 탭 선택
2. "Load SCOR Template" 클릭
3. **확인**: Plan/Source/Make/Deliver/Return L1 프로세스 + L2 하위 프로세스 트리 표시
4. 노드 추가: Name/Kind/Parent 입력 → "Add" 클릭 → 트리에 반영

### 시나리오 3: 코드↔도메인 매핑
1. "Mapping" 탭 선택 → 3컬럼 뷰 (Code | Mappings | Domain)
2. Code entity + Domain node 선택 → "Add Mapping" 클릭
3. **확인**: 매핑 목록에 새 항목 (status: draft)
4. "Gaps" 클릭 → 매핑되지 않은 코드 엔티티 목록 표시

### 시나리오 4: 영향 분석 (Impact Analysis)
1. "Impact Analysis" 탭 선택
2. 검색어 입력 (예: "SafetyStockCalculator" 또는 "InventoryPlanning")
3. **확인**: 영향받는 도메인 프로세스 목록 + BFS 깊이 + 미매핑 엔티티 수 표시
4. 미매핑 용어 입력 → "매핑되지 않은 용어입니다" 메시지 표시

### 시나리오 5: 승인 워크플로우
1. "Approval" 탭 선택
2. 매핑 제출 (mapping code + domain 입력) → Pending 목록에 표시
3. Approve/Reject 클릭 → 상태 변경 확인

### 트러블슈팅
- Neo4j 연결 실패: `docker compose logs neo4j` 확인, 7687 포트 열려 있는지 체크
- "No module named 'neo4j'": `uv pip install neo4j tree-sitter tree-sitter-java`
- 프론트엔드에서 API 에러: Next.js proxy가 `/api/modeling/*`를 백엔드로 전달하는지 확인

---

## UI/UX Overhaul: Content-First Layout

### 시나리오 1: Collapsible Side Panels

1. 브라우저에서 위키 문서 열기
2. `Cmd+B` (macOS) 또는 `Ctrl+B` (Windows) → 왼쪽 TreeNav 사이드바가 접힘. 폴더 아이콘 스트립만 남음
3. 다시 `Cmd+B` 또는 스트립 클릭 → 사이드바 복원
4. `Cmd+J` → 오른쪽 AI 코파일럿 접힘. Sparkles 아이콘 스트립만 남음
5. 페이지 새로고침 → 접힘 상태 유지됨 (localStorage)
6. **확인**: 양쪽 패널 접으면 편집 영역이 화면 대부분 차지

### 시나리오 2: Unified Document Info Bar

1. 문서 열기 → 상단에 32px 높이의 Info Bar 표시
2. **확인**: Status 뱃지(approved/draft 등), Domain·Process, 신뢰도 점수 pill, 연결 문서 수 뱃지가 한 줄에 표시
3. 신뢰도 pill 클릭 → 6개 시그널 상세 팝오버 표시
4. 오래된 문서 → amber 점 표시 (stale 표시)
5. ✓ 아이콘 클릭 → "확인했음" 피드백 전송
6. ✎ 아이콘 클릭 → "수정 필요" 피드백 전송

### 시나리오 3: Document Info Drawer

1. Info Bar 오른쪽 ▼ 버튼 클릭 또는 `Cmd+I` → Drawer 오픈
2. **메타데이터 탭**: Domain, Process, Tags, Status, Related 편집 가능. AutoTag 버튼 작동
3. **신뢰도 탭**: 전체 시그널 breakdown, stale 경고, 최신 대안 문서, 피드백 상세
4. **연결 문서 탭**: supersedes/superseded_by, 역참조, 관련 문서, AI 추천 문서, 그래프 링크
5. Escape 또는 drawer 바깥 클릭 → Drawer 닫힘
6. **확인**: Drawer가 에디터 위에 overlay로 표시 (콘텐츠를 밀어내지 않음)

### 시나리오 4: 키보드 단축키

| 단축키 | 동작 |
|--------|------|
| Cmd+B | TreeNav 사이드바 토글 |
| Cmd+J | AI 코파일럿 토글 |
| Cmd+I | Document Info Drawer 토글 |
| Cmd+K | 검색 Command Palette |
| Cmd+S | 저장 |

### 시나리오 5: AI 코파일럿 팝아웃

1. AI 코파일럿 패널 상단 `↗` (ExternalLink) 아이콘 클릭
2. **확인**: AI 패널이 접히고, 화면 우하단에 floating window로 분리됨
3. 타이틀 바 드래그 → 창 이동 가능
4. 우하단 모서리 드래그 → 리사이즈 가능 (최소 360×300)
5. 타이틀 바의 `⊞` (PanelRightClose) 버튼 클릭 또는 `Cmd+J` → 패널로 복귀
6. **확인**: 팝아웃 상태에서도 채팅 입력/응답 정상 작동
7. **확인**: 패널 복귀 시 기존 채팅 히스토리 유지

### Troubleshooting

- **Drawer가 안 열림**: Cmd+I 확인. 소스 모드에서도 Drawer는 동작함
- **접힌 패널이 복원 안 됨**: localStorage에서 `ontong_panel_tree_collapsed`, `ontong_panel_ai_collapsed` 확인
- **신뢰도 pill이 안 보임**: 백엔드 서버(port 8001) 실행 여부 확인. confidence API 응답 필요
- **팝아웃 창이 안 보임**: 화면 밖에 있을 수 있음. 페이지 새로고침하면 우하단으로 초기화됨

---

## Phase A: 신뢰도 시그널 수정 + 사용자 ID 연결

### 시나리오 1: Backlink Count 작동 확인

1. 문서 A의 frontmatter에 `related: [문서B경로]` 추가 후 저장
2. `curl localhost:8001/api/wiki/confidence/문서B경로`
3. **확인**: `signals.backlinks` > 0 (이전에는 항상 0)

### 시나리오 2: Owner Activity 작동 확인

1. 문서 저장 (updated_by가 자동 기록됨)
2. `curl localhost:8001/api/wiki/confidence/해당문서경로`
3. **확인**: `signals.owner_activity` = 100 (90일 이내 편집한 사용자)

### 시나리오 3: 사용자 인증 API

1. `curl localhost:8001/api/auth/me`
2. **확인**: `{"id": "dev-user", "name": "개발자", "email": "dev@ontong.local", "roles": ["admin"]}`

### 시나리오 4: 프론트엔드 사용자 ID 통합

1. 브라우저에서 문서 편집 → 저장
2. frontmatter의 `updated_by` 확인 → "개발자" (이전: 랜덤 user-xxxxx)
3. 잠금(lock) 사용자 이름도 인증된 사용자명으로 표시

## Phase B: 사용자 피드백 데모

### 시나리오 5: TrustBanner에서 "확인했음" 피드백

1. 아무 문서 열기
2. 상단 신뢰도 배너 하단에 **"확인했음"** / **"수정 필요"** 버튼 확인
3. **"확인했음"** 클릭
4. **확인**: "확인 1회" 카운트 표시 + "(마지막 확인: 개발자, 방금 전)" 표시
5. 다시 클릭 → "확인 2회"로 증가

### 시나리오 6: TrustBanner에서 "수정 필요" 피드백

1. **"수정 필요"** 클릭
2. **확인**: "수정 요청 1회" 추가 표시
3. 신뢰도 점수가 피드백을 반영하는지 확인 (Phase C에서 점수 반영 예정)

### 시나리오 7: AICopilot 소스 피드백

1. AI 채팅에서 질문 → 답변 받기
2. 답변 하단 소스 카드 옆에 👍/👎 아이콘 확인
3. 👍 클릭 → 해당 문서에 thumbs_up 피드백 기록됨
4. **API 확인**: `curl localhost:8001/api/wiki/feedback/해당문서` → thumbs_up_count 증가

### 시나리오 8: Feedback API 직접 테스트

```bash
# 피드백 기록
curl -X POST localhost:8001/api/wiki/feedback/some-doc.md \
  -H "Content-Type: application/json" -d '{"action": "verified"}'
# → {"ok": true, "feedback": {"verified_count": 1, ...}}

# 피드백 조회
curl localhost:8001/api/wiki/feedback/some-doc.md
# → {"verified_count": 1, "needs_update_count": 0, ...}
```

---

## Phase C: 피드백 → 점수 통합 데모

### 시나리오 9: 피드백이 신뢰도 점수에 반영 확인

1. 문서의 현재 신뢰도 확인: `curl localhost:8001/api/wiki/confidence/{path}`
2. "확인했음" 피드백 3회 전송:
   ```bash
   curl -X POST localhost:8001/api/wiki/feedback/{path} \
     -H "Content-Type: application/json" -d '{"action": "verified"}'
   ```
3. 다시 신뢰도 확인 → `signals.user_feedback` = 100.0, 점수 상승 확인
4. "수정 필요" 피드백 3회 전송 → `signals.user_feedback` 하락 확인

### 시나리오 10: "확인했음"이 freshness도 갱신

1. Stale 문서(12개월+ 미수정) 선택
2. `curl localhost:8001/api/wiki/confidence/{path}` → `stale: true` 확인
3. "확인했음" 피드백 전송
4. 다시 confidence 확인 → `stale: false`, `signals.freshness` 상승
5. 문서 frontmatter의 `updated` 필드가 현재 시각으로 갱신 확인

### 시나리오 11: 가중치 변경 확인

```bash
curl localhost:8001/api/wiki/confidence/{path}
# signals 필드에 6개 시그널 확인:
# freshness(25%), status(25%), metadata_completeness(15%),
# backlinks(10%), owner_activity(10%), user_feedback(15%)
```

---

## Phase D: Knowledge Graph 데모

### 시나리오 12: Graph Stats 확인

```bash
curl localhost:8001/api/graph/stats
# → {"total_nodes": N, "total_edges": M, "type_distribution": {"related": X, "conflicts": Y}}
```

### 시나리오 13: 문서별 관계 조회

```bash
curl "localhost:8001/api/graph/SCM/공정-관리-기준-v1.md"
# → center, relationships: [{source, target, rel_type, strength, created_by, ...}]

# depth=2로 2-hop 탐색
curl "localhost:8001/api/graph/SCM/공정-관리-기준-v1.md?depth=2"

# rel_type 필터
curl "localhost:8001/api/graph/SCM/공정-관리-기준-v1.md?rel_type=related"
```

### 시나리오 14: 관계 자동 반영

1. 문서 A의 frontmatter에 `related: [문서B]` 추가 후 저장
2. `curl localhost:8001/api/graph/문서A` → "related" 관계 존재 확인
3. `curl localhost:8001/api/graph/문서B` → 역방향으로도 조회 가능

---

## 스케일 대비 + UI 자기설명 개선 데모

### 시나리오 1: 관련 문서 관리 — 사용 가이드

1. 좌측 사이드바 → **관련 문서 관리** 메뉴 열기
2. **"사용 가이드 보기"** 링크 클릭
3. **확인**:
   - 처리 순서 (전체 스캔 → AI 분석 → 해결 액션) 설명 표시
   - 유형별 의미: 사실 불일치(빨강), 범위 중복(노랑), 시간 차이(파랑), 무관(회색) + 각 설명
   - 해결 액션 4종: 범위 명시, 버전 체인, 병합 제안, 무시 + 각각 언제 사용하는지 설명
4. 가이드 닫기 → 토글 정상 작동

### 시나리오 2: 관련 문서 관리 — 페이지네이션

1. 전체 스캔 실행 (충분한 문서가 있는 경우)
2. 20건 이상 결과 시 하단에 페이지네이션 표시
3. **확인**: "전체 N건 중 1–20건" 표시, 이전/다음 버튼

### 시나리오 3: 관리가 필요한 문서 — 섹션 설명

1. 좌측 사이드바 → **관리가 필요한 문서** 메뉴 열기
2. **확인**:
   - 상단 안내 배너: 대시보드 설명 + 작성자 필터 안내
   - 각 섹션(오래된 문서/신뢰도 낮은 문서/미해결 관련 문서)에 설명 + "조치 방법:" 안내
   - 5건 이상인 섹션에 "나머지 N건 더 보기" 접기/펼치기 버튼
3. 빈 상태일 때: "모든 문서가 양호한 상태입니다" 안내 표시

### 트러블슈팅

| 증상 | 원인 | 해결 |
|------|------|------|
| 가이드 토글 안 보임 | ConflictDashboard 구버전 | 프론트엔드 빌드 확인 (npm run dev) |
| 페이지네이션 안 보임 | 결과 20건 미만 | 전체 스캔 + threshold 낮춰서 충분한 결과 생성 |
| 섹션 설명 안 보임 | MaintenanceDigest 구버전 | 프론트엔드 빌드 확인 |

---

## Part 2 데모 — 충돌 & Lineage (2A/2B/2C/2D)

### 사전 준비

```bash
# 서버 실행 확인
curl -s http://localhost:8001/health | python3 -m json.tool

# 충돌 전체 스캔 (threshold 0.85로 낮춰서 더 많은 쌍 감지)
curl -s -X POST "http://localhost:8001/api/conflict/full-scan?threshold=0.85"

# 5초 후 결과 확인
curl -s "http://localhost:8001/api/conflict/duplicates?filter=all&threshold=0.85"
```

예상 결과: 최소 2쌍 — `공정-관리-기준-v1 ↔ v2` (0.95), `test-create ↔ test-create2` (0.88)

---

### 시나리오 1: 충돌 대시보드 그룹핑 (2D)

1. 좌측 사이드바 → **문서 충돌 감지** 메뉴 열기
2. 임계값을 **0.85**로 조정 → **새로고침** 클릭
3. **확인**: 같은 문서가 여러 쌍에 걸쳐있으면 하나의 카드로 그룹핑
   - 주 문서가 위에, 충돌 문서들이 아래 들여쓰기로 표시
   - 각 충돌 문서마다 유사도 % + "나란히 비교" 버튼
4. **필터 탭**: "미해결" / "해결됨" / "전체" 전환 확인

---

### 시나리오 2: 폐기 처리 (기존 기능 확인)

1. 충돌 대시보드에서 `공정-관리-기준-v1.md` 카드 확인
   - v1은 이미 deprecated 상태일 수 있음 → 시나리오 3으로 이동
   - deprecated가 아니면: **"폐기(deprecated) 처리"** 버튼 클릭
2. **확인**: 버튼 클릭 후 카드가 반투명 + status "deprecated" 표시
3. "해결됨" 탭으로 전환 → 해당 쌍이 이동했는지 확인

---

### 시나리오 3: 폐기 되돌리기 (2B) ⭐ 신규

1. "해결됨" 또는 "전체" 탭에서 deprecated 문서 찾기
2. deprecated 문서 카드의 **"되돌리기"** 버튼 (녹색 ↻) 클릭
3. **확인**:
   - 토스트: "→ approved (복원됨)"
   - 카드가 다시 불투명 + status "approved"로 변경
   - "미해결" 탭으로 전환 → 해당 쌍이 다시 미해결로 표시
4. **Lineage 정리 확인**: 복원된 문서의 frontmatter에서 `superseded_by` 필드가 빈 값인지 확인
   ```bash
   # v1 문서 frontmatter 확인
   head -10 wiki/SCM/공정-관리-기준-v1.md
   ```

---

### 시나리오 4: 검색 결과 deprecated 뱃지 (2C) ⭐ 신규

> 이 테스트를 위해 먼저 문서 하나를 deprecated로 만들어야 합니다.

**준비:**
```bash
# v1을 다시 deprecated로 설정 (v2가 대체)
curl -s -X POST "http://localhost:8001/api/conflict/deprecate?path=SCM/공정-관리-기준-v1.md&superseded_by=SCM/공정-관리-기준-v2.md"
```

**테스트:**
1. 채팅에서 **"공정 관리 기준 알려줘"** 입력
2. 답변 하단 소스 목록 확인:
   - `공정-관리-기준-v1.md` → 빨간 취소선 + **"폐기됨"** 뱃지 + **"→ 새 버전"** 링크
   - `공정-관리-기준-v2.md` → 정상 표시 (approved 아이콘)
3. **"→ 새 버전"** 링크 클릭 → `공정-관리-기준-v2.md`가 에디터에서 열리는지 확인
4. deprecated 문서 자체를 클릭 → 에디터에서 열리지만 취소선/빨간색으로 구분됨

---

### 시나리오 5: Lineage 사이클 감지 (2A)

> 백엔드 로직 테스트 — UI에는 직접 보이지 않음. 로그로 확인.

```bash
# 의도적 사이클 생성: A → B → A
# 1) v1의 superseded_by를 v2로 설정 (이미 위에서 완료)
# 2) v2의 superseded_by를 v1으로 설정 (사이클!)
head -10 wiki/SCM/공정-관리-기준-v2.md
# superseded_by 필드에 v1 경로를 수동 입력 후 검색 시 로그 확인

# 채팅으로 "공정 관리 기준" 검색 → 백엔드 로그에서 확인:
# "Supersede cycle detected: SCM/공정-관리-기준-v1.md -> ... -> SCM/공정-관리-기준-v1.md"
```

이 시나리오는 edge case 방어 확인용 — 정상 운영 시에는 발생하지 않음.

---

### 트러블슈팅

| 증상 | 원인 | 해결 |
|------|------|------|
| 충돌 대시보드 비어있음 | 스캔 안 했거나 threshold 너무 높음 | "전체 스캔" 버튼 클릭 + threshold 0.85 |
| 되돌리기 버튼 안 보임 | 문서가 deprecated가 아님 | "해결됨" 또는 "전체" 탭에서 확인 |
| deprecated 뱃지 안 보임 | 검색 결과에 deprecated 문서가 없음 | deprecated 문서와 관련된 키워드로 검색 |
| "→ 새 버전" 링크 없음 | `superseded_by` 미설정 | deprecate API 호출 시 `superseded_by` 파라미터 포함 |

---

## 세션 37 데모 — Path-Aware RAG + 대화형 경로 명확화

### 배경
수십만 문서 엔터프라이즈 위키에서 "장애 대응 절차" 같은 쿼리는 인프라/SCM/ERP 등 여러 영역에 매칭. 기존엔 경로 정보를 RAG에 활용하지 않아 도메인이 섞인 결과를 반환.

### 접근
4-Layer 설계: (L1) 경로 프리픽스 임베딩, (L2) path_depth 메타데이터 필터, (L3) 경로 분산 감지→대화형 명확화, (L4) 세션 경로 부스트 리랭크.

### 데모 시나리오

#### 1. 경로 임베딩 효과 확인
1. 채팅에서 "인프라 캐시 장애 대응" 입력
2. 기대: 인프라 문서가 상위 노출 (path_depth_1 필터 + 경로 프리픽스 임베딩 효과)

#### 2. 경로 명확화 (핵심 기능)
1. 채팅에서 도메인 모호한 질문 입력 (예: "장애 대응 절차")
2. 결과가 3개 이상 경로에 분산되면 → 버튼형 명확화 질문 표시
3. "인프라" 버튼 클릭 → 인프라 장애 대응 문서 기반 답변
4. 후속 질문 "캐시 관련은?" → 세션 path_preference로 인프라 문서 자동 우선

#### 3. 환경변수 토글
- `ONTONG_PATH_DISAMBIG_ENABLED=false` → 명확화 비활성 (기존 동작)
- `ONTONG_PATH_BOOST_WEIGHT=0` → 부스트 비활성
- `ONTONG_PATH_EMBED_ENABLED=false` → 경로 프리픽스 없이 인덱싱 (재인덱싱 필요)

### 측정
- 기존 RAG 테스트 12개 쿼리: hit@5=1.0, MRR=1.0 유지 (회귀 없음)
- 경로 필터 적용 검색: 인프라 문서만 반환 확인
- path_depth_1/2/stem 메타데이터 ChromaDB 저장 확인

### 트러블슈팅
- 명확화 안 뜸: `ONTONG_PATH_DISAMBIG_MIN_PATHS` 값 확인 (기본 3). 현재 문서가 적으면 3개 경로에 분산되지 않을 수 있음.
- 재인덱싱 필요 시: `curl -X POST "http://localhost:8001/api/wiki/reindex?force=true" -H "Authorization: Bearer test-token"`

---

## 세션 36 데모 — 태그 자동화 고도화 (Phase A+B)

### 배경
기존 AutoTag는 도메인 무관 top-100 태그에서 추천 → 중복/오분류 발생. 또 태그는 저장만 되고 RAG 검색에 반영되지 않음.

### 접근
- **Phase A**: 2-pass 추론 (domain→tags), 경로/이웃/관련문서 신호, 7개 few-shot, **always-normalize** (거리 3층), Soft alternatives UI
- **Phase B**: 쿼리→태그 의미매칭, RAG 검색 후 태그 교집합 부스트 rerank, domain 0건 시 태그-only fallback

### 데모 시나리오
1. **Auto-Tag 정규화 확인** — 인프라 디렉토리 문서(예: `wiki/인프라/캐시-장애-대응-매뉴얼.md`) 편집 → MetadataBar "Auto-Tag" 클릭 → `Redis→레디스`, `캐싱→캐시`, `장애대응→장애처리` 자동 치환 토스트
2. **Soft alternatives 칩** — 신규 추천 태그 옆에 `→ SOP (14건)` 같은 기존 태그 칩이 보이고 클릭 시 치환됨
3. **도메인 정확도** — SCM 문서에는 인프라 태그가 나오지 않음 (2-pass 스코핑 효과)
4. **RAG 채팅** — "캐시 장애 어떻게 대응해" / "월말 결산 절차" → 정답 문서가 상위 노출 (tag boost 효과)

### 측정 (`tests/fixtures/*.json`)
- `auto_tag_baseline.json`: domain 정확도 **100%** (27/27), 평균 confidence 0.85, 자동 치환 22건
- `rag_eval_baseline.json`: baseline hit@5 **1.0**, MRR **1.0** (12 쿼리)

### 트러블슈팅
- Auto-Tag가 10~15초 걸림 → 2-pass + 정규화 LLM confirm 때문. 정상.
- alternatives 칩이 안 보임 → 해당 태그가 이미 기존 태그와 충분히 가까워 자동 치환됐거나 (`tag_replaced`), 유사 후보가 0.65 이상으로 멀리 있음

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
2. **태그 브라우저**: Tags 아이콘 클릭 → Domain/Process 트리 + Tags 표시
   - Domain 클릭 → 하위 Process 목록 펼침 (프로세스 수 표시)
   - Process 클릭 → 해당 문서 목록 lazy 로딩 (문서 수 표시)
   - 문서 클릭 → 탭으로 열기
3. 태그 뱃지 클릭 → 해당 태그가 달린 문서 목록 표시 → 문서 클릭 시 탭으로 열림
4. **관리**: Settings 아이콘 클릭 → "메타데이터 템플릿" / "미태깅 문서" 메뉴
5. "메타데이터 템플릿" 클릭 → Workspace에 관리 탭 열림 → Domain-Process 트리 + Tags 관리
   - 도메인 클릭 → 하위 프로세스 목록 펼침 + 관련 문서 수 표시
   - 프로세스 클릭 → 해당 프로세스 문서 목록 lazy 로딩
   - 문서 클릭 → 해당 파일 탭으로 열기
   - 도메인/프로세스 추가·삭제 가능, Tags는 별도 섹션에서 관리
6. "미태깅 문서" 클릭 → 미태깅 목록 + 태그 통계 → "일괄 자동 태깅" 버튼
7. 에러코드 자동 추출: DG320 등이 본문에 있는 문서 저장 시 frontmatter에 자동 주입 확인

### ZZ. 태그 품질 시스템 (세션 34)

> 태그 분산 방지 + 유사 태그 병합 + 고아 태그 정리 기능입니다.
> 테스트 전 **백엔드 재시작** 필수 (tag_registry ChromaDB 초기화).

#### 사전 준비

```bash
# 백엔드 재시작 (tag_registry 초기화 필요)
# 기존 uvicorn 프로세스 종료 후:
cd ~/workspace/ai/onTong
source venv/bin/activate
set -a && source .env && set +a
uvicorn backend.main:app --host 0.0.0.0 --port 8001

# 리인덱스 (샘플 문서 반영)
curl -X POST "http://localhost:8001/api/wiki/reindex?force=true"
```

#### 테스트용 샘플 데이터 (이미 생성됨)

의도적으로 분산된 태그가 포함된 문서:

| 파일 | 분산 태그 |
|------|----------|
| `인프라/캐시-장애-대응-매뉴얼.md` | **캐시**, Redis, **장애대응** |
| `인프라/캐싱-전략-가이드.md` | **캐싱**, 성능최적화 |
| `인프라/cache-troubleshooting.md` | **cache**, **레디스** |
| `인프라/서버-장애처리-절차.md` | **장애처리**, SOP |
| `인프라/네트워크-보안-정책.md` | 네트워크, 보안정책, 방화벽 |
| `SCM/재고-실사-절차.md` | 재고관리, **희귀태그테스트** (고아) |

#### ZZ-1. 태그 건강도 대시보드 (브라우저)

1. 사이드바 관리 → "메타데이터 템플릿" 클릭
2. 페이지 하단 **"태그 건강도"** 섹션 확인
3. **"분석 실행"** 클릭
4. 확인 사항:
   - **유사 태그 그룹**: "캐시"/"캐싱"/"cache", "장애대응"/"장애처리", "Redis"/"레디스" 등 그룹 표시
   - **고아 태그**: "희귀태그테스트" 등 1건 이하 사용 태그 노란색 뱃지
5. 유사 그룹에서 **병합 버튼** 클릭 (예: `"캐싱" → "캐시"`)
   - 확인 다이얼로그 → "확인"
   - 성공 토스트 + 해당 문서의 태그가 자동 변경됨

#### ZZ-2. Smart Friction — 수동 태그 입력 (브라우저)

1. 아무 `.md` 문서 열기 → MetadataTagBar 펼치기 (Metadata 클릭)
2. Tags 입력란에 **"캐싱"** 입력 후 Enter
3. 확인 사항:
   - "유사한 태그가 있습니다" 프롬프트 표시
   - **"캐시 (N건)"** 버튼이 표시됨
   - [캐시 사용] 클릭 → "캐시"가 태그로 추가됨
4. 다시 **"장애처리"** 입력 후 Enter
   - "장애대응 (N건)" 유사 태그 제안 확인
5. **"그래도 '장애처리' 생성"** 클릭 → 새 태그로 강제 생성 확인

#### ZZ-3. 태그 건수 자동완성 (브라우저)

1. Tags 입력란에 **"캐"** 입력
2. 드롭다운에 태그 + **건수** 표시 확인:
   - `캐시  2건`
   - `캐싱  1건`
3. 건수가 큰 "캐시"를 자연스럽게 선택하도록 유도

#### ZZ-4. 유사 태그 API 확인 (터미널)

```bash
# 유사 태그 검색
curl "http://localhost:8001/api/metadata/tags/similar?tag=%EC%BA%90%EC%8B%B1&top_k=5"
# → "캐시", "cache" 등 유사 태그 반환 (서버 재시작 후에만 작동)

# 유사 그룹 조회 (default threshold=0.55)
curl "http://localhost:8001/api/metadata/tags/similar-groups"
# → 정책↔보안정책, 장애대응↔장애처리, 캐싱↔캐시, Redis↔cache 4그룹

# 고아 태그 조회
curl "http://localhost:8001/api/metadata/tags/orphans?min_docs=1"
# → 1건 이하 사용 태그 목록

# 태그 병합
curl -X POST "http://localhost:8001/api/metadata/tags/merge?source=%EC%BA%90%EC%8B%B1&target=%EC%BA%90%EC%8B%9C"
# → {"merged": "캐싱", "into": "캐시", "updated_documents": 1}
```

#### ZZ-5. LLM 자동태깅 정규화 (브라우저 — LLM API 키 필요)

> ⚠️ 이 테스트는 LLM API 호출이 발생합니다. 최소한으로만 테스트하세요.

1. 미태깅 문서 하나를 열거나, 기존 문서의 Auto-Tag 버튼 클릭
2. 확인 사항:
   - 제안된 태그가 기존 태그(캐시, 장애대응 등)와 **동일한 이름**으로 나오는지 확인
   - Layer 1: LLM이 프롬프트의 기존 태그 목록에서 선택
   - Layer 2: 새 태그 제안 시 임베딩 유사 검색으로 기존 태그로 자동 치환
3. 백엔드 로그에서 `Tag auto-normalized` 또는 `Tag LLM-normalized` 메시지 확인

#### ZZ-6. 트러블슈팅

| 증상 | 원인 | 해결 |
|------|------|------|
| 유사 태그 검색 결과 비어있음 | tag_registry 미초기화 | **백엔드 재시작** 필수 |
| 유사 그룹이 안 나옴 | 태그 수가 너무 적거나 threshold 낮음 | threshold=0.60으로 올려서 재시도 (OpenAI 임베딩은 단문에서 거리가 큼) |
| Smart Friction 프롬프트 안 나옴 | 유사 태그가 없거나 tag_registry 미연결 | 백엔드 재시작 + reindex |
| 건수 표시 안 됨 | `onSearchWithCount` 미연동 | 프론트 재시작 후 확인 |
| 병합 후 문서 태그 안 바뀜 | 캐시 | 브라우저 새로고침 후 문서 다시 열기 |

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

---

## 🏗️ 3-Section Platform v2 아키텍처 (계획 단계)

> **현재 상태**: Phase 0 진행 중 (6/17 완료) — 스캐폴딩 + 개발자 C 환경 준비 완료
> **상세 문서**: `toClaude/reports/platform_architecture_v2.md`

### 플랫폼 구조 개요

| Section | 용도 | 주 사용자 | 담당 |
|---------|------|-----------|------|
| Section 1 (Wiki) | 문서 관리 + AI Q&A | 전체 | 기존 시스템 유지 |
| Section 2 (Modeling) | 코드매핑/온톨로지/영향분석/시뮬실행 | IT 담당자 | 팀 리더 |
| Section 3 (Simulation) | 시나리오 설계/시각화 | SCM 현업 | 개발자 C |

### 핵심 설계 결정

1. **에이전트 독립**: 섹션마다 독립 에이전트 (shared에는 Protocol만)
2. **시뮬레이션 2종 분리**: 코드 영향분석(그래프 BFS) + 비즈니스 시뮬(Monte Carlo 등)
3. **온톨로지**: SCOR + ISA-95 하이브리드, Neo4j Community 저장
4. **Typed Contract**: `dict` 금지, 시나리오별 Pydantic 모델 필수
5. **비동기 Job Queue**: 시뮬레이션은 POST → job_id → 폴링/SSE
6. **매핑 신뢰도**: 0.95+ 자동승인, 0.80-0.95 IT리뷰, 0.60-0.80 합동리뷰, <0.60 거부

### Phase 0 데모 시나리오

**0-1. 섹션 네비게이션 확인** (구현 완료)
1. `http://localhost:3000` 접속
2. 상단 [Wiki] / [Modeling] / [Simulation] 탭 확인
3. 각 탭 클릭 시 해당 섹션 렌더링 확인
4. Wiki 탭에서 기존 3-pane 레이아웃 정상 동작

**0-2. Simulation 시나리오 목록 확인** (구현 완료)
1. Simulation 탭 클릭
2. 좌측에 3개 시나리오 (수요 예측, 재고 최적화, 리드타임 영향 분석) 표시
3. API 연동 확인:
```bash
curl http://localhost:8001/api/simulation/scenarios | python -m json.tool
curl http://localhost:8001/api/simulation/health
curl http://localhost:8001/api/modeling/health
```

**0-3. Mock 시뮬레이션 실행 확인** (구현 완료)
```bash
curl -X POST http://localhost:8001/api/simulation/scenario \
  -H "Content-Type: application/json" \
  -d '{"scenario_type":"demand_forecast","parameters":{"scenario_type":"demand_forecast","product_id":"PROD-001","forecast_horizon_days":30},"output_formats":["chart_line","table"]}' \
  | python -m json.tool
# → job_id, status=completed, result.outputs에 chart_line + table 확인
```

**0-4. shared 인프라 구조 확인** (구현 완료)
```bash
# 디렉토리 구조 확인
tree backend/shared/ -L 2
tree backend/simulation/ -L 2
tree backend/modeling/ -L 2

# import-linter 모듈 경계 검증 (미구현)
# lint-imports
```

**0-5. Wiki 마이그레이션 확인** (미구현)
- 기존 Wiki 기능이 `backend/wiki/` 아래에서 정상 동작
- 기존 테스트 전체 통과

**0-3. Section 2/3 스캐폴딩 확인**
```bash
# Section 2 API placeholder 응답
curl http://localhost:8000/api/v1/modeling/health

# Section 3 API placeholder 응답
curl http://localhost:8000/api/v1/simulation/health
```

**0-4. Neo4j 연결 확인**
```bash
# Neo4j Community 연결 테스트
curl http://localhost:7474/
```

### Phase 1 데모 시나리오 (구현 후 검증 예정)

**1-1. 코드 파싱 + 온톨로지 적재**
- tree-sitter로 코드 파싱 → 엔티티 추출
- Neo4j에 3-Layer 온톨로지 적재 (Domain / Code / Mapping)

**1-2. 코드 영향분석**
- 특정 함수 변경 시 영향받는 엔티티 목록 반환
- 그래프 BFS 기반 결정론적 분석

**1-3. 매핑 신뢰도 검증**
- 4-factor scoring (self_consistency + AST + embedding + body_relevance)
- 신뢰도 임계값별 자동/리뷰/거부 동작 확인

### Phase 2 데모 시나리오 (구현 후 검증 예정)

**2-1. 비즈니스 시뮬레이션 실행**
- Section 3에서 시나리오 선택 → Section 2 API 호출
- Job ID 발급 → 진행률 SSE → 결과 반환

**2-2. 시각화 대시보드**
- 시뮬레이션 결과 차트/테이블 동적 렌더링
- 시나리오 비교 기능

### 트러블슈팅 (공통)

| 증상 | 원인 | 해결 |
|------|------|------|
| Neo4j 연결 실패 | Docker 미실행 | `docker-compose up -d neo4j` |
| import-linter 위반 | 섹션 간 직접 import | shared Protocol 경유로 변경 |
| Section 2↔3 통신 오류 | typed contract 불일치 | `shared/contracts/simulation.py` 확인 |
| 시뮬레이션 타임아웃 | job queue 미동작 | 백엔드 로그 + job status 확인 |

---

## 에이전트 고도화 (AG-1) 데모 시나리오

### AG-1-4: 구조화된 대화 요약

**테스트 시나리오**: 긴 대화에서 맥락 유지 확인

1. 10회 이상 대화를 주고받으며 다양한 주제 질문
2. 이전 대화에서 언급된 문서/주제를 참조하는 질문
3. 기대: 에이전트가 이전 대화 맥락을 자연스럽게 유지

**검증 포인트**:
- 대화가 토큰 예산(4000) 초과 시 이전 내용이 구조화 요약으로 전환
- 요약에 "대화 규모", "이전 요청", "참조된 문서" 포함
- 요약의 존재를 인정하는 메타 발언 없음 ("이전 대화를 요약하면..." 금지)

### AG-1-5: Continuation Instruction

**테스트 시나리오**: 요약 후 자연스러운 이어가기

1. 긴 대화 후 이전 주제에 대한 후속 질문
2. 기대: "이전 대화를 보면..." 같은 표현 없이 바로 답변
3. 기대: 주제가 완전히 바뀌면 이전 맥락을 섞지 않음

### AG-1-6: Query Augment + 주제 전환 감지

**테스트 시나리오**: 주제 전환 시 컨텍스트 오염 방지

1. "후판 공정계획 알려줘" → "담당자 누구야?" (후속 질문 — topic_shift=false)
   - 기대: 쿼리가 "후판 공정계획 담당자"로 보강됨
2. "후판 공정계획 알려줘" → "회의실 예약 방법은?" (주제 전환 — topic_shift=true)
   - 기대: 이전 히스토리가 답변에 영향 안 줌
3. thinking step에서 "[주제 전환]" 라벨 확인

**검증 포인트**:
- thinking_step에 쿼리 보강 결과 표시
- 주제 전환 감지 시 히스토리가 LLM에 전달되지 않음
- 프롬프트에 "주어/목적어 복원" 규칙 포함

---

## 에이전트 고도화 (AG-2~4) 데모 시나리오

### AG-2-3: SkillResult feedback 필드

**테스트 시나리오**: deprecated 문서 필터링 경고

1. deprecated 상태의 문서가 있는 주제로 검색
2. 기대: 검색 결과에서 deprecated 문서가 제외됨
3. 기대: 서버 로그에 "Excluded deprecated docs" 출력

**검증 방법**:
```bash
# 서버 로그 확인
tail -f /tmp/ontong_backend.log | grep -i "deprecated\|feedback"
```

**검증 포인트**:
- wiki_search에서 deprecated 문서 필터 후 feedback 문자열 반환
- rag_agent에서 thinking_step "info" 이벤트로 표시

### AG-3-1: 세션 JSONL 영속성

**테스트 시나리오**: 서버 재시작 후 대화 복원

1. 채팅에서 여러 메시지 주고받기
```bash
curl -s -N -X POST http://localhost:8001/api/agent/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer test-token" \
  -d '{"message":"장애대응 플레이북 알려줘","session_id":"demo-persist"}' \
  --max-time 20 | head -5
```

2. JSONL 파일 확인
```bash
cat data/sessions/demo-persist.jsonl
```

3. 서버 재시작 후 동일 session_id로 후속 질문
```bash
# 서버 재시작
kill $(lsof -ti:8001); sleep 2
venv/bin/python -m backend.main &>/tmp/ontong_backend.log &
sleep 4

# 동일 세션으로 후속 질문
curl -s -N -X POST http://localhost:8001/api/agent/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer test-token" \
  -d '{"message":"아까 그 플레이북에서 P1 기준은?","session_id":"demo-persist"}' \
  --max-time 20 | head -5
```

**검증 포인트**:
- `data/sessions/{session_id}.jsonl`에 user/assistant 메시지 기록
- 서버 재시작 후 이전 대화 맥락 유지
- 후속 질문에서 이전 답변 참조 가능

### AG-3-2: 스킬 권한 매핑

**테스트 시나리오**: viewer 역할로 문서 편집 차단

```bash
# 직접 run_skill 호출 (Python)
venv/bin/python -c "
import asyncio
from unittest.mock import MagicMock
# (모듈 스텁 생략)
from backend.application.agent.context import AgentContext

ctx = AgentContext(
    request=MagicMock(), chroma=MagicMock(), storage=MagicMock(),
    session_store=MagicMock(), user_roles=['viewer'], intent_action='edit',
)
r = asyncio.run(ctx.run_skill('wiki_edit'))
print(f'success={r.success}, error={r.error}, hint={r.retry_hint}')
# 기대: success=False, error='권한 부족...', hint='관리자에게...'
"
```

**검증 포인트**:
- viewer → wiki_edit: `권한 부족` 에러 + retry_hint 반환
- editor/admin → wiki_edit: 권한 통과
- viewer → wiki_search (READ): 정상 허용

### AG-4-1: Q&A ReAct 자율 검색

**테스트 시나리오**: 관련도 낮을 때 자동 재검색

```bash
# 직접 _evaluate_search_results 호출 (Python)
venv/bin/python -c "
import asyncio, os, sys
# (.env 로딩 생략)
from backend.application.agent.rag_agent import RAGAgent
from unittest.mock import MagicMock

agent = RAGAgent(chroma=MagicMock(), storage=MagicMock())

# 관련도 20% (threshold 25% 미만) → LLM 평가 트리거
r = asyncio.run(agent._evaluate_search_results(
    query='2025년에 변경된 연차 규정 알려줘',
    search_query='연차 규정',
    documents=['서버 관리 규정 문서입니다...'],
    metadatas=[{'path':'/서버관리/규정.md'}],
    distances=[0.80],
    ctx=MagicMock(),
))
print(f'sufficient: {r[\"sufficient\"]}')
print(f'reason: {r[\"reason\"]}')
print(f'retry_query: {r[\"retry_query\"]}')
# 기대: sufficient=False, retry_query에 구체화된 검색어
"
```

**검증 포인트**:
- 관련도 40%+ → rule-based fast-path (LLM 호출 없이 즉시 sufficient)
- 관련도 25% 미만 → LLM이 insufficient 판단 + 재검색 쿼리 생성
- 재검색 쿼리가 원본과 다름 (구체화/동의어/날짜 추가)
- 최대 3턴 후 중단 (무한 루프 방지)
- 빈 결과 → 즉시 insufficient (LLM 호출 없음)

### AG-4-2: 재검색 전략 5단계

**검증 방법**: qa_react.md 프롬프트 내용 확인
```bash
cat backend/application/agent/skills/prompts/qa_react.md
```

**검증 포인트**:
- 구체화 → 시간 → 동의어 → 상위개념 전략 포함
- 충분성 체크리스트 (핵심 키워드, 시간 범위, 구체적 수치) 포함
- 비용 통제 규칙 (부분 충분 → sufficient=true) 포함

---

## 에이전트 고도화 v3 전체 데모 체크리스트

| # | 항목 | 검증 방법 | 상태 |
|---|------|----------|------|
| 1 | ontong.md 인격 적용 | 채팅에서 톤/스타일 확인 | |
| 2 | 토큰 히스토리 | 10회+ 대화 후 맥락 유지 | |
| 3 | 구조화된 요약 | 긴 대화 → 요약 메타발언 없음 | |
| 4 | topic_shift | 주제 전환 후 오염 없음 | |
| 5 | 프롬프트 .md 분리 | prompts/ 디렉토리 5개 파일 | |
| 6 | Cognitive Reflect 제거 | thinking_step에 cognitive_reflect 없음 | |
| 7 | 스킬 도구 풀 제한 | question intent → wiki_write 차단 | |
| 8 | SkillResult feedback | deprecated 문서 경고 로그 | |
| 9 | 세션 JSONL 영속성 | 재시작 후 대화 복원 | |
| 10 | 스킬 권한 매핑 | viewer → WRITE 차단 | |
| 11 | ReAct 자율 검색 | 낮은 관련도 → 재검색 | |
| 12 | 재검색 전략 | qa_react.md 5단계 전략 | |

### AG-3-3: PreSkill/PostSkill 훅 시스템

**검증 방법**: 훅 동작 확인 (백엔드 로그 + 채팅)

1. **QuerySanitizeHook (pre-hook)**: 공백 과다 쿼리 정리
   ```
   채팅에 "  후판    공정   계획  " 입력 (공백 과다)
   ```
   - 백엔드 로그에서 `QuerySanitizeHook` 로그 확인
   - 검색 결과가 정상적으로 반환됨 (공백이 정리된 쿼리로 검색)

2. **DeprecatedDocHook (post-hook)**: 폐기 문서 경고
   - deprecated 상태 문서가 검색 결과에 포함되면 feedback에 경고 추가
   - 백엔드 로그: `Search feedback: 폐기(deprecated) 문서 N건이 검색 결과에 포함`

3. **빈 쿼리 차단**: 공백만 입력 시 훅이 차단
   - QuerySanitizeHook이 `allow=False` 반환 → 검색 실행 안 됨

4. **pytest 확인**:
   ```bash
   python3 -m pytest tests/test_ag33_hooks.py -v
   # 14/14 PASSED (CompletionStatus 5, HookRegistry 6, BuiltinHooks 3)
   ```

**확인 포인트**:
- 훅 등록: 백엔드 시작 로그에 "Default hooks registered" 출력
- pre-hook 차단 시 SkillResult.status == BLOCKED
- post-hook feedback 주입 시 status == DONE_WITH_CONCERNS

### AG-3-3b: CompletionStatus 확장

**검증 방법**: SkillResult 상태 4단계 확인

| 상태 | 값 | 트리거 조건 | 확인 방법 |
|------|-----|-------------|-----------|
| DONE | `done` | 정상 완료 | 일반 질문 → 답변 정상 |
| DONE_WITH_CONCERNS | `concerns` | 완료 + 경고 | deprecated 문서 포함 검색 |
| BLOCKED | `blocked` | 진행 불가 | 권한 없는 사용자의 WRITE 시도 |
| NEEDS_CONTEXT | `needs_context` | 사용자 확인 필요 | (에이전트가 명시적으로 설정 시) |

```bash
# 자동 상태 추론 확인 (pytest)
python3 -m pytest tests/test_ag33_hooks.py::TestCompletionStatus -v
```

### AG-4-3: 사용자 확인 루프 (ClarificationRequestEvent)

**검증 방법**: SSE 이벤트 타입 + 프론트엔드 타입 확인

1. **백엔드 스키마 확인**:
   ```bash
   python3 -c "from backend.core.schemas import ClarificationRequestEvent; print(ClarificationRequestEvent.model_fields.keys())"
   # dict_keys(['event', 'request_id', 'question', 'options', 'context'])
   ```

2. **ChatRequest에 clarification_response_id 필드 존재**:
   ```bash
   python3 -c "from backend.core.schemas import ChatRequest; print('clarification_response_id' in ChatRequest.model_fields)"
   # True
   ```

3. **AgentContext.emit_clarification() 유틸리티**:
   ```bash
   python3 -c "
   from backend.application.agent.context import AgentContext
   sse = AgentContext.emit_clarification('어떤 공정을 말씀하시나요?', ['후판', '열연', '냉연'])
   print(sse[:80])
   "
   # event: clarification_request\ndata: {"event":"clarification_request",...
   ```

4. **프론트엔드 타입 동기화**: `npx tsc --noEmit` 에러 없음

### Per-Skill Allowed Tools (스킬별 도구 제한)

**검증 방법**: 스킬 생성 → allowed-tools 확인

1. **UI에서 생성**:
   - 좌측 사이드바 → ⚡ 스킬 탭 → + 버튼 → 톱니바퀴 (고급)
   - "고급 설정 (6-Layer)" 펼치기
   - 하단 **"허용 도구 (Allowed Tools)"** 에서 원하는 도구 체크
   - 생성 후 wiki 파일에서 `allowed-tools:` YAML 확인

2. **API로 확인**:
   ```bash
   # 스킬 생성 (allowed-tools 포함)
   curl -s http://localhost:8001/api/skills/ -X POST \
     -H "Content-Type: application/json" \
     -d '{
       "title": "테스트 도구 제한",
       "trigger": ["도구테스트"],
       "allowed_tools": ["wiki_search", "llm_generate"]
     }' | python3 -m json.tool

   # allowed_tools 필드 확인
   curl -s http://localhost:8001/api/skills/ | python3 -c "
   import json, sys
   data = json.load(sys.stdin)
   for s in data.get('system', []) + data.get('personal', []):
       if s.get('allowed_tools'):
           print(f\"{s['title']}: {s['allowed_tools']}\")
   "
   ```

3. **동작 확인**: allowed_tools가 설정된 스킬 선택 후 질문 → context.py에서 user_skill.allowed_tools가 INTENT_ALLOWED_SKILLS보다 우선 적용

### 스킬 UX 개선 — 사용자 교육 & 가이드

**검증 방법**: 브라우저에서 직접 확인

1. **소개 배너 (일회성)**:
   - ⚡ 스킬 탭 클릭 → 상단에 "스킬이란?" 배너 표시
   - X 클릭 → 배너 사라짐
   - 페이지 새로고침 → 배너 다시 안 나타남
   - (리셋: 개발자도구 → `localStorage.removeItem("ontong:skill-intro-dismissed")`)

2. **빈 상태 CTA**:
   - 스킬 0개 상태 → "아직 만든 스킬이 없습니다" + Zap 아이콘
   - "+ 첫 번째 스킬 만들기" 클릭 → 인라인 생성 폼 열림
   - 공용 스킬 빈 상태 → "범위를 '공용'으로 선택하면..." 안내

3. **채팅 피커 교육**:
   - 채팅 입력란 ⚡ 버튼 클릭 → 드롭다운 상단에 "스킬을 적용하면 AI가 정해진 역할과 형식으로 답변합니다" 서브텍스트
   - 스킬 0개일 때: "왼쪽 사이드바 ⚡ 탭에서 스킬을 만들어보세요" 안내

4. **자동 제안 교육**:
   - 트리거 키워드 매칭 시 배너에 "입력 내용에 맞는 스킬이 있습니다" 부연

5. **생성 다이얼로그 개선**:
   - 톱니바퀴 → 고급 생성 열기
   - 헤더: Zap 아이콘 + "이름과 설명만 입력해도 바로 사용할 수 있습니다"
   - 트리거 라벨: "— 이 단어가 포함되면 자동 제안" 힌트
   - 고급 설정 펼치면: "각 항목은 선택 사항입니다. 필요한 것만 채우세요"
   - 6-Layer 라벨에 각각 한 줄 설명 (역할→"AI의 페르소나와 톤" 등)

6. **탭 툴팁**:
   - 좌측 하단 ⚡ 아이콘에 마우스 올리면 "스킬 — AI 응답을 커스터마이징하는 템플릿" 표시

### 사용자별 AI 페르소나 설정 (자유 마크다운)

**검증 방법**: 브라우저 + curl

1. **파일 열기**:
   - AICopilot 헤더 → 톱니바퀴(Settings) 아이콘 클릭
   - 워크스페이스에 `ontong.local.md` 탭이 열림
   - 처음이면 가이드 템플릿 표시 (나에 대해/응답 스타일/참고 사항)

2. **자유롭게 편집**:
   - Tiptap 에디터로 마크다운 자유 작성
   - 예시:
     ```
     ## 나에 대해
     물류팀 DevOps 엔지니어. 인프라/배포 관련 문서를 주로 본다.

     ## 응답 스타일
     - 캐주얼하게 답변해줘
     - 코드 예시 항상 포함
     - 영어 기술 용어 번역하지 마
     - 표 형식으로 정리해줘
     ```
   - 저장 (Ctrl+S 또는 자동저장)

3. **답변 톤 비교**:
   - 편집 전: "휴가 규정 알려줘" → 기본 톤 답변
   - 편집 후: 같은 질문 → 커스텀 스타일 적용된 답변
   - 캐시 최대 60초 후 반영 (저장 시 즉시 무효화됨)

4. **빈 템플릿 확인**:
   - 가이드 주석만 있고 실제 내용 미작성 → 프롬프트에 주입되지 않음 (정상)

5. **API 직접 확인**:
   ```bash
   # 파일 없으면 템플릿 생성
   curl -X POST http://localhost:8001/api/persona/ensure
   # → {"path": "_personas/@개발자/ontong.local.md", "created": true}

   # 캐시 수동 무효화
   curl -X POST http://localhost:8001/api/persona/invalidate
   ```

6. **저장 파일 확인** (서버 측):
   - `wiki/_personas/@개발자/ontong.local.md` 파일 존재 확인
   - 자유 마크다운 내용이 그대로 저장됨

---

### 스킬 크리에이터 6-Layer + 참조 문서 (기존 확인)

**검증 방법**: 고급 생성 → 모든 필드 동작

1. 톱니바퀴 → 고급 생성 다이얼로그
2. 역할/지시사항/워크플로우/체크리스트/출력형식/제한사항 각각 입력
3. 참조 문서 피커: 문서 검색 → 선택 → 뱃지 표시 → X로 제거
4. 허용 도구: 체크박스 선택 → 생성
5. 생성된 스킬 파일 열기 → YAML frontmatter에 `allowed-tools:` 포함 확인
6. 스킬 내용에 `[[문서명]]` 위키링크 포함 확인

---

### 에이전트 고도화 전체 데모 체크리스트 (v3 최종)

| # | 기능 | 데모 시나리오 | 통과 |
|---|------|--------------|------|
| 1 | ontong.md 인격 | "안녕" → 톤 확인 | |
| 2 | 토큰 기반 히스토리 | 8턴 이상 대화 → 맥락 유지 | |
| 3 | 구조화된 요약 | 긴 대화 후 요약 확인 (로그) | |
| 4 | 주제 전환 감지 | 다른 주제 질문 → 이전 맥락 안 섞임 | |
| 5 | Query Augment | 후속 질문 → 보강된 쿼리 확인 | |
| 6 | SkillResult feedback | deprecated 문서 → 경고 | |
| 7 | 스킬별 도구 풀 제한 | allowed_tools 설정 스킬 동작 | |
| 8 | 파이프라인 병렬화 | thinking_step SSE 순서 확인 | |
| 9 | 세션 JSONL 영속성 | 서버 재시작 후 대화 복원 | |
| 10 | 스킬 권한 매핑 | viewer → WRITE 차단 | |
| 11 | ReAct 자율 검색 | 낮은 관련도 → 재검색 | |
| 12 | 재검색 전략 | qa_react.md 5단계 전략 | |
| 13 | **훅 시스템** | 공백 과다 쿼리 → 정리 후 검색 | |
| 14 | **CompletionStatus** | DONE/BLOCKED/CONCERNS 상태 확인 | |
| 15 | **사용자 확인 루프** | ClarificationRequestEvent 스키마 확인 | |
| 16 | **Per-skill allowed-tools** | 스킬 생성 → 도구 제한 동작 | |
| 17 | **스킬 UX 교육** | 소개 배너 + 빈 상태 CTA + 피커 안내 | |
| 18 | **사용자별 페르소나** | Settings → ontong.local.md 편집 → 자유 마크다운 → 답변 스타일 변화 | |

### 트러블슈팅

**LLM 호출 실패 (401/403)**:
- `.env`에서 `LITELLM_MODEL` 확인 (현재 `anthropic/claude-sonnet-4-20250514`)
- API 키 확인: `curl https://api.anthropic.com/v1/messages -H "x-api-key: $ANTHROPIC_API_KEY" -H "anthropic-version: 2023-06-01" -d '{"model":"claude-sonnet-4-20250514","max_tokens":10,"messages":[{"role":"user","content":"hi"}]}' -H "Content-Type: application/json"`
- 크레딧 부족 시: https://console.anthropic.com/settings/billing

**ReAct 재검색이 트리거 안 됨**:
- 정상 동작임. 위키 236개 문서에서 대부분 40%+ 관련도 나옴
- 재검색은 관련도 25% 미만에서만 트리거 (비용 통제 설계)
- 직접 테스트: `_evaluate_search_results(distances=[0.80])` 호출

**세션 파일 안 생김**:
- `data/sessions/` 디렉토리 존재 확인
- 백엔드 로그에서 "Failed to persist" 확인
- session_id에 특수문자 있으면 sanitize됨

**스킬 소개 배너가 안 보임**:
- localStorage에 `ontong:skill-intro-dismissed`가 이미 설정됨
- 리셋: 개발자도구 Console → `localStorage.removeItem("ontong:skill-intro-dismissed")`

**훅이 등록 안 됨**:
- 백엔드 시작 로그에서 "Default hooks registered" 확인
- `hooks.py`의 `register_default_hooks()` 가 `main.py`에서 호출되는지 확인

---

## 세션 33 — Domain-Process 계층 구조 + 데이터 클린업

### 19. 메타데이터 템플릿 API

```bash
# 전체 템플릿 조회
curl -s http://localhost:8001/api/metadata/templates | python3 -m json.tool
# → domain_processes: {SCM: [...], ERP: [...], ...} 구조 확인

# 도메인 목록
curl -s http://localhost:8001/api/metadata/templates/domains | python3 -m json.tool

# 특정 도메인의 프로세스
curl -s http://localhost:8001/api/metadata/templates/processes/SCM | python3 -m json.tool
# → {"domain": "SCM", "processes": ["주문", "품질", "진행", "공정", "물류"]}

# 도메인 추가
curl -s -X POST http://localhost:8001/api/metadata/templates/domain \
  -H "Content-Type: application/json" \
  -d '{"name": "테스트도메인", "processes": ["프로세스A"]}' | python3 -m json.tool

# 도메인 삭제
curl -s -X DELETE http://localhost:8001/api/metadata/templates/domain/테스트도메인 | python3 -m json.tool

# 프로세스 추가 (도메인 하위)
curl -s -X POST http://localhost:8001/api/metadata/templates/domain/SCM/process \
  -H "Content-Type: application/json" \
  -d '{"name": "테스트프로세스"}' | python3 -m json.tool

# 프로세스 삭제
curl -s -X DELETE http://localhost:8001/api/metadata/templates/domain/SCM/process/테스트프로세스 | python3 -m json.tool
```

### 20. Domain-Process Cascade UI

1. 좌측 트리에서 아무 문서 클릭 (예: `SCM/주문-처리-절차.md`)
2. 에디터 상단 **Metadata** 접기/펼치기
3. **Domain 드롭다운**: SCM, ERP, MES, 인프라, 기획, 재무, 인사 확인
4. **SCM 선택** → Process 드롭다운에 **주문, 품질, 진행, 공정, 물류**만 표시
5. **Domain을 ERP로 변경** → Process가 자동 초기화 (빈값) → ERP 프로세스 표시
6. Domain 미선택 시 Process에 전체 목록 표시

### 21. 샘플 문서 확인

**도메인별 문서 수**: 7개 도메인, 총 21개 문서
- SCM: 5개 (주문, 발주, 물류, 공정v1 deprecated, 공정v2)
- ERP: 3개 (마스터데이터, 모듈관리, 인터페이스)
- MES: 3개 (생산계획, 실적관리, 설비보전)
- 인프라: 3개 (서버, 모니터링, 보안)
- 기획: 2개 (예산, 프로젝트)
- 재무: 2개 (결산, 세무)
- 인사: 3개 (온보딩, 교육, 평가)

**Lineage 테스트**: `SCM/공정-관리-기준-v1.md` (deprecated) → `SCM/공정-관리-기준-v2.md` (approved)

### 22. 채팅 필터 테스트 (reindex 후)

```bash
# 먼저 reindex 실행
curl -X POST http://localhost:8001/api/wiki/reindex

# 채팅 테스트 — 도메인 필터링 확인
curl -s -N -X POST http://localhost:8001/api/agent/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "SCM 주문 처리 절차를 알려줘", "session_id": "test-filter"}'
# → sources에 SCM 도메인 문서가 우선 표시

curl -s -N -X POST http://localhost:8001/api/agent/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "설비보전 점검표 보여줘", "session_id": "test-filter2"}'
# → MES/설비보전-점검표.md가 sources에 포함
```

### 23. AutoTagButton confidence 표시

1. 아무 문서 열기 → Metadata 펼치기
2. **Auto-Tag** 버튼 클릭
3. 확인:
   - 신뢰도 뱃지 (초록 70%+, 노랑 50~69%, 빨강 <50%)
   - domain/process 제안 뱃지 (현재 비어있을 때만 표시)
   - 개별 수락 체크 버튼
   - 신뢰도 50% 미만 태그는 흐림 처리

### 24. Related 문서 편집

1. 문서 열기 → Metadata 펼치기
2. "관련 문서" 섹션 확인
3. 입력란에 문서 경로 타이핑 → 자동완성 드롭다운
4. Enter로 추가, X로 삭제
5. supersedes/superseded_by는 읽기전용 표시 확인 (SCM/공정-관리-기준-v1.md 열어보기)

### 25. Bulk Auto-tag (미태깅 대시보드)

```bash
# 미태깅 문서 확인
curl -s http://localhost:8001/api/metadata/untagged | python3 -m json.tool

# Bulk 미리보기 (apply=false)
curl -s -X POST http://localhost:8001/api/metadata/suggest-bulk \
  -H "Content-Type: application/json" \
  -d '{"paths": ["SCM/주문-처리-절차.md"], "apply": false}' | python3 -m json.tool

# Bulk 적용 (apply=true)
curl -s -X POST http://localhost:8001/api/metadata/suggest-bulk \
  -H "Content-Type: application/json" \
  -d '{"paths": ["SCM/주문-처리-절차.md"], "apply": true}' | python3 -m json.tool
```

**UI 테스트**: TreeNav 좌측 하단 "미태깅" 뱃지 클릭 → 대시보드 열기 → "미리보기" → confidence 확인 → "전체 자동 태깅"

---

## 세션 35 — Smart Friction 레이턴시 최적화 (2026-04-07)

### 배경
`/tags/similar` 엔드포인트는 OpenAI 임베딩 왕복으로 매 호출당 **560ms**가 고정적으로 소요된다. 기존 TagInput은 사용자가 Enter를 누를 때 비로소 이 호출을 시작해, 태그 추가 시 눈에 띄게 답답했다.

### 개선 방식
디바운스된 자동완성 검색(`/tags/search`, 3ms)과 **동일한 타이밍**에 `onCheckSimilar`를 백그라운드로 선제 호출하여 결과를 `similarCacheRef` Map에 저장한다. 사용자가 드롭다운을 훑어보는 자연스러운 공백(보통 1~2초)을 네트워크 왕복 시간으로 활용하는 **병렬화** 전략이다. Enter 시점엔 캐시 히트 → 체감 0ms.

메모리 관리를 위해 Map 삽입 순서 특성을 이용한 경량 LRU(최대 50개)를 함께 구현했다. 히트 시 `delete` 후 재삽입으로 recency를 갱신하고, 초과 시 `keys().next()`로 oldest를 evict.

### 데모 절차
1. 아무 문서 열기 → MetadataTagBar 태그 입력란 포커스
2. `캐싱` 타이핑 → 드롭다운에 `캐시 N건` 표시 확인 (200ms)
3. **1초 정도 기다린 후** Enter → 유사 태그 프롬프트가 **즉시** 표시되는지 확인 (캐시 히트)
4. 대조군: 다른 새 태그(예: `레디스풀링`) 타이핑 후 **바로 Enter** → 최악의 경우 560ms 대기 (캐시 미스, 기존과 동일)

### 측정
- `curl -s -o /dev/null -w "%{time_total}s\n" "http://localhost:8001/api/metadata/tags/similar?tag=캐싱"` → ~0.56s
- `curl -s -o /dev/null -w "%{time_total}s\n" "http://localhost:8001/api/metadata/tags/search?q=캐&with_count=true"` → ~0.003s

### 스케일 특성
병목은 OpenAI 임베딩 API 고정 비용이며 ChromaDB HNSW 검색은 O(log N)이므로, 태그 수가 10만개가 되어도 쿼리 레이턴시는 거의 변하지 않는다. LRU 50개 제한으로 장시간 세션 메모리도 상수.

### 변경 파일
- `frontend/src/components/editors/metadata/TagInput.tsx`

---

## Trust System Phase 1 데모 — 문서 신뢰도 점수

### 사전 준비

```bash
# 서버 실행 확인
curl -s http://localhost:8001/health | python3 -m json.tool

# 단위 테스트 확인
venv/bin/python -m pytest tests/test_confidence.py -v
```

### 시나리오 1: Confidence API 테스트

```bash
# 단일 문서 신뢰도 조회 (아무 wiki 파일 경로)
curl -s "http://localhost:8001/api/wiki/confidence/개발운영/캐시-장애-대응-매뉴얼.md" | python3 -m json.tool

# 배치 조회
curl -s "http://localhost:8001/api/wiki/confidence-batch?paths=개발운영/캐시-장애-대응-매뉴얼.md,SCM운영/공정-관리-기준-v1.md" | python3 -m json.tool
```

**확인**:
- `score`: 0-100 숫자
- `tier`: "high" | "medium" | "low"
- `stale`: true/false
- `signals`: 5개 시그널 점수 (freshness, status, metadata_completeness, backlinks, owner_activity)

### 시나리오 2: 에디터 헤더 신뢰도 pill

1. 아무 문서 열기
2. 에디터 상단 MetadataTagBar 아래에 **신뢰도 pill** 확인
   - 초록: "신뢰도 XX" (high, 70+)
   - 노랑: "신뢰도 XX — 검증 필요" (medium, 40-69)
   - 회색: "신뢰도 XX — 최신 정보가 아닐 수 있습니다" (low, 0-39)

### 시나리오 3: AI 채팅 소스 신뢰도 dot

1. AI 채팅에서 질문 (예: "캐시 장애 대응 절차 알려줘")
2. 답변 아래 소스 태그 확인
3. 각 소스 뱃지 오른쪽에 **색상 dot** 표시:
   - 초록 (high), 노랑 (medium), 회색 (low)
4. dot 호버 시 툴팁: "신뢰도 XX" / "신뢰도 XX — 검증 권장" / "신뢰도 XX — 오래된 문서"

### 시나리오 4: RAG 랭킹 부스트 확인

```bash
# AI 질문 후 소스 순서 확인 — 높은 신뢰도 문서가 상위에 올라와야 함
# 같은 관련도의 문서라도 신뢰도 높은 것이 먼저 (mild boost)
```

### 트러블슈팅

| 증상 | 원인 | 해결 |
|------|------|------|
| 신뢰도 pill 미표시 | 서버 미실행 또는 API 503 | `curl localhost:8001/health` 확인 |
| 소스에 dot 미표시 | confidence_score=-1 반환 | `main.py`에서 confidence_svc 주입 확인 |
| 모든 문서 점수 동일 | 메타데이터 없음 | MetadataIndex 재빌드 (POST /api/wiki/reindex) |

### 변경 파일
- `backend/application/trust/confidence.py` — 스코어링 엔진
- `backend/application/trust/confidence_cache.py` — TTL 캐시
- `backend/application/trust/confidence_service.py` — 서비스 오케스트레이터
- `backend/api/wiki.py` — API 엔드포인트
- `backend/application/agent/rag_agent.py` — RAG 랭킹 통합
- `backend/core/schemas.py` — SourceRef 확장
- `backend/main.py` — 와이어링
- `frontend/src/components/AICopilot.tsx` — 소스 신뢰도 dot
- `frontend/src/components/editors/MarkdownEditor.tsx` — 에디터 신뢰도 pill
- `frontend/src/lib/api/sseClient.ts` — SSE 타입 확장

---

## Trust System Phase 2 데모 — 작성 시 관련 문서 넛지

### 사전 준비

```bash
# 서버 실행 확인
curl -s http://localhost:8001/health | python3 -m json.tool

# 테스트 확인
venv/bin/python -m pytest tests/test_related_search.py -v
```

### 시나리오 1: 관련 문서 API 테스트

```bash
# 특정 문서의 관련 문서 조회
curl -s "http://localhost:8001/api/search/related?path=개발운영/캐시-장애-대응-매뉴얼.md&limit=5" | python3 -m json.tool
```

**확인**:
- 배열 반환 (최대 5건)
- 각 항목: `path`, `title`, `snippet`, `similarity` (0.5~1.0), `confidence_score`, `confidence_tier`, `relationship`
- `relationship`: "similar_topic" | "same_domain" | "shared_tags"
- 시스템 경로(`_skills/`, `_personas/`) 미포함

### 시나리오 2: LinkedDocsPanel "참고할 만한 문서"

1. 아무 문서 열기 (충분한 내용이 있는 문서)
2. "연결된 문서" 패널 확인
3. **기존 섹션** (lineage, backlinks) 아래에 **"✨ 참고할 만한 문서"** 섹션 확인
   - 각 문서: 신뢰도 dot (초록/노랑/회색) + 문서명 + 유사도%
   - 문서명 클릭 → 해당 문서 탭으로 이동
4. 처음 로딩 시 spinner (Loader2) 표시

### 시나리오 3: 저장 시 자동 related 제안

1. **새 문서 생성** (related 필드 없는 문서)
2. 캐시 관련 내용 작성 후 저장
3. 5~10초 후 문서 다시 열기
4. **확인**: frontmatter에 `related:` 필드가 자동 추가됨 (similarity > 0.7인 상위 3건)
5. 이미 `related`가 있는 문서는 변경 없음

### 트러블슈팅

| 증상 | 원인 | 해결 |
|------|------|------|
| 관련 문서 0건 | ChromaDB 미인덱싱 | POST /api/wiki/reindex 실행 |
| LinkedDocsPanel 안 보임 | 연결 문서 0건 + 관련 문서 0건 | 인덱싱 완료 후 새로고침 |
| 자동 related 미추가 | 이미 related 있음 또는 similarity < 0.7 | frontmatter 확인, threshold 확인 |
| API 503 | ConfidenceService 미주입 | main.py 와이어링 확인 |

### 변경 파일
- `backend/api/search.py` — `/related` 엔드포인트
- `backend/core/schemas.py` — `RelatedDocResult` 모델
- `backend/application/wiki/wiki_service.py` — `_auto_suggest_related()`
- `backend/main.py` — chroma/confidence 와이어링
- `frontend/src/components/editors/LinkedDocsPanel.tsx` — AI 추천 섹션

---

## 스코어링 중앙화 + UX 개선 데모

### 스코어링 설정 확인 API

```bash
# 모든 스코어링 파라미터를 한국어로 확인
curl -s http://localhost:8001/api/wiki/scoring-config | python3 -m json.tool
```

기대: confidence(가중치/tier/stale), related_documents(유사도/자동제안/UI), rag_boost(공식), conflict_detection(임계값) 섹션이 한국어 설명과 함께 반환.

### 관련 문서 UX 개선 확인

1. **min_similarity 0.7 적용 확인**
```bash
curl -s "http://localhost:8001/api/search/related?path=인프라/캐시-장애-대응-매뉴얼.md&limit=10" | python3 -m json.tool
```
기대: similarity < 0.7인 문서는 결과에 포함되지 않음.

2. **LinkedDocsPanel 기본 2건 + "더 보기"** — 브라우저에서 관련 문서 3건 이상인 문서 열기 → 기본 2건만 표시, "더 보기 (+N)" 버튼 클릭 시 전체 표시.

### 트러블슈팅

| 증상 | 원인 | 해결 |
|------|------|------|
| scoring-config 404 | wiki.py에 엔드포인트 미추가 | `api/wiki.py` 확인 |
| related 결과 너무 적음 | min_similarity 0.7로 상향 | threshold 조정 가능 (scoring_config.py) |
| 더 보기 버튼 안 보임 | 관련 문서 2건 이하 | 정상 동작 (3건 이상일 때만 표시) |

### 변경 파일
- `backend/application/trust/scoring_config.py` — 중앙 설정 (모든 가중치/임계값)
- `backend/application/trust/confidence.py` — SCORING 참조로 리팩터
- `backend/api/search.py` — SCORING.related 참조
- `backend/api/wiki.py` — `/scoring-config` 엔드포인트
- `backend/application/agent/rag_agent.py` — SCORING.rag_boost 참조
- `backend/application/conflict/conflict_service.py` — SCORING.conflict 참조
- `backend/application/wiki/wiki_service.py` — SCORING.related 참조
- `frontend/src/components/editors/LinkedDocsPanel.tsx` — 기본 2건 + 더 보기

---

## 사용자 투명성 + 관리자 대시보드 데모

### 1. 신뢰도 pill 상세 팝오버
1. 아무 문서를 에디터에서 열기 (예: `인프라/캐시-장애-대응-매뉴얼.md`)
2. 상단 MetadataTagBar 아래의 **신뢰도 pill** (초록/노랑/회색 배경) 클릭
3. 기대: 5개 시그널 상세가 팝오버로 표시
   - 최신성 (30%) — 진행 바 + 점수
   - 문서 상태 (25%)
   - 메타데이터 (15%)
   - 역참조 (15%)
   - 작성자 활동 (15%)
4. 팝오버 바깥 클릭 → 닫힘

### 2. 관리자 페이지 — 신뢰도 설정
1. 사이드바 상단의 **톱니바퀴 아이콘** 클릭
2. "관리" 섹션에서 **"신뢰도 설정"** (초록 게이지 아이콘) 클릭
3. 기대: 4개 섹션이 카드 형태로 표시
   - 문서 신뢰도 점수 — 공식, 가중치 5개, 등급 기준, 오래된 문서 기준
   - 관련 문서 발견 — 복합 정렬 공식, 최소 유사도, 자동 제안, 기본 표시 개수
   - AI 검색 순위 보정 — 공식, 효과
   - 유사 문서 감지 — 유사도 임계값
4. 상단 파란 안내 배너에 "점수는 어떻게 활용되나요?" 설명 확인

### 3. AI 소스 뱃지 툴팁
1. AI 채팅에서 아무 질문 → 답변의 소스 문서에 마우스 호버
2. 기대: 여러 줄 툴팁 (관련도, 신뢰도+해석, 작성자, 수정일, 상태)

### 트러블슈팅
| 증상 | 원인 | 해결 |
|------|------|------|
| pill 팝오버 안 뜸 | 빌드 미반영 | HMR 새로고침 확인 |
| 설정 페이지 빈 화면 | API 503 | 백엔드 실행 확인 |
| 시그널 바가 다 0 | signals 필드 미반환 | confidence API 응답 확인 |

### 변경 파일
- `frontend/src/components/editors/MarkdownEditor.tsx` — 신뢰도 pill 팝오버
- `frontend/src/components/editors/ScoringDashboard.tsx` — 관리자 대시보드 (새 파일)
- `frontend/src/components/TreeNav.tsx` — "신뢰도 설정" 메뉴 항목
- `frontend/src/components/workspace/FileRouter.tsx` — scoring-dashboard 라우팅
- `frontend/src/types/workspace.ts` — VirtualTabType 확장
- `frontend/src/lib/workspace/useWorkspaceStore.ts` — 탭 타이틀
- `frontend/src/components/AICopilot.tsx` — 소스 뱃지 툴팁 강화

---

## Trust System Phase 3 데모 — 읽기 시 맥락

### 사전 준비
서버 실행 확인: `curl -s http://localhost:8001/health | python3 -m json.tool`

### 1. TrustBanner 기본 동작
1. 브라우저에서 아무 문서 열기 (예: `인프라/캐시-장애-대응-매뉴얼.md`)
2. 기대: MetadataTagBar 아래에 TrustBanner 표시
   - 신뢰도 pill (초록/노랑/회색) 클릭 → 시그널 상세 팝오버
   - 기존 MarkdownEditor의 pill이 아닌 TrustBanner 컴포넌트에서 렌더

### 2. 인용 카운트 확인
1. AI 채팅에서 질문 → 소스 문서가 인용됨
2. 해당 문서를 에디터에서 열기
3. 기대: TrustBanner에 "AI 답변에서 N회 인용" 표시

```bash
# API로 확인
curl -s "http://localhost:8001/api/wiki/confidence/인프라/캐시-장애-대응-매뉴얼.md" | python3 -m json.tool
# citation_count 필드 확인
```

### 3. 오래된 문서 경고 배너
- `stale_months >= 12`인 문서를 열면 노란 배너: "N개월 이상 수정되지 않았습니다"
- 최근 수정된 문서에는 배너 안 뜸

### 4. 최신 대안 패널
- 신뢰도 < 40인 문서를 열면 파란 패널: "이 주제의 최신 문서: [문서명] (신뢰도 XX)"
- 신뢰도 높은 문서에는 패널 안 뜸

### 트러블슈팅
| 증상 | 원인 | 해결 |
|------|------|------|
| TrustBanner 안 보임 | confidence API 503 | 백엔드 실행 확인 |
| 인용 카운트 항상 0 | AI 채팅 미사용 | 채팅으로 질문 후 확인 |
| 최신 대안 안 뜸 | 신뢰도 >= 40 | 정상 (낮은 신뢰도 문서에만 표시) |
| pill 팝오버 스타일 깨짐 | TrustBanner로 이전 중 누락 | TrustBanner.tsx 확인 |

### 변경 파일
- `backend/application/trust/citation_tracker.py` — 인용 카운트 (새 파일)
- `backend/application/trust/confidence.py` — NewerAlternative 모델, ConfidenceResult 확장
- `backend/application/trust/confidence_service.py` — citation_tracker/chroma 연동, newer_alternatives 조회
- `backend/application/agent/rag_agent.py` — 소스 emit 후 인용 기록
- `backend/main.py` — CitationTracker 와이어링
- `frontend/src/components/editors/TrustBanner.tsx` — 통합 신뢰 배너 (새 파일)
- `frontend/src/components/editors/MarkdownEditor.tsx` — 기존 pill 제거, TrustBanner 사용
- `tests/test_phase3_trust.py` — 14개 테스트

---

## Trust System Phase 4 데모 — 스마트 충돌 해결

### 사전 준비

```bash
# 서버 실행 확인
curl -s http://localhost:8001/health | python3 -m json.tool

# 전체 스캔 (충돌 쌍 생성)
curl -s -X POST "http://localhost:8001/api/conflict/full-scan?threshold=0.85"

# 10초 후 typed 충돌 확인
curl -s "http://localhost:8001/api/conflict/typed?filter=all" | python3 -m json.tool
```

### 1. 관련 문서 관리 대시보드 (리네이밍)
- 사이드바 설정(톱니바퀴) → "관련 문서 관리" 클릭
- 이전 "문서 충돌 감지" → 이제 "관련 문서 관리"
- 유사 문서 쌍 목록 표시 (미분석 상태)

### 2. AI 분석 (유형 분류)
- 쌍 카드에서 **"AI 분석"** 버튼 클릭
- LLM이 두 문서를 비교하여 유형 분류:
  - **사실 불일치** (빨간 뱃지) — 같은 질문, 다른 답
  - **범위 중복** (노란 뱃지) — 같은 영역, 다른 범위
  - **시간 차이** (파란 뱃지) — 구버전/신버전 관계
  - **무관** (회색 뱃지) — 오탐
- claim_a / claim_b에 구체적 인용 표시
- 추천 해결 방법 파란 박스로 표시

```bash
# 수동 분석 API
curl -s -X POST "http://localhost:8001/api/conflict/analyze-pair?file_a=문서A경로&file_b=문서B경로" | python3 -m json.tool
```

### 3. 원클릭 해결
- **무시**: 오탐으로 표시 → resolved
- **범위 명시**: 양쪽 문서의 `related` 필드에 상호 링크 추가
- **버전 체인**: 구 문서 deprecated + supersedes/superseded_by 설정
- **병합 제안**: resolved로 표시 (향후 LLM 병합 초안 예정)

```bash
# 해결 API
curl -s -X POST "http://localhost:8001/api/conflict/resolve" \
  -H "Content-Type: application/json" \
  -d '{"file_a":"docs/a.md","file_b":"docs/b.md","action":"dismiss","resolved_by":"admin"}' | python3 -m json.tool
```

### 4. 관리가 필요한 문서 다이제스트
- 사이드바 설정 → "관리가 필요한 문서" 클릭
- 세 섹션으로 그룹핑:
  - **오래된 문서** (12개월+ 미수정)
  - **신뢰도 낮은 문서** (점수 < 40)
  - **미해결 관련 문서** (충돌 미해결)
- 사용자 필터로 본인 문서만 확인 가능

```bash
# 다이제스트 API
curl -s "http://localhost:8001/api/wiki/digest" | python3 -m json.tool
curl -s "http://localhost:8001/api/wiki/digest?user_filter=admin" | python3 -m json.tool
```

### 5. 저장 시 자동 심층 분석
- 문서 저장 → 인덱싱 → 충돌 감지 → 유사도 > 0.9인 상위 3쌍 자동 LLM 분석
- 대시보드에서 분석 결과 자동 반영 (별도 조작 불필요)

### 트러블슈팅
| 증상 | 원인 | 해결 |
|------|------|------|
| typed API 빈 결과 | 전체 스캔 미실행 | POST /full-scan 먼저 실행 |
| AI 분석 실패 | LLM 연결 문제 | .env의 LLM 설정 확인 |
| 해결 버튼 에러 | 문서 경로 변경 | 새로고침 후 재시도 |
| 다이제스트 503 | digest_service 미초기화 | 백엔드 재시작 |
| 대시보드 "미분석" 표시 | 아직 LLM 분석 안 됨 | "AI 분석" 버튼 클릭 |

### 변경 파일
- `backend/core/schemas.py` — TypedConflict 모델
- `backend/application/agent/models.py` — ConflictAnalysis LLM 출력 모델
- `backend/application/agent/skills/conflict_check.py` — analyze_pair() static method
- `backend/application/agent/skills/prompts/conflict_analyze_pair.md` — 분석 프롬프트
- `backend/application/conflict/conflict_store.py` — StoredConflict 확장, update_analysis/resolve_pair
- `backend/application/conflict/conflict_service.py` — get_typed_pairs, resolve_pair, trigger_deep_analysis
- `backend/api/conflict.py` — POST /resolve, GET /typed, POST /analyze-pair
- `backend/application/trust/digest.py` — DocumentDigestService (새 파일)
- `backend/api/wiki.py` — GET /digest 엔드포인트
- `backend/application/wiki/wiki_service.py` — 저장 시 deep analysis 트리거
- `backend/main.py` — digest_svc 와이어링
- `frontend/src/types/wiki.ts` — TypedConflict, ConflictType 등 타입
- `frontend/src/components/editors/ConflictDashboard.tsx` — 전면 리라이트
- `frontend/src/components/editors/MaintenanceDigest.tsx` — 다이제스트 컴포넌트 (새 파일)
- `frontend/src/components/workspace/FileRouter.tsx` — maintenance-digest 라우트
- `frontend/src/types/workspace.ts` — maintenance-digest VirtualTabType
- `frontend/src/lib/workspace/useWorkspaceStore.ts` — 탭 타이틀 추가
- `frontend/src/components/TreeNav.tsx` — 사이드바 메뉴 추가 + 레이블 변경
- `tests/test_phase4_smart_conflict.py` — 13개 테스트

---

## Status Simplification + Lineage/Versioning Overhaul (2026-04-11)

> 67개 자동 테스트 통과, TS 빌드 클린. 아래는 서버 기동 후 **브라우저 UI 기반** 통합 검증 시나리오.

### 사전 준비

1. 서비스 기동 (터미널에서)
   - `docker compose up -d chroma redis`
   - `source venv/bin/activate && set -a && source .env && set +a && uvicorn backend.main:app --host 0.0.0.0 --port 8001`
   - 별도 터미널: `cd frontend && npm run dev`
2. 브라우저에서 `http://localhost:3000` 접속

---

### 시나리오 1: 상태 3종화 확인

**목적**: 상태 드롭다운에 draft / approved / deprecated 3개만 존재하는지 확인

1. 왼쪽 TreeNav에서 **아무 문서** 클릭하여 열기
2. 우측 상단 **ℹ️ 아이콘** (또는 `Cmd+I`) 클릭 → Document Info Drawer 열기
3. 메타데이터 탭에서 **상태(Status) 드롭다운** 클릭
4. **확인**:
   - `Draft`, `Approved`, `Deprecated` **3개만** 표시
   - `Review`, `-- 미설정 --` 옵션이 **없어야** 함

---

### 시나리오 2: 새 문서 기본 상태 = Draft

**목적**: 새로 만든 문서가 자동으로 draft 상태가 되는지 확인

1. TreeNav 상단의 **+ 새 문서** 버튼 클릭
2. 폴더: `test-lineage`, 파일명: `새문서.md` 입력 → 생성
3. 에디터에 아무 내용 입력 후 **저장** (`Cmd+S`)
4. **ℹ️ Drawer** 열기 → 메타데이터 탭
5. **확인**: 상태가 **Draft**로 표시됨 (직접 설정하지 않았는데 자동)

---

### 시나리오 3: Approved 자동 강등

**목적**: approved 문서의 **본문**을 수정하면 자동으로 draft로 강등되는지 확인

**준비 — Approved 문서 만들기**
1. `test-lineage/새문서.md`를 열고 Drawer에서 상태를 **Approved**로 변경 → 저장
2. Drawer 닫고 다시 열어서 상태가 **Approved**인지 확인

**테스트 — 본문 수정**
3. 에디터에서 **본문 내용을 수정** (예: 문장 추가) → 저장
4. Drawer 열기
5. **확인**: 상태가 **Draft**로 자동 강등됨

**테스트 — 메타데이터만 수정 (강등 안 됨)**
6. Drawer에서 상태를 다시 **Approved**로 변경 → 저장
7. Drawer에서 **태그만 추가** (본문 수정 없이) → 저장
8. **확인**: 상태가 여전히 **Approved** (메타데이터만 변경이라 강등 안 됨)

---

### 시나리오 4: "새 버전 만들기" (우클릭 메뉴)

**목적**: 우클릭으로 쉽게 새 버전 문서를 생성하고, lineage가 자동 연결되는지 확인

1. 새 문서 생성: `test-lineage/배포가이드-v1.md`, 내용 작성
2. Drawer에서 domain: `IT`, 태그: `배포` 추가 → 저장
3. TreeNav에서 `배포가이드-v1.md`를 **우클릭** → **"새 버전 만들기"** 클릭
4. 다이얼로그에 파일명이 **`배포가이드-v2.md`로 자동 제안**됨을 확인
5. **생성** 버튼 클릭
6. **확인**:
   - `배포가이드-v2.md`가 자동으로 열림
   - Drawer 열기 → `이전 버전(supersedes)` 필드에 `배포가이드-v1.md` 자동 설정됨
   - domain: `IT`, 태그: `배포`가 **자동 상속**됨
7. `배포가이드-v1.md` 열기 → Drawer 확인
   - `새 버전(superseded_by)` 필드에 `배포가이드-v2.md`가 **자동 설정**됨 (양방향 링크)

---

### 시나리오 5: "새 버전 작성" (Drawer 버튼)

**목적**: Drawer 내 버튼으로도 새 버전을 생성할 수 있는지 확인

1. `배포가이드-v2.md` 열기 → Drawer 열기
2. **"새 버전 작성"** 버튼 클릭
3. 파일명 입력란에 **`배포가이드-v3.md`** 자동 제안됨 확인
4. **생성** 클릭
5. **확인**:
   - v3 문서 열림, supersedes에 v2 자동 설정
   - v2 문서의 superseded_by에 v3 자동 설정 (양방향)
   - v2의 "새 버전 작성" 버튼이 이제 **사라짐** (이미 superseded_by가 있으므로)

---

### 시나리오 6: 버전 체인 타임라인 UI

**목적**: 3-node 체인 (v1→v2→v3)이 타임라인에 정상 표시되는지 확인

1. `배포가이드-v1.md` 열기 → Drawer에서 상태를 **Deprecated**로 변경 → 저장
2. `배포가이드-v2.md` 열기 → Drawer에서 상태를 **Deprecated**로 변경 → 저장
3. `배포가이드-v3.md` 열기 → Drawer에서 상태를 **Approved**로 변경 → 저장
4. `배포가이드-v2.md` 클릭하여 열기
5. **확인**: 상단에 **amber 배너** "이 문서는 폐기되었습니다" + 새 버전 링크
6. **"전체 버전 히스토리"** 버튼 클릭
7. **확인**: 수직 타임라인에:
   - v1 (deprecated)
   - v2 (deprecated, **현재 문서 하이라이트**)
   - v3 (approved, 초록)
8. v3 노드 클릭 → 해당 문서로 이동

---

### 시나리오 7: Lineage 검증 — 자기참조/사이클 차단

**목적**: 잘못된 lineage 설정이 차단되는지 확인

**자기참조**
1. 새 문서 생성: `test-lineage/자기참조.md`
2. Drawer 열기 → `이전 버전(supersedes)` 필드에 **`test-lineage/자기참조.md`** (자기 자신) 입력 → 저장
3. **확인**: 에러 메시지 — 저장 실패

**사이클**
4. 새 문서 생성: `test-lineage/사이클-A.md`
   - Drawer에서 `이전 버전(supersedes)` = `test-lineage/사이클-B.md` → 저장
5. 새 문서 생성: `test-lineage/사이클-B.md`
   - Drawer에서 `이전 버전(supersedes)` = `test-lineage/사이클-A.md` → 저장
6. **확인**: B 저장 시 에러 — 사이클 감지

---

### 시나리오 8: TreeNav deprecated 스타일

**목적**: TreeNav에서 deprecated 파일이 시각적으로 구분되는지 확인

1. 왼쪽 TreeNav에서 `test-lineage/` 폴더 펼치기
2. **확인**:
   - `배포가이드-v1.md`, `배포가이드-v2.md` → **취소선(line-through) + 반투명(50% opacity)**
   - `배포가이드-v3.md` → 정상 표시 (취소선 없음, 불투명)
3. deprecated 문서를 클릭해도 정상적으로 열리는지 확인

---

### 시나리오 9: Deprecated 배너 + 후속 문서 링크

**목적**: deprecated 문서를 열었을 때 경고 배너와 후속 문서 링크가 표시되는지 확인

1. `배포가이드-v1.md` 클릭하여 열기
2. **확인**: 상단에 **amber/red 배너** 표시
   - "이 문서는 폐기되었습니다"
   - 새 버전 링크: `배포가이드-v2.md` (클릭 가능)
3. 링크 클릭 → `배포가이드-v2.md`로 이동
4. v2에서도 배너 확인 → v3 링크 클릭 → v3(approved)로 이동
5. **확인**: v3(approved)에는 deprecated 배너가 **없음**

---

### 시나리오 10: 상태 드롭다운으로 직접 Deprecate

**목적**: UI에서 상태를 deprecated로 변경하고 부수 효과 확인

1. `test-lineage/새문서.md` 열기
2. Drawer에서 상태를 **Deprecated**로 변경 → 저장
3. **확인**: TreeNav에서 해당 파일이 **취소선 + 반투명**으로 변경됨
4. **확인**: 문서 상단에 deprecated 배너 표시 (superseded_by 없으면 "대체 문서 없음" 안내)

---

### 시나리오 11: AI 코파일럿 검색 — deprecated 제외

**목적**: AI 검색에서 deprecated 문서가 제외되고, 활성 문서 기반으로 답변하는지 확인

1. 우측 **AI 코파일럿** 패널 열기 (`Cmd+J`)
2. "공정 관리 기준에 대해 알려줘"로 질문
3. **확인**:
   - 소스에 `SCM/공정-관리-기준-v2.md` (활성)가 표시
   - `SCM/공정-관리-기준-v1.md` (deprecated)는 소스에 **없음**
   - 탐색 과정 펼치면 amber ⓘ 아이콘으로 "폐기된 문서 N건이 검색 결과에서 제외됨" 메시지 표시
4. 답변 내용이 v2 기준 (불량률 목표 1.5%, AI 기반 실시간 감지 등)인지 확인

---

### 시나리오 12: 문서 삭제 시 참조 보호

**목적**: 다른 문서가 참조 중인 파일은 삭제가 차단되는지 확인

1. TreeNav에서 `배포가이드-v2.md`를 **우클릭 → 삭제**
2. **확인**: 삭제 차단 또는 경고 — "이 문서를 참조하는 문서가 있습니다: 배포가이드-v3.md"
3. 참조가 없는 문서 (예: `자기참조.md`)를 삭제 → **정상 삭제됨**

---

### 시나리오 13: 종합 워크플로우

**목적**: 실제 업무 시나리오 재현 — 문서 작성 → 승인 → 새 버전 만들기 → 구버전 자동 폐기

1. 새 문서 `test-lineage/보안정책-v1.md` 생성, 내용 작성 후 저장
   - **확인**: 기본 상태 **Draft**
2. Drawer에서 domain: `보안`, 태그: `정책` 추가 → 상태를 **Approved**로 변경 → 저장
3. 정책이 바뀌었다고 가정:
   - TreeNav에서 `보안정책-v1.md` **우클릭 → 새 버전 만들기**
   - 파일명 `보안정책-v2.md` 확인 → **생성**
4. **확인**:
   - v2가 자동으로 열림, supersedes에 v1 자동 설정
   - v1을 열어보면 superseded_by에 v2 **자동 설정**됨 (양방향)
   - v2에 domain: `보안`, 태그: `정책` **자동 상속**됨
5. v1을 열고 상태를 **Deprecated**로 변경 → 저장
6. **확인**:
   - TreeNav: v1은 취소선, v2는 정상
   - v1 열기: deprecated 배너 + v2 링크
   - v2 열기: "전체 버전 히스토리" 버튼 → 타임라인에 v1→v2 표시
   - AI 코파일럿에서 "보안정책" 검색 → v2가 상위 결과

### 시나리오 14: 새 버전 생성 검증 (엣지 케이스)

**목적**: 새 버전 만들기의 방어 로직 확인

1. **Deprecated 문서에서 차단**: v1을 deprecated 상태로 만든 후, TreeNav에서 **우클릭**
   - **확인**: 컨텍스트 메뉴에 "새 버전 만들기" 항목이 **표시되지 않음**
2. **이미 새 버전이 있는 문서에서 차단**: v1에 superseded_by가 설정된 상태에서 (API로) 새 버전 시도
   - **확인**: "이미 새 버전이 존재합니다: 보안정책-v2.md" 에러
3. **자동 폐기 + 상태 복원**: approved 상태인 v2에서 새 버전 v3 생성
   - **확인**: v2가 자동 deprecated, 토스트에 "이전 버전이 자동으로 폐기 처리되었습니다" 표시
   - v3를 삭제 → v2가 **approved로 복원** (draft가 아님)
4. **삭제 다이얼로그**: TreeNav에서 문서 우클릭 → 삭제
   - **확인**: 브라우저 기본 confirm 대신 스타일된 Dialog 표시, Enter로 실행 가능

### 시나리오 15: 폐기 되돌리기

**목적**: deprecated된 문서를 원래 상태로 복원

**사전 조건**: 시나리오 13에서 v1이 deprecated 상태

1. 좌측 사이드바에서 **관련 문서 관리** (AlertTriangle 아이콘) 탭 열기
2. 상단 필터에서 **해결됨** 탭 클릭
3. v1 ↔ v2 쌍 찾기 — `version_chain` 또는 `auto_deprecated`로 해결된 항목
4. **"폐기 되돌리기"** 버튼 클릭 (amber 색상 Undo 아이콘)
5. **확인**:
   - 토스트: "폐기 되돌리기 완료 — 보안정책-v1.md → approved"
   - v1 열기: status가 **approved** (원래 상태로 복원, draft가 아님)
   - v1의 superseded_by가 **비어있음**
   - v2의 supersedes가 **비어있음** (양방향 정리)
   - TreeNav: v1의 취소선 **제거됨**
   - **VersionTimeline**: v2에서 "전체 버전 히스토리" 열면 v1이 **더 이상 표시되지 않음** (체인 분리 확인)
   - v1에서 "전체 버전 히스토리" 열면 **v1만 단독** 또는 이전 체인만 표시

### 시나리오 16: 삭제 시 참조 보호 + Lineage 자동 정리

**목적**: 삭제 시 관련 문서 참조 보호 및 lineage 자동 정리 확인

1. v1의 related에 v2를 수동 추가 → 저장
2. v2를 TreeNav에서 삭제 시도
   - **확인**: "삭제할 수 없습니다 — 참조 문서: 보안정책-v1.md" 토스트 (파일명만 표시)
3. v1에서 related 제거 후 저장
4. 다시 v2 삭제 시도 → 성공
   - **확인**: v1의 superseded_by가 자동 정리됨

---

### 정리

테스트 완료 후 `test-lineage/` 폴더를 TreeNav에서 삭제하여 정리.

---

### Troubleshooting

| 증상 | 원인 | 해결 |
|------|------|------|
| 상태 드롭다운에 review 남아있음 | 프론트엔드 빌드 캐시 | `rm -rf frontend/.next && npm run dev` |
| TreeNav 취소선 안 보임 | statuses API 빈 응답 | 터미널에서 `curl -s localhost:8001/api/wiki/reindex -X POST` → metadata index 재빌드 |
| version-chain에 1개만 | 양방향 자동 링크 실패 | "새 버전 만들기"로 생성하면 자동 연결. 수동 입력 시 저장 후 상대 문서도 확인 |
| approved 강등 안 됨 | 본문을 수정하지 않음 | 메타데이터가 아닌 **본문 텍스트**를 실제로 변경해야 강등 발생 |
| 자기참조 에러가 안 나옴 | lineage_validator 미로드 | 백엔드 서버 재시작 |
| VersionTimeline 로딩만 표시 | API 프록시 문제 | `next.config.ts` rewrites에 `/api/wiki/version-chain` 포함 확인 |
| 폐기 되돌리기 후 타임라인 안 바뀜 | MetadataIndex 미갱신 | 백엔드 서버 재시작 (P2-FIX2로 수정 완료) |
| deprecated 배너 안 보임 | LineageWidget 미렌더링 | 문서에 superseded_by 필드가 실제로 저장되었는지 Drawer에서 확인 |

### 변경 파일 요약

**Backend (8 파일 수정, 1 파일 생성)**
- `backend/core/schemas.py` — status default "draft"
- `backend/infrastructure/storage/local_fs.py` — _normalize_status() 읽기 시 정규화
- `backend/application/trust/scoring_config.py` — review/unset 제거
- `backend/application/trust/confidence.py` — STATUS_SCORES 업데이트
- `backend/application/metadata/metadata_index.py` — 역참조 인덱스 + 조회 API 5개
- `backend/application/wiki/wiki_service.py` — 자동 강등, lineage 검증, 폐기 훅, 참조 업데이트
- `backend/api/wiki.py` — version-chain, predecessor-context, bulk-status, delete force
- `backend/api/metadata.py` — GET /statuses
- `backend/application/wiki/lineage_validator.py` — **신규** 계보 검증기

**Frontend (5 파일 수정, 1 파일 생성)**
- `frontend/src/types/wiki.ts` — DocumentStatus 타입
- `frontend/src/lib/markdown/frontmatterSync.ts` — emptyMetadata default
- `frontend/src/components/editors/DocumentInfoDrawer.tsx` — 드롭다운
- `frontend/src/components/editors/metadata/MetadataTagBar.tsx` — 드롭다운/뱃지
- `frontend/src/components/editors/DocumentInfoBar.tsx` — statusColors
- `frontend/src/components/editors/DocumentGraph.tsx` — STATUS_COLORS
- `frontend/src/components/editors/LineageWidget.tsx` — 강화 배너 + 타임라인 연동
- `frontend/src/components/TreeNav.tsx` — deprecated 스타일 + statuses fetch
- `frontend/src/components/editors/VersionTimeline.tsx` — **신규** 타임라인 UI

**Tests (5 파일 생성, 67 tests)**
- `tests/test_p2b2_status_field.py` (18), `tests/test_metadata_index_enriched.py` (17)
- `tests/test_lineage_validation.py` (14), `tests/test_deprecation_side_effects.py` (6)
- `tests/test_version_chain.py` (5), `tests/test_reference_integrity.py` (7)
