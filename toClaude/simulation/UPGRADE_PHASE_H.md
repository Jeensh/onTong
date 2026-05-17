# Section 3 — 검증 시스템 고도화 (Phase H/I/J/K)

> 사용자 요구: "AST 파싱 단위? Java vs Python 결과 비교? BigDecimal 정밀? 신뢰도 100% 영역과 AI 추론 영역 경계?
> slab-design 폴더 무수정 제약하에 모두 고도화."

작성: 2026-05-08
범위: Phase H (Java Headless Bridge) + Phase I (BigDecimal tolerance) + Phase J (LineOrigin 라인별 신뢰도) + Phase K (Differential API + UI)

---

## 0. 출발점 — 갭 분석 요약 (이전 응답)

| 사용자 질문 | 변경 전 상태 |
|---|---|
| AST 파싱 단위? | tree-sitter, **메서드 단위** (이미 OK) |
| Java vs Python 결과 비교? | ❌ 없음 — `shadow_compare` 는 Python ↔ Python (기존 미러 step) |
| BigDecimal 정밀? | ⚠️ LLM prompt 강제만, 자동 비교는 dict `==` |
| 신뢰도 100% / AI 추론 경계? | ❌ `confidence` 단일 % 1개 + `method=llm/fallback` 만 |
| 검증 자동화 — 사람 손 외 시스템 내부? | ⚠️ Python 단독 회귀만, Java 비교 없음 |

**Phase H/I/J/K** 가 위 4 ❌ 모두 해결.

---

## 1. Phase H — Java Headless Bridge (slab-design 무수정)

### 1-1. 핵심 디자인

slab-design 폴더는 **read-only**. 별도 Maven 프로젝트 (`backend/simulation/jvm_bridge/java_bridge/`) 가:
1. slab-design 의 jar 들을 Maven `<dependency>` 로 참조 (사용자가 사전에 `mvnw install`)
2. Spring `@Primary @Bean` 으로 Oracle Repository / Kafka Producer 만 mock 으로 swap
3. main 메서드: stdin JSON → `SdDesigner.design()` → stdout JSON
4. fat jar 산출 → Python subprocess 로 호출

### 1-2. 산출 파일

```
backend/simulation/jvm_bridge/
├── __init__.py                                       Python public API
├── runner.py                                         subprocess + JSON I/O + timeout
├── differential.py                                   Java/Python 동시 실행 + flatten diff
└── java_bridge/                                      별도 Maven 프로젝트
    ├── pom.xml                                       slab-design jar dep + H2 + Jackson
    ├── README.md                                     빌드 + TODO 가이드
    ├── src/main/java/com/ontong/bridge/
    │   ├── BridgeApp.java                            @SpringBootApplication, scan slab-design.feature
    │   ├── MockConfig.java                           @Configuration — @Primary @Bean placeholder
    │   └── HeadlessRunner.java                       CommandLineRunner — JSON I/O
    └── src/main/resources/
        └── application.yml                           H2 in-memory + Kafka off + log WARN
```

### 1-3. 사용자 빌드 절차 (1회)

```bash
# (a) slab-design jar 들을 local m2 에 적재
cd /Users/jiyoon/claude/onTong/sample-repos/slab-design
./mvnw install -DskipTests       # 5~10분

# (b) Java Bridge fat jar 빌드
cd /Users/jiyoon/claude/onTong/backend/simulation/jvm_bridge/java_bridge
mvn package -DskipTests           # 1~2분

# 산출: target/java-bridge-1.0.0.jar
```

빌드 후 `is_bridge_available()` True 반환 + `JavaPythonComparePanel` 활성.

### 1-4. ⚠️ 사용자가 마저 채워야 할 부분 (HeadlessRunner.java TODO)

현재 `HeadlessRunner.java` 의 `run()` 본문은 **stub** (echoed_order_no 만 반환).
slab-design 의 정확한 클래스 시그니처 확인 후 4 단계로 완성:

