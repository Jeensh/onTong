# Section 2 Modeling — 데모 가이드

> Engine Phase 1a + Source Viewer & Mapping Workbench Phase 2a

---

## 사전 준비

```bash
# Neo4j + ChromaDB + Redis
docker compose up -d neo4j chroma redis

# 백엔드 (반드시 새 코드로 재시작)
source venv/bin/activate && set -a && source .env && set +a
uvicorn backend.main:app --host 0.0.0.0 --port 8001

# 프론트엔드
cd frontend && npm run dev
```

### 헬스체크
```bash
# Engine API
curl -s http://localhost:8001/api/modeling/engine/status
# → {"repo_id":"","mapping_count":0,...,"ready":false}  (데모 로드 전)

# Source API
curl -s http://localhost:8001/api/modeling/source/tree/scm-demo
# → 데모 로드 전에는 빈 children, 로드 후 파일 트리 반환

# health에 simulation, engine_query 포함 확인
curl -s http://localhost:8001/api/modeling/health
```

---

## Part A: 분석 콘솔 + 시뮬레이션 (Engine Phase 1a)

### A-1: SCM 데모 로드

1. 브라우저에서 `http://localhost:3000` 접속
2. 상단 **Modeling** 탭 클릭
3. **확인**: 사이드바 구조
   - MAIN: 분석 콘솔 (기본 선택) / 시뮬레이션 / 매핑 워크벤치
   - 설정: 코드 분석 / 도메인 온톨로지 / 매핑 관리 / 검토 요청
4. 메인 영역에 **"SCM 데모 프로젝트 로드"** 버튼 클릭
5. **확인**:
   - Repository가 `scm-demo`로 설정됨
   - 분석 콘솔 화면으로 자동 전환
   - 예시 질의 4개 표시 (안전재고, 주문 서비스, 생산 계획, InventoryManager)
   - 사이드바에 코드분석/온톨로지/매핑 옆 녹색 체크 아이콘

```bash
curl -s http://localhost:8001/api/modeling/engine/status
# → {"repo_id":"scm-demo","simulatable_entities":9,"ready":true}
```

---

### A-2: 한국어 영향 분석 (핵심 데모)

1. 분석 콘솔의 검색창에 **"안전재고 계산 로직 변경"** 입력 → "분석" 클릭
2. **확인**:
   - 검색 대상: `SafetyStockCalculator`
   - 도메인 매핑: → `SCOR/Plan/InventoryPlanning`
   - 영향받는 프로세스 목록 (distance 표시)
   - "시뮬레이션 실행" 버튼 표시
3. 다른 예시도 테스트:
   - "주문 서비스 수정" → `OrderService`
   - "생산 계획 변경" → `ProductionPlanner`
   - "InventoryManager" → 영문 직접 매칭

```bash
curl -s -X POST http://localhost:8001/api/modeling/engine/query \
  -H "Content-Type: application/json" \
  -d '{"query":"안전재고 계산 로직 변경","repo_id":"scm-demo"}'
```

---

### A-3: 시뮬레이션 (분석 → 시뮬레이션 연결)

1. A-2에서 **"시뮬레이션 실행"** 버튼 클릭
2. **확인**:
   - "시뮬레이션" 탭이 자동 활성화
   - 드롭다운에 `SafetyStockCalculator — 안전재고 계산` 자동 선택
   - 3개 파라미터 슬라이더: `safety_factor` 1.65, `lead_time_days` 14, `service_level` 0.95
3. `safety_factor` 슬라이더를 **2.5**로 변경
4. **확인**: "실행" 버튼 활성화, 기존값 취소선 표시
5. **"실행"** 클릭
6. **확인**:
   - 안전재고 수준: 123 → 187개 (+51.5%) ↑
   - 재주문점: 823 → 887개 (+7.7%) ↑

```bash
curl -s -X POST http://localhost:8001/api/modeling/engine/simulate \
  -H "Content-Type: application/json" \
  -d '{"entity_id":"com.ontong.scm.inventory.SafetyStockCalculator","repo_id":"scm-demo","params":{"safety_factor":"2.5"}}'
```

---

### A-4: 다른 엔티티 시뮬레이션

1. 시뮬레이션 탭 드롭다운 → **OrderService — 주문 서비스** 선택
2. **확인**: `order_batch_size` (기본 10), `auto_approve_threshold` (기본 50000)
3. `order_batch_size`를 20으로 변경 → "실행"
4. **확인**: before/after 결과 표시

---

### A-5: Term Resolution 매핑표 (9개 엔티티)

| 한국어 입력 | 기대 결과 |
|------------|-----------|
| 안전재고 계산 로직 변경 | SafetyStockCalculator |
| 재고 관리 | InventoryManager |
| 주문 서비스 수정 | OrderService |
| 생산 계획 변경 | ProductionPlanner |
| 작업 지시 | WorkOrderProcessor |
| 구매 주문 | PurchaseOrderService |
| 공급업체 평가 | SupplierEvaluator |
| 배송 추적 | ShipmentTracker |
| 창고 관리 | WarehouseController |

---

## Part B: 매핑 워크벤치 (Phase 2a)

### B-1: 워크벤치 진입 및 레이아웃 확인

1. SCM 데모가 로드된 상태에서 (Part A-1 완료 후)
2. 좌측 사이드바에서 **매핑 워크벤치** 클릭
3. **확인**:
   - 화면이 55:45 비율로 좌/우 분할
   - 좌측: React Flow 도메인 그래프 + 하단 코드 엔티티 패널
   - 우측: "소스 코드" 헤더 + 파일 트리 + 에디터 영역
   - 도메인 그래프가 화면에 맞게 자동 피팅 (fitView)
   - 분할선(리사이저)을 마우스로 드래그해서 비율 조절 가능

