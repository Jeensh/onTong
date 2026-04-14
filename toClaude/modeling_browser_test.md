# Section 2 Modeling — 브라우저 데모 테스트 시나리오

> API 검증은 완료됨 (2026-04-14). 이 문서는 브라우저 UI 검증용.
> 백엔드: `http://localhost:8001` | 프론트엔드: `http://localhost:3000`

---

## 사전 준비

```bash
docker compose up -d neo4j chroma redis
set -a && source .env && set +a
.venv/bin/python -m uvicorn backend.main:app --host 0.0.0.0 --port 8001
cd frontend && npm run dev
```

---

## 시나리오 1: Modeling 섹션 진입

1. `http://localhost:3000` 접속
2. 상단 SectionNav에서 **Modeling** 클릭
3. **확인**:
   - [ ] Modeling 섹션으로 전환됨 (Wiki가 아닌 Modeling UI 표시)
   - [ ] 왼쪽에 5개 서브메뉴: 코드 분석, 도메인 온톨로지, 매핑 관리, 영향분석, 검토 요청
   - [ ] 상단에 "Repository" 입력란 표시
   - [ ] Repository 미입력 시 "Repository ID를 입력하세요" 안내 표시

---

## 시나리오 2: Repository 입력 + 코드 분석

1. 왼쪽 상단 Repository 입력란에 `test-java` 입력
2. 왼쪽 메뉴에서 **코드 분석** 클릭
3. **확인 (이미 파싱된 데이터 있는 경우)**:
   - [ ] package / class / method / field 별로 그룹핑된 엔티티 목록 표시
   - [ ] 각 그룹에 아이콘 + 개수 표시 (예: package (N), class (N))
   - [ ] Total 카운트 배지 표시
   - [ ] 각 엔티티에 name + parent + file_path 표시

4. **새 repo 파싱 테스트** (선택):
   - Repository URL에 `https://github.com/mkyong/java-json.git` 입력
   - "Parse Repository" 버튼 클릭
   - [ ] 로딩 스피너 표시
   - [ ] 파싱 완료 후 초록색 배너: "Parsing complete — Files: 95 | Entities: 442 | Relations: 1350"
   - [ ] 아래에 파싱된 엔티티 목록 자동 갱신

---

## 시나리오 3: 도메인 온톨로지

1. 왼쪽 메뉴에서 **도메인 온톨로지** 클릭
2. **확인 (이미 SCOR 로드된 경우)**:
   - [ ] SCOR+ISA-95 노드 트리 표시 (Plan, Source, Make, Deliver, Return 등)
   - [ ] 각 노드에 kind (process/entity/role) 뱃지 표시
   - [ ] 계층 구조가 들여쓰기로 표현됨

3. **SCOR 템플릿 미로드 시**:
   - "Load SCOR Template" 버튼 클릭
   - [ ] "Loaded 38 nodes" 성공 메시지
   - [ ] 트리 자동 갱신

4. **커스텀 노드 추가**:
   - 하단 "Add Node" 폼에서:
     - Name: `테스트 프로세스`
     - Kind: `Process` 선택
     - Parent ID: `SCOR/Make` 입력
   - "Add" 클릭
   - [ ] 트리에 새 노드 추가됨
   - [ ] SCOR/Make 하위에 "테스트 프로세스" 표시

---

## 시나리오 4: 매핑 관리 (핵심 뷰)

1. 왼쪽 메뉴에서 **매핑 관리** 클릭
2. **확인**:
   - [ ] 3컬럼 레이아웃: Code Entities | Mappings | Domain Nodes
   - [ ] Code Entities 컬럼: 파싱된 코드 엔티티 목록 (name + kind)
   - [ ] Domain Nodes 컬럼: SCOR 온톨로지 노드 목록 (name + kind)
   - [ ] Mappings 컬럼: 기존 매핑 목록 (code ↔ domain + status 뱃지)

3. **기존 매핑 확인** (API 검증에서 추가한 것):
   - [ ] `com.mkyong.json.App` ↔ `SCOR/Plan/DemandPlanning` — 초록 `confirmed` 뱃지
   - [ ] `com.mkyong.json.gson` ↔ `SCOR/Source/SupplierSelection` — 회색 `draft` 뱃지

4. **unmapped 경고 뱃지**:
   - [ ] 우측 상단에 "N unmapped" 주황 뱃지 표시 (매핑 안 된 엔티티 수)

5. **새 매핑 추가**:
   - "Add Mapping" 버튼 클릭 → 폼 표시
   - Code Entity 드롭다운에서 아무 클래스 선택 (예: `GsonConvertJsonToObject (class)`)
   - Domain Node 드롭다운에서 `Inventory Planning (process)` 선택
   - Owner: `demo-tester` 입력
   - "Add" 클릭
   - [ ] Mappings 컬럼에 새 항목 추가됨 (status: draft)
   - [ ] unmapped 카운트 1 감소

---