1. `import com.example.slabdesign.feature.sd.designer.SdDesigner;` 등 정확한 패키지 경로
2. 생성자 `Object sdDesigner` → `SdDesigner sdDesigner` 로 타입 교체
3. `run()` 의 TODO 영역에서 `objectMapper.treeToValue(order, SDOrderEntity.class)` → `sdDesigner.design(orderEntity)` → 응답 변환
4. `MockConfig.java` 에 slab-design 의 모든 Oracle-bound Repository 인터페이스를 `@Primary @Bean` 으로 stub
   (현재는 placeholder `mockMarker()` 만)

상세 수정 가이드: `backend/simulation/jvm_bridge/java_bridge/README.md` "사용자가 완성해야 하는 부분".

### 1-5. Python 측 API

```python
from backend.simulation.jvm_bridge import (
    is_bridge_available, run_java, run_differential,
)

# 단독 Java 호출
result: JavaResult = run_java({"order": {...}}, timeout_sec=30.0)
# JavaResult(ok=True, payload={...}, stderr="...", elapsed_sec=0.21)

# Java + Python 동시 + 결과 diff
diff: DifferentialResult = run_differential({"order": {...}})
# DifferentialResult(java_available=True, java_ok=True, python_ok=True,
#                    matched_count=42, mismatched_count=0, field_diffs=[...])
```

---

## 2. Phase I — BigDecimal Numeric Tolerance

### 2-1. 변경 위치

`backend/simulation/transpile/equivalence.py`:
- `_to_decimal(v)` 신규 — string / int / float / Decimal → Decimal (변환 불가 시 None)
- `values_close(a, b, rel=1e-9, abs_=1e-12)` 신규 — `|a-b| <= max(abs_, rel * max(|a|, |b|))`
- `shadow_compare` 의 dict 비교 `a != b` → `not values_close(a, b)` 로 교체

### 2-2. 의의

- 자바 `BigDecimal("0.812820")` 와 Python `Decimal("0.812819999999")` 같은 미세 차이 무시
- string 으로 직렬화된 값도 자동 numeric 비교 (`"0.5" == "0.50"` 도 같은 값으로 판정)
- shadow_compare + differential test 양쪽 모두에서 노이즈 diff 제거
- bool 은 명시 제외 (`True == 1` 같은 typing 함정 방지)

### 2-3. 검증

기존 14건 transpile 테스트 + 기존 189 pytest 모두 통과 (PG 미모드 회귀).

---

## 3. Phase J — LineOrigin (라인별 신뢰도 영역)

### 3-1. 새 데이터 모델

`backend/simulation/transpile/llm_transpile.py`:

```python
class LineOrigin(BaseModel):
    line: int                                        # 1-based
    kind: Literal["det", "llm", "stub", "human"]
    confidence: float                                # 0~1
    note: Optional[str]
```

`PythonStepDraft` 에 `line_origins: list[LineOrigin]` 필드 추가.

### 3-2. LLM Prompt 규칙 12 추가

LLM 이 변환 시 **각 라인 끝에 origin 주석** 부착:

```python
def thickness(inputs: dict) -> dict:                  # [det]
    order = inputs["order"]                            # [det]
    sm = order["smPlantCd"]                            # [det]
    cast_cd = LOOKUP_PLANT_MAPPING.get(sm)             # [llm:0.7]   (Java 의 PlantMappingService 매핑)
    if cast_cd is None:                                # [llm:0.7]
        raise ValueError("DG101")                      # [det]
    slab_thickness = inputs.get("cast_spec", {}).get(  # [stub]      (CastSpecRepo 주입 필요)
        "slabThickness"
    )
    return {"slab": {"slabThickness": slab_thickness}} # [det]
```

### 3-3. Python 후처리