---

### B-2: 도메인 그래프 확인

워크벤치 화면에서:

1. 도메인 그래프에 SCOR 노드들이 트리 구조로 표시되는지 확인
   - SCOR (루트) → Plan, Source, Make, Deliver (1단계)
   - 각 하위 노드 (DemandPlanning, InventoryPlanning 등)
2. **확인**:
   - 매핑된 노드: **초록색 테두리** + "N개 코드 연결" 텍스트
   - 매핑 안 된 노드: **회색 테두리**
   - 초록 노드 7개: InventoryPlanning, DemandPlanning, Manufacturing, Purchasing, SupplierSelection, Transportation, Warehousing
   - Zoom In/Out, Fit View 컨트롤 (우측 상단)
   - 미니맵 (우측 하단)
   - "도메인 노드에 코드 엔티티를 드래그하여 매핑" 안내 (좌측 상단)

---

### B-3: 코드 엔티티 패널

1. 좌측 하단 **코드 엔티티** 패널 확인
   - class/interface만 표시 (method, field 제외)
   - 각 엔티티 옆에 상태 원형: 초록(매핑됨) / 빨강(미매핑)
   - 매핑된 엔티티 우측에 도메인 이름 표시
2. **확인**:
   - InventoryManager: 초록 원 + "InventoryPlanning"
   - Product, Supplier, Warehouse (model 패키지): 빨강 원 (미매핑)
3. 검색창에 `Order` 입력 → OrderService, OrderStatus만 필터링
4. 검색 초기화 후 `Warehouse` 입력 → WarehouseController만 표시

---

### B-4: 파일 트리 탐색 및 소스 보기

1. 우측 파일 트리에서 `src > main > java > com > ontong > scm` 확장
2. `inventory` 폴더 확장 → **InventoryManager.java** 클릭
3. **확인**:
   - Monaco 에디터에 Java 소스 코드가 syntax highlight되어 표시
   - 파일 경로 바에 `src/main/java/com/ontong/scm/inventory/InventoryManager.java`
   - "10개 엔티티" 텍스트 (파일 경로 바 우측)
   - 에디터가 read-only (편집 불가)
   - 매핑된 엔티티 라인에 좌측 세로선 마커 (초록/노랑)
4. 다른 파일 선택: `order > OrderService.java` 클릭 → 파일 전환 확인
5. 파일 검색창에 `Safety` 입력 → `SafetyStockCalculator.java`만 트리에 표시

```bash
# Source File API 직접 확인
curl -s "http://localhost:8001/api/modeling/source/file/scm-demo?path=src/main/java/com/ontong/scm/inventory/InventoryManager.java" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'entities: {len(d[\"entities\"])}, language: {d[\"language\"]}')"
# → entities: 10, language: java
```

---

### B-5: 양방향 연동 — Canvas → Viewer

1. 좌측 도메인 그래프에서 **InventoryPlanning** 노드 클릭
2. **확인**: 매핑된 코드 엔티티 확인 (InventoryManager, SafetyStockCalculator)

---

### B-6: 양방향 연동 — Viewer → Canvas

1. 우측에서 `InventoryManager.java` 파일이 열린 상태
2. 에디터의 클래스 선언부 (8번째 줄 부근) 클릭
3. **확인**:
   - 좌측 도메인 그래프에서 **InventoryPlanning** 노드에 ring 하이라이트
   - 매핑 안 된 코드 영역 클릭 시 하이라이트 없음

```bash
# Entity Location API — 양방향 연동의 백엔드
curl -s "http://localhost:8001/api/modeling/source/entity/scm-demo/com.ontong.scm.inventory.InventoryManager"
# → {"qualified_name":"...","file_path":"src/main/java/.../InventoryManager.java","line_start":8,"line_end":47}
```

---

### B-7: 드래그 & 드롭 매핑 생성

1. 엔티티 패널에서 미매핑 엔티티 (빨강 원, 예: `Product`) 를 드래그
2. 도메인 그래프의 아무 노드 위에 드롭
3. **확인**:
   - 드래그 시 커서: grab → link 아이콘
   - 해당 노드의 연결 카운트 증가
   - 엔티티의 원이 빨강 → 초록으로 변경
   - 새로고침 불필요 (즉시 반영)

---

## 트러블슈팅

| 증상 | 원인 | 해결 |
|------|------|------|
| `{"detail":"Not Found"}` on `/engine/*` | 백엔드가 이전 코드로 실행 중 | uvicorn 재시작 |
| 파일 트리가 비어있음 | Seed 미실행 | "SCM 데모 프로젝트 로드" 클릭 |
| 도메인 그래프 안 보임 | 온톨로지 미로드 | Seed 다시 실행 |
| 에디터에 코드 안 나옴 | 파일 미선택 | 파일 트리에서 .java 파일 클릭 |
| 그래프 노드가 작게 보임 | fitView 미적용 | Fit View 버튼 클릭 |
| `simulatable_entities: 0` | 데모 미로드 | "SCM 데모 프로젝트 로드" 클릭 |
| 시뮬레이션 "실행" 비활성 | 파라미터 미변경 | 슬라이더를 기본값에서 변경 |
| Term resolve 실패 | fuzzy threshold 미달 | 정확한 한국어 alias 또는 영문 클래스명 사용 |
| Neo4j 연결 실패 | Docker 미실행 | `docker compose up -d neo4j` |
| 프론트엔드 API 에러 | Next.js proxy 설정 | `next.config.ts`에 `/api/modeling/*` → 8001 확인 |