## 시나리오 5: 영향 분석

1. 왼쪽 메뉴에서 **영향분석** 클릭
2. **매핑된 용어 검색**:
   - Search Term에 `App` 입력 → "Analyze" 클릭 (또는 Enter)
   - [ ] Source 카드에 Term: `App`, Code Entity: `com.mkyong.json.App`, Domain: `SCOR/Plan/DemandPlanning` 표시
   - [ ] 하단에 결과 메시지 표시

3. **도메인 용어 검색**:
   - `DemandPlanning` 입력 → Analyze
   - [ ] 동일하게 `com.mkyong.json.App` 으로 resolve 됨

4. **미매핑 용어 검색**:
   - `존재하지않는클래스` 입력 → Analyze
   - [ ] 주황색 "Not Found" 경고 박스 표시
   - [ ] "매핑되지 않은 용어입니다" 메시지

5. **빈 입력 테스트**:
   - 검색어 비우고 Analyze 클릭
   - [ ] 버튼이 disabled 상태여서 아무 일도 안 일어남

---

## 시나리오 6: 검토 요청 (승인 워크플로우)

1. 왼쪽 메뉴에서 **검토 요청** 클릭
2. **확인**:
   - [ ] Approval Queue 제목 표시
   - [ ] 이전에 API로 승인한 건은 이미 처리됨 → "No pending reviews" 또는 빈 목록

3. **새 리뷰 제출 (curl로 생성)**:
   터미널에서 실행:
   ```bash
   curl -s -X POST http://localhost:8001/api/modeling/approval/submit \
     -H "Content-Type: application/json" \
     -d '{"mapping_code":"com.mkyong.json.gson","mapping_domain":"SCOR/Source/SupplierSelection","repo_id":"test-java","requested_by":"demo-user"}'
   ```

4. 브라우저에서 "Refresh" 버튼 클릭
   - [ ] Pending 리뷰 1건 표시
   - [ ] mapping_code → mapping_domain 화살표 표시
   - [ ] `pending` 주황 뱃지
   - [ ] "Requested by: demo-user" 표시
   - [ ] "Approve" 초록 버튼 + "Reject" 빨간 버튼 표시

5. **승인 테스트**:
   - "Approve" 클릭
   - [ ] 리뷰가 목록에서 사라짐 (pending → approved)
   - 매핑 관리 탭으로 이동 →
   - [ ] 해당 매핑의 status가 `confirmed`로 변경됨

6. **반려 테스트** (선택 — 새 리뷰 제출 후):
   - "Reject" 클릭 → 코멘트 입력란 표시
   - `도메인 매핑이 정확하지 않음` 입력 → "Confirm" 클릭
   - [ ] 리뷰가 목록에서 사라짐

---

## 시나리오 7: 탭 간 전환 + 데이터 일관성

1. 매핑 관리 → 영향분석 → 코드 분석 → 도메인 온톨로지 → 검토 요청 순서로 전환
   - [ ] 각 탭 전환 시 에러 없이 데이터 로딩
   - [ ] 콘솔에 JavaScript 에러 없음 (DevTools > Console 확인)

2. Repository ID 변경 (`test-java` → `nonexistent-repo`)
   - [ ] 각 탭에서 빈 상태 / 에러 메시지 정상 표시 (크래시 없음)

3. 다시 `test-java`로 변경
   - [ ] 기존 데이터 정상 복원

---

## 시나리오 8: Wiki 섹션과 격리 확인

1. SectionNav에서 **Wiki** 클릭
   - [ ] 기존 Wiki UI 정상 표시 (TreeNav, 에디터, AICopilot)
   - [ ] Modeling 관련 UI 요소 없음

2. SectionNav에서 다시 **Modeling** 클릭
   - [ ] Modeling UI 복원, 이전 상태(Repository ID 등) 유지

---

## 트러블슈팅

| 증상 | 원인 | 해결 |
|------|------|------|
| Modeling 클릭해도 안 바뀜 | `setActiveSection` 미동작 | 브라우저 하드 리프레시 (Cmd+Shift+R) |
| "Repository ID를 입력하세요"만 표시 | repo ID 미입력 | 왼쪽 상단 Repository 입력란에 `test-java` 입력 |
| Code Entities 비어있음 | 아직 파싱 안 함 | 코드 분석 탭 → URL 입력 → Parse |
| Domain Nodes 비어있음 | SCOR 미로드 | 도메인 온톨로지 탭 → Load SCOR Template |
| 매핑 추가 시 에러 | 코드/도메인 미선택 | 드롭다운에서 반드시 선택 후 Add |
| 영향분석 결과 0건 | 의존관계가 없는 코드 | 다른 클래스 검색 or 매핑 추가 후 재시도 |
| API 에러 (Network Error) | 백엔드 미시작 or CORS | `curl localhost:8001/health`로 백엔드 확인 |
| Neo4j 연결 실패 | 컨테이너 미시작 | `docker compose up -d neo4j` |