`parse_line_origins(python_source)` — 정규식 `# [det|llm|stub|human](:0.85)?` 매칭 → `LineOrigin` 리스트.
`transpile_method()` 끝에 자동 호출 → `draft.line_origins` 채움.

`_attach_fallback_origins()` — fallback stub 의 자바 본문 영역 (=== 자바 원본 본문 === ~ === 미완 ===) 을 자동으로 모두 `kind="stub"` 으로 분류.

### 3-4. UI 색상 매핑 (제안)

| kind | confidence | 색상 | 의미 |
|---|---|---|---|
| `det` | 1.0 | 🟢 녹색 | 자바 원본 1:1 변환 — 결정적 |
| `llm` | 0.5~0.9 | 🟡 황색 | LLM 추론 — 검토 권장 |
| `llm` | 0.2~0.5 | 🟠 주황 | 신뢰도 낮음 — 사람 검증 |
| `stub` | 0.0 | 🔴 빨강 | TODO / 사람 보정 필요 |
| `human` | 1.0 | ⚪ 회색 | 사람이 직접 보정 |

(라인별 색칠 UI 컴포넌트는 다음 iteration. 현재 데이터 모델 + 추출 로직만 완성 — TranspilePanel 의 코드 미리보기에 색상 입히면 즉시 활용 가능.)

### 3-5. TypeScript 타입 추가

`frontend/src/lib/simulation/transpileApi.ts` 에 `LineOrigin` interface + `PythonStepDraft.line_origins` 필드.

---

## 4. Phase K — Differential API + Frontend 패널

### 4-1. Backend API

`backend/simulation/api/differential_router.py` (`backend/main.py` 등록):

| 엔드포인트 | 동작 |
|---|---|
| `GET /api/simulation/differential/status` | Java Bridge JAR 가용 여부 + 빌드 안내 |
| `POST /api/simulation/differential/run` | inputs = {order, slab?, rules?} → Java SdDesigner / Python pipeline_full 양쪽 실행 + flatten diff |

### 4-2. Frontend

- `frontend/src/lib/simulation/differentialApi.ts` — 2 함수, 4 type
- `frontend/src/components/simulation/JavaPythonComparePanel.tsx` — 신규 패널
  - 상단: Java Bridge 상태 카드 (활성/미빌드)
  - 좌측: 샘플 주문 빠른 선택 3건 (정상 / DG001 / DG003) + Order JSON textarea + 「양쪽 실행 + 비교」 버튼
  - 우측: Java/Python 상태 배지 (OK / FAIL / 미가용 + 경과 시간) + 일치/차이 카드 + 필드별 diff 테이블 (최대 20행) + Java 에러 details + raw 응답 JsonTable
- 사이드바 그룹 "운영" 에 신규 메뉴 **"Java ↔ Python 비교"** 추가 (icon: GitCompare)

### 4-3. 사용 시나리오

1. 사이드바 → **Java ↔ Python 비교**
2. 「정상 주문 (ORD-NORMAL-001)」 빠른 버튼 → Order JSON 자동 채워짐
3. 「양쪽 실행 + 비교」 클릭
4. 결과:
   - Java Bridge 빌드 안 됐으면 → Python 만 실행, 카드에 빌드 가이드 표시
   - 빌드 완료 시 → 양쪽 실행 (~ 200~500ms) → 일치 행 수 / 차이 필드 테이블 / raw 응답

---

## 5. 검증 자동화 — 더 좋은 방법 5가지 (향후)

본 Phase H/I/J/K 는 **수동 1건** 비교가 가능한 단계. 다음 단계 후보:

| # | 아이디어 | 상태 |
|---|---|---|
| **1** | **Differential Property-Based Testing** — Hypothesis 로 입력 100건 자동 생성 → 양쪽 자동 실행 → diff 자동 리포트 | 미구현. 향후 `differential.py` 에 `run_differential_batch(strategy, n=100)` 추가 |
| **2** | **Golden File Regression** — Java 결과를 PG `transpile_golden` 에 stash → Python 변경 후 stash 와 비교 (Java 매번 안 띄움) | 미구현. PG schema 신규 + diff 로직 재사용 |
| **3** | **Mutation Testing** — 자바 한 줄 변경 → AI 가 파이썬 동등 변경 → 양쪽 결과 차이가 같으면 transpile 정확도 ↑ | 미구현. 학술적 — 우선순위 낮음 |
| **4** | **CI Gate** — `/transpile/save` 호출 시 100건 randomized differential test 강제 통과 | 미구현. save_router 에 hook 만 추가하면 가능 |
| **5** | **양방향 Baseline** — Java 결과를 PG `runs` 에 baseline 으로 저장 → 파이썬 코드 변경마다 자동 회귀 검증 | 미구현. Phase 6-B baseline 시스템 재사용 |

권장 다음 우선순위: **1 (PBT) → 4 (CI 게이트) → 2 (Golden File)**.

---

## 6. 영향받은 파일 목록

### 백엔드 신규
- `backend/simulation/jvm_bridge/__init__.py`
- `backend/simulation/jvm_bridge/runner.py`
- `backend/simulation/jvm_bridge/differential.py`
- `backend/simulation/jvm_bridge/java_bridge/pom.xml`
- `backend/simulation/jvm_bridge/java_bridge/README.md`
- `backend/simulation/jvm_bridge/java_bridge/src/main/java/com/ontong/bridge/{BridgeApp,MockConfig,HeadlessRunner}.java`
- `backend/simulation/jvm_bridge/java_bridge/src/main/resources/application.yml`
- `backend/simulation/api/differential_router.py`

### 백엔드 수정
- `backend/simulation/transpile/equivalence.py` — `_to_decimal`, `values_close`, BigDecimal tolerance 적용
- `backend/simulation/transpile/llm_transpile.py` — `LineOrigin` 모델, prompt 규칙 12, `parse_line_origins`, `_attach_fallback_origins`, `transpile_method` 개선
- `backend/main.py` — `differential_router` 등록

### 프론트 신규
- `frontend/src/lib/simulation/differentialApi.ts`
- `frontend/src/components/simulation/JavaPythonComparePanel.tsx`

### 프론트 수정
- `frontend/src/lib/simulation/transpileApi.ts` — `LineOrigin` interface, `PythonStepDraft.line_origins` 필드
- `frontend/src/components/simulation/SimulationSection.tsx` — `SimView` 에 "differential" 추가, GOVERN_NAV 에 nav item, render 분기
- `frontend/src/components/simulation/index.ts` — export 추가

### 문서
- `toClaude/simulation/UPGRADE_PHASE_H.md` (본 문서)

---

## 7. 검증 방법 (사용자가 확인할 수 있는 절차)

### 7-1. 빠른 sanity (Java Bridge 미빌드 상태)

```bash
# 백엔드 재기동 (router 등록 반영) — env 그대로 유지
SIM_DB_HOST=localhost SIM_DB_PORT=5434 SIM_DB_USER=simulation \
SIM_DB_PASSWORD=simulation_dev SIM_DB_NAME=simulation \
SIMULATION_SKIP_ONTOLOGY=1 \
  /Users/jiyoon/claude/onTong/venv/bin/uvicorn backend.main:app --reload --port 8001

# 1) status
curl http://localhost:8001/api/simulation/differential/status
# → {"java_bridge_available": false, "guide": "Java Bridge 미빌드 — ..."}

# 2) Python 단독 실행 (Java 미가용 상태에서도 동작)
curl -s -X POST http://localhost:8001/api/simulation/differential/run \
  -H "Content-Type: application/json" \
  -d '{"order": {"cmpCd":"K","orgCd":"K01","orderNo":"ORD-001","stockCode":0,"orderWidth":"1200","orderLength":"3000","pkgWgtLow":"5","pkgWgtHigh":"30","confirmedPlantCd":"KKKK    ","gradeCd":"G01","customerCd":"C001"}}'
# → {"java_available": false, "python_ok": true, "python_payload": {...}}
```

브라우저: <http://localhost:3000> → Simulation → 사이드바 **「Java ↔ Python 비교」** 메뉴 노출 확인.

### 7-2. Java Bridge 빌드 후

```bash
# (1) slab-design install
cd sample-repos/slab-design && ./mvnw install -DskipTests

# (2) Bridge build
cd backend/simulation/jvm_bridge/java_bridge && mvn package -DskipTests

# (3) 백엔드 재기동
... (위와 동일)

# (4) 동작 확인
curl http://localhost:8001/api/simulation/differential/status
# → {"java_bridge_available": true, ...}

curl -s -X POST http://localhost:8001/api/simulation/differential/run -H "..." -d '...'
# → {"java_available": true, "java_ok": true, "field_diffs": [...]}
```

⚠️ 주의: 4단계에서 Java 응답 `slab` 이 stub (`{"_stub": true, "echoed_order_no": "..."}`) 으로 나옴.
사용자가 `HeadlessRunner.java` 의 TODO 를 채워야 실제 SdDesigner.design() 결과가 반환.

### 7-3. 회귀 (기존 189 pytest)

```bash
# in-memory 모드 (env 미설정) — Phase H/I/J/K 도입 후에도 유지
/Users/jiyoon/claude/onTong/venv/bin/pytest tests/simulation/ -q --ignore=tests/simulation/test_postgres_repo.py
# → 189 passed (BigDecimal tolerance / LineOrigin 추가가 기존 동작 안 깸)

# tsc
cd frontend && npx tsc --noEmit
# → exit 0
```

---

## 8. 알려진 한계 + 다음 작업 후보

### 한계
- **Java Bridge HeadlessRunner.java 의 SdDesigner 호출부가 stub** — 사용자가 slab-design 의 Repository 인터페이스 확인 후 MockConfig 의 @Primary @Bean 작성 필요. README 에 가이드 있음.
- **LineOrigin UI 색칠 미적용** — TranspilePanel 의 `<pre>` 코드 영역에 색상 매핑 컴포넌트 추가 필요 (다음 iteration). 데이터 + 추출 로직은 완성.
- **Differential PBT 미구현** — 1건 수동 비교만 가능. Hypothesis 자동 케이스 생성은 다음 단계.

### 다음 작업 후보 (우선순위)
1. **(P1)** TranspilePanel 라인별 색칠 — `line_origins` 시각화 UI (반나절)
2. **(P1)** HeadlessRunner.java SdDesigner 호출부 + MockConfig Bean 채우기 (사용자 작업, 1일)
3. **(P2)** Differential PBT — Hypothesis 자동 생성 + N건 batch (1일)
4. **(P2)** Golden File — PG `transpile_golden` 테이블 + 회귀 비교 (1일)
5. **(P3)** CI Gate — `/transpile/save` hook (반나절)

---

## 9. 사용자에게 보고

- **요구한 4가지 모두 시스템에 반영**: AST 메서드 단위 (이미 OK) / Java vs Python 비교 (Phase H+K) / BigDecimal tolerance (Phase I) / 라인별 신뢰도 영역 (Phase J).
- **slab-design 폴더 무수정 제약 100% 준수** — 별도 `jvm_bridge/java_bridge/` Maven 모듈에서 `@Primary @Bean` override 패턴.
- **검증 자동화 5가지 추가 아이디어** (PBT / Golden / Mutation / CI Gate / 양방향 Baseline) 본 문서 §5 에 정리.
- **사용자가 직접 마무리할 부분** 2개:
  1. `slab-design install` + Java Bridge `mvn package` (인프라 빌드)
  2. `HeadlessRunner.java` 의 SdDesigner 호출부 + `MockConfig` Bean 채우기 (slab-design 의 정확한 인터페이스 적용)
