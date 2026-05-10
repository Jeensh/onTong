# Section 3 시뮬레이션 — 직접 검증 시나리오 가이드

> 사용자가 직접 데이터를 주입하고 화면에서 모든 기능을 검증하기 위한 가이드.
> 각 시나리오 = **(0) 검증 포인트** → **(1) 데이터 주입 위치 (파일:줄)** → **(2) 화면 클릭 단계** → **(3) 기대 결과** → **(4) 실패 시 디버깅** 구조.

마지막 갱신: 2026-05-05 (Phase G — PostgreSQL DB 모드 추가, slab-design JPA 미러)

---

## 0. 시작하기 전에 — 데이터 주입 모델 (★ 중요)

Section 3 는 **두 가지 모드** 로 데이터를 사용합니다. 환경변수로 토글.

### 0.1 모드 비교

| 모드 | 활성 조건 | 데이터 위치 | 변경 방법 |
|---|---|---|---|
| **A. in-memory** (기본) | env 미설정 | `backend/simulation/sandbox/fixtures/fixtures.py` 의 factory 함수 | Cursor 에서 dataclass `__init__` 인자 수정 → uvicorn reload |
| **B. PostgreSQL** (★ 신규, Phase G) | `SIM_DB_HOST` 등 env 설정 + `simulation-postgres` 컨테이너 기동 | `simulation` PG DB 의 10 테이블 (slab-design JPA 그대로 미러) | (1) 홈 「DB 시드 초기화」 버튼 / (2) DBeaver/psql 직접 INSERT / (3) fixtures 수정 후 재시드 |

**룰 override 입력 (rules.hr 등)** 은 두 모드 모두 in-memory 로 처리 — 휘발성 시뮬이라 PG 불요.

### 0.2 Mode B (PG) 기동 — 사용자 직접 검증 시 권장

```bash
# 1) 의존성 설치 (1회)
poetry install
# 또는 venv: pip install 'psycopg[binary]>=3.2,<4'

# 2) PG 컨테이너 기동
docker-compose up -d simulation-postgres
# 컨테이너명: ontong-simulation-postgres / port 5434 → 5432

# 3) 환경변수 (.env 또는 export)
export SIM_DB_HOST=localhost
export SIM_DB_PORT=5434
export SIM_DB_USER=simulation
export SIM_DB_PASSWORD=simulation_dev
export SIM_DB_NAME=simulation

# 4) 백엔드 + 프론트
source venv/bin/activate
SIMULATION_SKIP_ONTOLOGY=1 uvicorn backend.main:app --reload --port 8001
cd frontend && npm run dev   # :3000

# 5) 브라우저: http://localhost:3000 → Simulation → 홈
#    → 상단 「PostgreSQL 시드 데이터」 카드의 "DB 시드 초기화" 클릭
#    → 9 마스터 + 주문 5건 적재됨 (각 테이블 행 수 표시)
```

**시드 직후 PG 의 10 테이블**:
| 테이블 | 시드 행 수 | 내용 |
|---|---|---|
| `plant_mapping` | 5 | A/B/C/D/K → CC*/M* |
| `cast_spec` | 3 | 두께 220/250/210 |
| `hr_spec` | N | hrPlantCd × prodTypeCd 매트릭스 |
| `edging_spec` | M | 그룹코드 + '*' wildcard |
| `edging_group` | M | priority ASC |
| `hr_min_wgt`, `hr_max_wgt` | 2D | thickness × width 셀 |
| `productivity_std` | 8 | 8 공정 실수율 (HR 0.95 / HRF 0.93 / ANL1 0.92 …) |
| `customer_std` | M | 옵션 제약 |
| `order_os` | **5** | 정상 / DG001 / DG002 / DG003 / DG109 후보 |

**검증 명령** (PG 활성 확인):
```bash
curl http://localhost:8001/api/simulation/seed/status
# {"counts": {"plant_mapping": 5, "cast_spec": 3, ..., "order_os": 5}}

curl http://localhost:8001/api/simulation/orders | jq '.orders[].order_no'
# "ORD-NORMAL-001" / "ORD-DG001-STOCK" / "ORD-DG003-PKGWGT" / ...
```

### 0.3 데이터 편집 3 경로 (PG 모드)

검증할 때 데이터를 변경하는 방법은 3가지:

1. **DBeaver / psql 직접 INSERT** (가장 강력) — 새 row 추가, 기존 row UPDATE. 즉시 반영.
   ```bash
   psql postgresql://simulation:simulation_dev@localhost:5434/simulation
   simulation=# UPDATE cast_spec SET slab_thickness = 230 WHERE prod_type_cd = 'A001';
   ```
2. **fixtures.py 수정 + 재시드** — 코드 단의 default 데이터를 바꾸고 「DB 시드 초기화」 클릭. 모든 사용자 추가 row 는 사라짐 (TRUNCATE).
3. **UI 룰 override** — `rules.hr=0.50` 같은 1회성 입력. PG 안 건드림.

### 0.4 Mode A (in-memory) 가 필요한 케이스

다음은 PG 모드여도 in-memory 가 강제됩니다:
- **룰 override 가 들어온 productivity 호출** (`rules.hr/hrf/anl1`) — 휘발성
- **EDGING_SPEC wildcard 제거 시뮬** (`include_wildcard=false`) — 시나리오 14
- **PlantMapping 마이그 시뮬** — UI 가 dict 를 직접 변경하는 시뮬

---

## A. slab-design 시스템 한눈에

### A.1 21-step 알고리즘 흐름

| Phase | Step | 자바 클래스 | Section 3 step_id | 1줄 설명 |
|---|---|---|---|---|
| **P1 — 사전 처리** | P1.1 | `SdOrderValidator` | `validator` | DG001~005 정합성 점검 |
| | P1.2 | `SdProductClassifier` | (silent) | COIL 만 통과 |
| | P1.3.c | `ProductivityService` | `productivity` | 누적 실수율 = HR × HRF × ANL1 × ... (활성 공정 곱) |
| **P2 — one-shot (1~7)** | 1 | `SdThicknessAction` | `thickness` | CAST_SPEC 룩업 → Slab 두께 |
| | 2 | `SdWidthRangeAction` | `width_range` | CastSpec ∩ HrSpec ∩ EdgingGroup+Spec |
| | 3 | `SdLengthRangeAction` | `length_range` | CastSpec ∩ HrSpec |
| | 4 | `SdFirstWeightAction` | (Phase 6+ pipeline 내부) | 1차 단중 |
| | 5 | `SdSecondWgtLowAction` | `second_wgt` (low) | HR_MIN_WGT 2D 룩업 |
| | 6 | `SdSecondWgtHighAction` | `second_wgt` (high) | HR_MAX_WGT 2D 룩업 |
| | 7 | `SdMaxSplitCountAction` | `max_split` | A-a 루프 시작점 |
| **P2 — A-a 루프 (8~15)** | 8 | `SdSplitRangeAction` | `split_range` | 분할 범위 |
| | 9 | `SdSlabCountAction` ★ | `slab_count` | Slab 매수 (★ 데모 핵심) |
| | 10 | `SdInitialSlabWgtAction` | `slab_weight` | 초기 단중 (통과 시 루프 탈출) |
| | 12-13 | `SdSlabWgtRecalcAction` | `slab_weight` 재실행 | 단중 재산정 (실패 시 분할수 -1 후 재시도) |
| **P2 — final (16~19)** | 16 | `SdFinalWidthRangeAction` | `final_width_range` | 최종 폭 |
| | 17 | `SdFinalLengthRangeAction` | `final_length_range` | 최종 길이 |
| | 18-19 | `SdTargetWidthAction/LengthAction` | `target_size` | 목표 치수 |
| **P2 — save (20~21)** | 20 | `SdSlabSaveAction` | (사이드 effect, sandbox 미포함) | SLAB_RESULT 적재 |
| | 21 | `SdHistoryAction` | (사이드 effect, sandbox 미포함) | HISTORY 적재 |

`pipeline_full` step 은 **validator → productivity → thickness → width_range → length_range → second_wgt → max_split → split_range → slab_count → slab_weight → final_width → final_length → target_size** 순으로 호출.

### A.2 핵심 도메인 클래스 (자바 = Python dataclass)

| 자바 | Python (sandbox) | 핵심 필드 |
|---|---|---|
| `SDOrderEntity` | `SDOrder` | `orderWidth/Length`, `orderWgtLow/High`, `pkgWgtLow/High`, `confirmedPlantCd`, `smDue`, `gradeCd` |
| `SDSlabEntity` | `SDSlab` | `slabThickness`, `currentSplitCount`, `maxSplitCount`, `secondWgtLow/High`, `firstWidth/Length`, `targetWidth/Length` |
| `CastSpecEntity` | `CastSpec` (Repo) | `smCd/castCd/machineCd/productTypeCd`, `slabThickness`, `widthLow/High`, `lengthLow/High`, `wgtLow/High` |
| `HrSpecEntity` | `HrSpec` (Repo) | `hrPlantCd`, `productTypeCd`, `widthLow/High`, `lengthLow/High` |
| `EdgingSpecEntity` | `EdgingSpec` (Repo, '*' fallback) | `edgingGroupCd`, `edgingCapLow/High` |
| `PlantMappingService` | `PlantMappingRepo` | `smCd → (castCd, machineCd)` 매핑 + `.has()/.default()` |

### A.3 에러 코드

| 코드 | 시점 | 의미 |
|---|---|---|
| **DG001** | validator | 재고주문 (`stockCode=1`) 진입 차단 |
| **DG002** | validator | 주문 폭/길이 양수 아님 |
| **DG003** | validator | 포장단중 범위 정합성 위반 (`pkgWgtLow > pkgWgtHigh`) |
| **DG004** | validator | 설계대기량 상한 < 포장단중 하한 |
| **DG005** | validator | 작업기한일 미설정 또는 과거 |
| **DG101** | thickness, length_range | CAST_SPEC 미존재 |
| **DG102** | width_range, length_range | HR_SPEC 미존재 |
| **DG103** | width_range | EDGING_GROUP 미존재 |
| **DG104** | width_range | 폭 범위 invalid (low > high) |
| **DG105** | length_range | 길이 범위 invalid |
| **DG106** | second_wgt | HR_MIN_WGT 미존재 |
| **DG107** | second_wgt | HR_MAX_WGT 미존재 |
| **DG109** | A-a 루프 | 분할수 1까지 모두 실패 |

---

## B. Section 3 사이드바 한눈에

| # | 좌측 사이드바 라벨 | view key | 패널 컴포넌트 |
|---|---|---|---|
| 1 | **홈 (개요)** | `home` | `HomeDashboardPanel` |
| 2 | **안전 가상 실행 (샌드박스)** | `sandbox` | `SandboxPanel` |
| 3 | **시나리오 라이브러리** | `scenarios` | `ScenarioLibraryPanel` |
| 4 | **실행 이력** | `history` | `RunHistoryPanel` |
| 5 | **재실행 비교 (차이 검증)** | `regression` | `RegressionPanel` |
| 6 | **변경 영향 분석** | `impact` | `Agent1ImpactPanel` |
| 7 | **온톨로지 브릿지** | `bridge` | `OntologyBridgePanel` |
| 8 | **코드 내비게이터** | `navigator` | `NavigatorPanel` |

---

## C. 데이터 주입 — Cursor 위치 가이드

본 가이드의 시나리오들은 다음 위치들을 사용합니다. Cursor 에서 미리 열어두세요.

```
backend/simulation/sandbox/fixtures/fixtures.py     ← in-memory factory
backend/simulation/storage/postgres/schema.sql      ← PG 스키마 (10 테이블)
backend/simulation/storage/postgres/seed.py         ← 샘플 주문 5건 정의
backend/simulation/data/scenarios/rule_changes.yaml ← 시나리오 시드
backend/simulation/sandbox/fixtures/steps/          ← 자바 미러 step (룰 자체)
sample-repos/slab-design/.../action/                ← 자바 원본 (Auto-PR 검증)
frontend/src/lib/simulation/autoPrApi.ts            ← Auto-PR 매핑 추가
```

**PG 모드 SQL 빠른 참조** (DBeaver/psql 에서):

```sql
-- 모든 주문 보기
SELECT order_no, stock_code, order_width, order_length,
       pkg_wgt_low, pkg_wgt_high, grade_cd
  FROM order_os ORDER BY order_no;

-- 새 비정상 주문 추가 (예: DG003 변형 — 음수 폭)
INSERT INTO order_os (cmp_cd, org_cd, order_no, stock_code,
                      order_width, order_length, pkg_wgt_low, pkg_wgt_high,
                      product_type_cd, grade_cd, customer_cd)
  VALUES ('K', 'K01', 'ORD-CUSTOM-001', 0,
          -100, 3000, 5, 30, 'A001', 'G01', 'C001');

-- CastSpec 두께 변경 (시나리오 4 변형: 매칭 성공하지만 결과 달라짐)
UPDATE cast_spec SET slab_thickness = 250 WHERE prod_type_cd = 'A001';

-- EDGING_SPEC wildcard row 제거 (시나리오 14 PG 변형)
DELETE FROM edging_spec WHERE edging_group_cd = '*';

-- HR 실수율 (productivity_std) 변경 (시나리오 6 영구 변경)
UPDATE productivity_std SET productivity = 0.50
  WHERE proc_cd = 'HR' AND grade_cd = 'G01';
```

각 시나리오마다 **"PG 모드"** / **"in-memory 모드"** 두 경로를 모두 안내합니다.

---

# 검증 시나리오 (총 15종)

## 시나리오 1 — 정상 주문 끝까지 통과 ✅ (smoke test)

**검증 포인트**: pipeline_full 이 default fixtures 만으로 끝까지 PASS 하는가? 모든 step 출력이 채워지는가?

### 1.1 데이터 주입
**없음** — `fixtures.py:36-74` `make_default_order()` 의 default 값이 정상 주문. 그대로 사용.

### 1.2 화면 클릭

1. 사이드바 → **"안전 가상 실행 (샌드박스)"** 클릭
2. 좌측 **대상 Step** select → `pipeline_full` 선택
3. 케이스 유형: **[정상]** 만 체크 (다른 항목 해제)
4. 테스트 수: `5`
5. 룰 변경 펼치기는 그대로 (변경 없음)
6. **▶ 실행** 클릭

### 1.3 기대 결과

- 우측 **SandboxConsole** 에 `case 1 ... case 5 done` 까지 SSE 진행
- **ResultChart**: pass=5, fail=0
- **실패 케이스 테이블**: 비어있음
- **TimelineScrubber**: cursor 1~5, matched 100%
- 어떤 cursor 위치에서도 JsonTable 미리보기에 `slab.slabThickness`, `slab.targetWidth`, `slab.targetLength` 모두 값 채워짐

### 1.4 실패 시
- pass < 5 → fixtures 디폴트가 망가졌다는 뜻. `git diff backend/simulation/sandbox/fixtures/fixtures.py` 로 변경분 확인
- SSE 끊김 → 백엔드 로그 확인 (`uvicorn` stdout)

---

## 시나리오 2 — DG001 재고주문 차단 🚫

**검증 포인트**: `stockCode=1` 주문이 validator 에서 즉시 fail 하는가?

### 2.1 데이터 주입

**수정 위치**: 화면에서 직접 입력 (fixtures 수정 불필요).

### 2.2 화면 클릭

1. 사이드바 → **"안전 가상 실행 (샌드박스)"**
2. 대상 Step → `validator`
3. 케이스 유형: **[오류]** 만 체크
4. 테스트 수: `1`
5. 화면에 직접 입력 input 이 보이는 케이스가 있다면 `order.stockCode = 1` 설정. 없다면 시나리오 라이브러리 5번으로 갈음:
   - 사이드바 → **"시나리오 라이브러리"** → "재고주문 차단" 검색 → ▶ 실행

### 2.3 기대 결과

- ResultChart: fail=1, pass=0
- 실패 케이스 테이블에 `error_code: "DG001"` 메시지
- TimelineScrubber 의 actual_output JsonTable 에 `error_code = DG001` 표기

### 2.4 실패 시
- `error_code` 가 다른 값이면 → `backend/simulation/sandbox/fixtures/steps/validator.py` (또는 동등 위치) 의 stockCode 검사 로직 확인

---

## 시나리오 3 — DG003 포장단중 범위 위반 (사용자 직접 편집)

**검증 포인트**: validator 가 `pkgWgtLow > pkgWgtHigh` 인 주문을 거부하는가?

### 3.1 데이터 주입

**[PG 모드]** — 시드된 `ORD-DG003-PKGWGT` 주문이 이미 존재. 별도 작업 없음.
검증: `psql ... -c "SELECT order_no, pkg_wgt_low, pkg_wgt_high FROM order_os WHERE order_no='ORD-DG003-PKGWGT'"` → low=12, high=8.

**[in-memory 모드]** — `backend/simulation/sandbox/fixtures/fixtures.py` 의 `make_default_order()` (대략 line 36~74 사이) 수정.

```python
# 기존 (정상)
pkgWgtLow=Decimal("8.0"),
pkgWgtHigh=Decimal("12.0"),

# 변경 (DG003 트리거)
pkgWgtLow=Decimal("12.0"),
pkgWgtHigh=Decimal("8.0"),     # low > high
```

저장 → uvicorn 자동 reload (--reload 켜진 경우).

### 3.2 화면 클릭

1. **"안전 가상 실행 (샌드박스)"** → step `validator` → 정상 1건 실행
2. 또는 step `pipeline_full` → 정상 1건 실행 → 첫 step 에서 fail

### 3.3 기대 결과

- pass=0, fail=1
- 실패 케이스 → `error_code: "DG003"`

### 3.4 실패 시
- DG002 (양수 검사) 가 먼저 잡히면 → `orderWidth/Length` 가 0/음수가 아닌지 확인

### 3.5 정리

검증 끝나면 fixtures.py 의 두 줄을 원래대로 복구 (또는 `git checkout backend/simulation/sandbox/fixtures/fixtures.py`).

---

## 시나리오 4 — DG101 CAST_SPEC 미존재 (Repo 비우기)

**검증 포인트**: thickness step 이 매칭되는 CastSpec row 가 없을 때 DG101 을 던지는가?

### 4.1 데이터 주입

**[PG 모드]** — 가장 빠른 경로:
```sql
TRUNCATE TABLE cast_spec;
-- 또는 특정 row 만:
DELETE FROM cast_spec WHERE prod_type_cd = 'A001';
```
검증 후 복구: 「DB 시드 초기화」 클릭 → 원래 3행 복구.

**[in-memory 모드]** — `fixtures.py:91-111` `make_default_cast_spec()` 수정.

```python
# 기존: 3개 row 반환
def make_default_cast_spec():
    repo = CastSpecRepo()
    repo.add(CastSpec(smCd="A", castCd="CC1", machineCd="M1", productTypeCd="COIL",
                      slabThickness=Decimal("220"), ...))
    repo.add(CastSpec(... 250mm ...))
    repo.add(CastSpec(... 다른 강종 ...))
    return repo

# 변경: 빈 Repo 반환 (한 줄 위에 early return)
def make_default_cast_spec():
    return CastSpecRepo()  # ★ 빈 Repo
```

### 4.2 화면 클릭

1. **"안전 가상 실행 (샌드박스)"** → step `thickness` → 정상 1건 실행

### 4.3 기대 결과

- fail=1, `error_code: "DG101"`

### 4.4 정리
- fixtures.py 복구

---

## 시나리오 5 — DG109 A-a 루프 끝까지 실패 (분할수 강제)

**검증 포인트**: A-a 루프가 분할수 max→1 모두 실패 시 DG109 로 종료되는가?

### 5.1 데이터 주입

극단적으로 좁은 단중 범위로 `make_default_order` 수정:

```python
# fixtures.py make_default_order()
orderWgtLow=Decimal("99.0"),
orderWgtHigh=Decimal("99.5"),  # 매우 좁아서 어떤 분할수에서도 통과 불가
pkgWgtLow=Decimal("99.0"),
pkgWgtHigh=Decimal("99.5"),
```

### 5.2 화면 클릭

1. **"안전 가상 실행 (샌드박스)"** → step `pipeline_full` → 정상 1건

### 5.3 기대 결과

- fail=1, error_code 가 `DG109` (A-a 루프 끝까지 실패) 또는 `DG104/105` (범위 무효) — 어느 쪽이든 의미는 "기준 데이터 좁아서 실패"

### 5.4 정리 → fixtures.py 복구

---

## 시나리오 6 — HR 실수율 변경 → 영향 분석 ★ 핵심 시연

**검증 포인트**: HR 실수율을 0.93 → 0.50 으로 바꾸면 step 6/9 에 cascade 효과가 시각화되는가?

### 6.1 데이터 주입
**없음** — UI 에서 룰 override 만으로 검증.

### 6.2 화면 클릭

1. 사이드바 → **"변경 영향 분석"** 클릭
2. **변경 대상** select → `HR 실수율 (default 0.93)`
3. **새 값** input → `0.50`
4. **표본 크기** slider → `30`
5. **▶ 영향도 분석 실행** 클릭 (약 10초 대기)

### 6.3 기대 결과

- 분석 요약 카드: "표본 30건 중 N건의 Slab 매수 변동"
- Plotly overlay histogram × 4 (누적 실수율 / Slab 매수 / Slab 단중 / 분할단중 상한)
- 누적 실수율 차트: 변경 전(회색) ~0.81 ↔ 변경 후(파란색) ~0.50
- Slab 매수: 분포 우측 이동 (실수율 ↓ → 매수 ↑)
- **변화 매트릭스 (2x2)**: 「유지 OK / 새로 깨짐 ★ / 개선됨 / 유지 Fail」 4셀 채워짐
- Δ평균 / Δ% 카드 — 메트릭별 변동률 색상 구분

### 6.4 What-if 슬라이더로 즉시 탐색 (신박 1호 검증)

6.3 결과 영역에 **슬라이더** (0.500~1.000) 노출 확인:
1. 슬라이더 우측 끝 (1.000) 으로 드래그 → 600ms 후 매트릭스 갱신, "유지 OK" 셀이 늘어남
2. 좌측 끝 (0.500) → "새로 깨짐" 셀 증가
3. 중간값 (0.700) → 부분 cascade

### 6.5 실패 시
- 슬라이더 미노출 → 사전 영향도 분석 미실행. 6.2 단계 다시 실행
- 매트릭스 4셀이 모두 같은 값 → 표본 너무 작음. sample_size 50 이상으로

---

## 시나리오 7 — 시나리오 라이브러리 1-click 실행 + Export/Import

**검증 포인트**: `data/scenarios/rule_changes.yaml` 의 8건 시드가 잘 등록되고, 한 번의 클릭으로 잡 큐에 등록되는가?

### 7.1 데이터 주입

**수정 위치**: `backend/simulation/data/scenarios/rule_changes.yaml` 끝에 새 entry 추가.

```yaml
- id: scn-user-test-001
  name: "내 테스트 — HR 0.85"
  description: "사용자 직접 작성 시나리오"
  step_id: pipeline_full
  tags: ["my-test"]
  inputs:
    rules:
      hr: "0.85"
    order:
      orderWidth: "1500"
      orderLength: "8000"
```

### 7.2 화면 클릭

1. 사이드바 → **"시나리오 라이브러리"**
2. 헤더 **"초기화"** (Seed) 버튼 클릭 → YAML 시드가 SQLite 에 멱등 적재
3. 태그 필터 → `my-test` 클릭 → 새 시나리오 1건 노출 확인
4. 그 row 의 **▶ 실행** 클릭 → 잡 큐 등록 알림 (Toast)
5. 사이드바 → **"실행 이력"** 으로 이동 → 4초 폴링으로 신규 run 등장

### 7.3 Export 검증
1. ScenarioLibrary 헤더 **Export YAML** 클릭 → `.yaml` 다운로드
2. 파일 열어 보면 9건 (기존 8 + 신규 1) 포함

### 7.4 Import 검증
1. **Import YAML** 토글 → textarea 에 다음 paste:
```yaml
- id: scn-import-test
  name: "임포트 테스트"
  step_id: validator
  inputs:
    order:
      stockCode: 1
```
2. **추가** 클릭 → 시나리오 +1 등장 확인

### 7.5 실패 시
- "초기화" 후에도 신규 시나리오 미노출 → YAML 문법 오류. 백엔드 로그에서 `yaml.scanner.ScannerError` 확인

---

## 시나리오 8 — baseline 등록 → 자동 회귀 검증

**검증 포인트**: 기준 결과 등록 후 같은 시나리오 재실행 시 자동 diff 가 첨부되는가?

### 8.1 데이터 주입
없음 (시나리오 7 결과물 활용).

### 8.2 화면 클릭

1. 사이드바 → **"실행 이력"**
2. 시나리오 7 의 신규 run 1행에서 **별표(☆)** 아이콘 클릭 → "기준 결과" 등록 → ★ 로 변경
3. 사이드바 → **"시나리오 라이브러리"** → 같은 시나리오 ▶ 실행 (재실행)
4. 다시 **"실행 이력"** → 신규 run 우측에 "diff 발견" 마크 확인 (없으면 동일 결과 = 회귀 없음)
5. 사이드바 → **"재실행 비교 (차이 검증)"**
6. **Baseline** select → 첫 run, **Candidate** select → 두 번째 run
7. **▶ 비교** 클릭

### 8.3 기대 결과

- 비교 결과 표시:
  - 첫 실행이 결정적이라면 "회귀 없음" (emerald 카드)
  - Hypothesis 보조 입력이 있으면 일부 필드 차이 (`slab.targetWidth` 등)
- 필드별 Diff 테이블: 경로 / Before / After / 상태 아이콘

### 8.4 실패 시
- "Baseline 옵션이 비어있음" → 별표 등록 누락. 다시 실행 이력에서 ☆ 클릭

---

## 시나리오 9 — OntologyBridge 도메인 용어 검색 + AI 어시스턴트

**검증 포인트**: 비즈니스 용어 → 영향 step 매핑 + 자연어로 시나리오 추천이 동작하는가?

### 9.1 화면 클릭 — 용어 검색

1. 사이드바 → **"온톨로지 브릿지"**
2. "용어 검색" 섹션 → input 에 `실수율` 입력 → **검색** 클릭
3. 결과: 영향 step 8개 (productivity, slab_count, slab_weight, ...) + 추천 시나리오 카드 N개
4. 영향 step 중 하나의 **"샌드박스로 →"** 클릭 → SandboxPanel 자동 jump + step 사전 채움 + preset inputs 적용

### 9.2 화면 클릭 — AI 어시스턴트

1. 같은 패널 상단 amber 카드 → textarea 에 다음 입력:
   > "HR 실수율을 0.85 로 줄였을 때 Slab 매수가 어떻게 바뀌는지 보고 싶어"
2. **추천 받기** 클릭 → 약 3~10초 대기
3. Draft 카드 등장: 제목 / 설명 / step_id (`pipeline_full`) / inputs (`rules.hr=0.85`)
4. **시나리오로 저장** 클릭 → ScenarioLibrary 에 신규 entry 추가 확인

### 9.3 기대 결과
- 용어 카탈로그 16종이 자동완성 리스트로 노출
- LLM 미가용 시에도 fallback 카탈로그 draft 가 반환되어 동작 (LLM key 없어도 OK)

### 9.4 실패 시
- 검색 결과 0건 → 용어가 카탈로그에 없는 미등록어. `backend/simulation/ontology_bridge/bridge.py` 의 16종 alias 표 확인
- "AI 어시스턴트가 늦음" → LLM cold start. 첫 호출은 5~15초 정상

---

## 시나리오 10 — 코드 내비게이터 → 시뮬 핸드오프

**검증 포인트**: 자연어 → 자바 코드 위치 매핑 + ⚡ 핸드오프가 동작하는가?

### 10.1 화면 클릭

1. 사이드바 → **"코드 내비게이터"**
2. 빠른 질의 버튼 **"단중상한이 어디서 결정돼?"** 클릭 (또는 자유 입력)
3. 결과:
   - 매칭 키워드 chip: `단중상한`
   - 위치 탭: `SdSecondWgtHighAction.execute` (가능 시 다른 후보)
   - 코드 미리보기 ±20줄 (Java syntax highlight)
4. 우상단 **⚡ 이 step 시뮬레이션 →** 클릭

### 10.2 기대 결과
- SandboxPanel 자동 jump
- step 자동 선택: `second_wgt` (또는 매핑된 step)
- 별도 입력 없이 ▶ 실행 가능

### 10.3 실패 시
- 매칭 0건 → 다른 빠른 질의 버튼 사용 ("누적 실수율", "분할수")
- preview 비어있음 → `sample-repos/slab-design/` 경로 미존재 (`ls sample-repos/slab-design/CLAUDE.md` 확인)

---

## 시나리오 11 — Time-travel scrubber (신박 2호)

**검증 포인트**: 케이스 시퀀스를 영상처럼 스크럽하면서 어느 시점에 fail 비율이 급등하는지 시각화되는가?

### 11.1 화면 클릭

1. 사이드바 → **"안전 가상 실행 (샌드박스)"**
2. step → `slab_count`, 케이스 유형 [정상, 경계, 오류] 모두, 테스트 수 `30`
3. 룰 변경 펼치기 → HR 실수율 `0.30` 입력 (극단)
4. **▶ 실행** → SSE 90건 진행 → 완료
5. 결과 영역 하단 **TimelineScrubber** 자동 노출 확인

### 11.2 스크러버 조작

1. cursor 슬라이더 좌→우 드래그 → 누적 matched/failed 비율 진행바가 실시간 갱신
2. **재생** 버튼 클릭 → 60ms 자동 진행
3. 현재 cursor 위치의 case input / actual_output 이 JsonTable 미리보기로 갱신

### 11.3 기대 결과

- "정상 분포 입력 + HR 0.30" 조합에서 처음 fail 이 등장하는 cursor 위치를 시각적으로 식별 가능
- 케이스 유형별(정상/경계/오류) 진행 게이지가 색상별 누적

### 11.4 실패 시
- scrubber 미노출 → 실행 미완료. 진행 100% 도달 후 등장
- JsonTable 비어있음 → `useAgent2Stream.casesDetailed` payload 누락. 새로고침 후 재실행

---

## 시나리오 12 — Auto-PR 자바 방어 코드 (신박 3호)

**검증 포인트**: 실패 케이스 → LLM 패치 제안 + unified diff color-coded + 클립보드 복사가 동작하는가?

### 12.1 사전 조건 — 매핑된 step 사용
현재 매핑 (`frontend/src/lib/simulation/autoPrApi.ts:59-72`):
- `thickness` ↔ `SdThicknessAction.execute`
- `slab_count` ↔ `SdSlabCountAction.execute`

**다른 step 으로 매핑 추가 (선택)**:
```typescript
// autoPrApi.ts:59-72 STEP_TO_TARGET 에 추가
width_range: {
  java_path: "sample-repos/slab-design/.../action/SdWidthRangeAction.java",
  method_name: "execute",
  class_name: "SdWidthRangeAction",
},
```

### 12.2 화면 클릭

1. **"안전 가상 실행 (샌드박스)"** → step `slab_count` → [오류] 만 체크 → 5건 실행
2. 결과 영역 하단 **실패 케이스 섹션** 으로 스크롤
3. 실패 케이스 카드 상단 **AutoPRCard** 노출 확인
4. **패치 제안 받기** 클릭 → 약 5~15초 대기 (LLM 호출)

### 12.3 기대 결과

- **rationale** 카드: 왜 이런 패치가 필요한지 자연어 설명
- **unified diff** color-coded:
  - `+` 녹색 (추가 라인)
  - `-` 빨강 (제거 라인)
  - `@@` 보라 (hunk 헤더)
- **patched method** details 펼침 → 전체 자바 메서드 본문
- **risk_notes** amber 박스 (위험 항목)
- **클립보드 복사** 버튼 → 복사 토스트

### 12.4 매핑 없는 step
- step `validator` 같이 `STEP_TO_TARGET` 미보유 → "비활성 안내" 메시지 ("이 step 은 자바 매핑이 없습니다")

### 12.5 실패 시
- "패치 제안 받기" 응답이 fallback stub → LLM API key 미설정. `LITELLM_MODEL` env 확인. fallback 도 자바 본문 + 실패 케이스 주석 형태로 반환됨 (의도된 동작)

---

## 시나리오 13 — PlantMapping 마이그레이션 라이브 데모

**검증 포인트**: 홈 대시보드의 라이브 데모가 즉시 실행되어 Before/After diff 가 보이는가?

### 13.1 화면 클릭

1. 사이드바 → **"홈 (개요)"**
2. 화면 중간 **"라이브 데모 — PlantMapping Migration"** 카드 영역
3. 입력 미리보기 확인: smCd, productType, 마이그 후 매핑값
4. **지금 실행** 버튼 클릭

### 13.2 기대 결과

- 100ms 폴링으로 잡 완료 검출
- **MigrationDiffCard** 등장:
  - Before: 기존 매핑 (예: A → CC1/M1)
  - After: 마이그 후 매핑
  - 깨짐 감지 강조 (있다면 빨강)

### 13.3 실패 시
- 응답 없음 → AsyncJobQueue 미가동. 백엔드 로그에서 jobs_router 등록 확인

---

## 시나리오 14 — EDGING_SPEC `*` fallback 누락

**검증 포인트**: EdgingSpec wildcard `*` row 를 제거하면 step 2 가 fail 하는가?

### 14.1 데이터 주입

**[PG 모드]** — 가장 직관적:
```sql
DELETE FROM edging_spec WHERE edging_group_cd = '*';
```
복구: 「DB 시드 초기화」 클릭. 또는 다시 INSERT.

⚠️ **중요**: registry.py 의 `_repo_edging_spec` 은 `include_wildcard=False` 인자를 받으면 **항상 in-memory** 로 fallback 합니다 (PG 시드는 wildcard 포함). 따라서 width_range step 호출 시 `include_wildcard=True` (기본) 로 두면 PG 의 변경이 반영되고, `include_wildcard=False` 면 fixtures.py 의 in-memory 가 작동.

**[in-memory 모드]** — `_run_width_range` 호출 시 `include_wildcard=False` 로 input 에 추가:
```json
{"include_wildcard": false}
```
또는 fixtures 수정:
```python
def make_default_edging_spec(include_wildcard=False):  # ★ default 변경
```

### 14.2 화면 클릭

1. **"안전 가상 실행 (샌드박스)"** → step `width_range` → 정상 1건

### 14.3 기대 결과
- fail=1, `error_code: "DG103"` (EDGING_GROUP 미존재) 또는 `EdgingSpecMissingError` 변환 메시지

### 14.4 정리
- include_wildcard=True 로 복구

---

## 시나리오 16 — PG 직접 INSERT (사용자 정의 주문 + 신규 마스터 row)

**검증 포인트** (★ PG 모드 전용): SQL 클라이언트로 새 row 추가 후 시뮬이 즉시 그 데이터를 사용하는가?

### 16.1 데이터 주입 — 새 주문 + 새 CastSpec

```sql
-- DBeaver / psql 접속:
-- postgresql://simulation:simulation_dev@localhost:5434/simulation

-- 1) 사용자 정의 주문 (정상 + 큰 폭)
INSERT INTO order_os (cmp_cd, org_cd, order_no, stock_code,
                      order_width, order_length, order_wgt_low, order_wgt_high,
                      pkg_wgt_low, pkg_wgt_high,
                      confirmed_plant_cd, product_type_cd, grade_cd, customer_cd,
                      sm_due, hr_due, hrf_due, anl1_due, work_due)
  VALUES ('K', 'K01', 'ORD-USER-WIDE', 0,
          1800, 5000, 12, 30, 8, 25,
          'KKKK    ', 'A001', 'G01', 'C001',
          NOW() + INTERVAL '30 days', NOW() + INTERVAL '30 days',
          NOW() + INTERVAL '30 days', NOW() + INTERVAL '30 days',
          NOW() + INTERVAL '30 days');

-- 2) 새 CastSpec — 기존에 없던 두께 (300mm)
INSERT INTO cast_spec
  (cmp_cd, org_cd, sm_plant_cd, cast_cd, machine_cd, prod_type_cd,
   slab_thickness, width_low, width_high, length_low, length_high)
  VALUES ('K', 'K01', 'K', 'CC2', 'M2', 'A001',
          300, 1500, 2000, 3000, 13000);
```

검증: `curl http://localhost:8001/api/simulation/orders` 로 신규 주문 확인.

### 16.2 화면 클릭

1. 사이드바 → **"안전 가상 실행 (샌드박스)"**
2. **대상 Step** → `pipeline_full`
3. 케이스 유형 [정상] / 테스트 수 1
4. 화면 직접 입력 가능한 영역에 `order.orderNo = "ORD-USER-WIDE"` 지정 (또는 시나리오 라이브러리에 신규 시나리오로 등록)
5. **▶ 실행**

### 16.3 기대 결과

- pipeline_full 정상 통과
- step 1 (`thickness`) 결과: `slab.slabThickness` 가 새로 INSERT 한 두께 값 (300) 반영 (smPlantCd/castCd/machineCd 가 매칭되는 경우)
- 또는 매칭 키 다른 row 면 기존 220 그대로

### 16.4 정리

```sql
DELETE FROM order_os WHERE order_no = 'ORD-USER-WIDE';
DELETE FROM cast_spec WHERE machine_cd = 'M2';
```
또는 「DB 시드 초기화」.

### 16.5 실패 시
- 새 INSERT 가 안 보임 → ConnectionPool 캐시. 백엔드 재기동 또는 트랜잭션 commit 확인.
- 매칭 미스 → CastSpec PK 키 11개 중 어느 것이라도 다르면 매칭 안 됨. cast_cd / machine_cd / sm_plant_cd 정확히 일치하는지

---

## 시나리오 15 — 룰 자체 코드 변경 (자바 미러 step 수정)

**검증 포인트**: Python 미러 step 의 룰 한 줄 변경이 실제 결과에 반영되는가?

### 15.1 데이터 주입

**수정 위치**: `backend/simulation/sandbox/fixtures/steps/` 의 mirror step (예: `productivity.py` 등 — 정확한 파일명은 디렉토리 확인).

예) productivity step 의 활성 공정 곱 곱 공식 변경:
```python
# 기존
return hr * hrf * anl1

# 변경 (실수율 효과 강제 증폭)
return (hr * hrf * anl1) ** 2
```

### 15.2 화면 클릭

1. 시나리오 6 (HR 0.93→0.50 영향 분석) 재실행
2. 동일 sample_size, 동일 새 값 → 결과 분포가 이전과 다른지 확인

### 15.3 baseline 비교

1. 변경 **전** 결과를 baseline 으로 저장 (시나리오 8 절차)
2. 코드 수정 후 재실행
3. RegressionPanel 에서 baseline ↔ candidate 비교 → 필드 단위 diff 다수 등장

### 15.4 정리
- `git checkout backend/simulation/sandbox/fixtures/steps/`

---

# D. 일반 트러블슈팅

| 증상 | 원인 / 대응 |
|---|---|
| `SIMULATION_SKIP_ONTOLOGY=1` 인데 ontology 응답 시도 | uvicorn 재기동 (env 변수 갱신) |
| 프론트 SSE 끊김 | nginx buffering OFF, dev mode 직접 백엔드 호출 (CORS 확인) |
| Plotly 번들 미로드 | DevTools console 확인, dynamic import (`ssr:false`) 동작 검증 |
| Hypothesis 매번 다른 fail case | `.example()` 는 random sample — 의도된 동작 |
| 시나리오 라이브러리 비어있음 | 헤더 "초기화" 클릭 (YAML 시드 적재) |
| 실행 이력 폴링 멈춤 | 4초 setInterval 체크. 다른 패널로 이동했다 다시 옴 |
| Auto-PR 응답이 자바 주석만 | fallback stub. LLM API key 미설정. 의도된 동작 |
| RegressionPanel 빈 baseline 옵션 | 실행 이력에서 별표 클릭으로 baseline 등록 누락 |

---

# E. 시연 권장 순서 (검증을 데모로 전환할 때)

1. 시나리오 1 (정상 통과) — 0:00–0:30
2. 시나리오 6 (영향 분석 + What-if 슬라이더) — 0:30–2:00
3. 시나리오 11 (Time-travel scrubber) — 2:00–3:00
4. 시나리오 12 (Auto-PR 패치) — 3:00–4:30
5. 시나리오 9 (OntologyBridge AI 어시스턴트) — 4:30–5:30
6. 시나리오 10 (코드 내비게이터 핸드오프) — 5:30–6:30
7. 마무리 — "정적 분석은 못 보던 동적 영향 + LLM 자동 패치까지 한 화면" — 6:30–7:00

---

# F. 검증 체크리스트 (15종 PASS 마킹용)

- [ ] 시나리오 1 — 정상 주문 통과
- [ ] 시나리오 2 — DG001 재고주문
- [ ] 시나리오 3 — DG003 포장단중 (fixtures 수정)
- [ ] 시나리오 4 — DG101 CAST_SPEC 미존재 (Repo 비우기)
- [ ] 시나리오 5 — DG109 A-a 루프 끝까지 실패
- [ ] 시나리오 6 — HR 0.93→0.50 영향 분석 + What-if 슬라이더 ★
- [ ] 시나리오 7 — 시나리오 라이브러리 1-click + Export/Import
- [ ] 시나리오 8 — baseline 등록 + 회귀 검증
- [ ] 시나리오 9 — OntologyBridge 용어 검색 + AI 어시스턴트
- [ ] 시나리오 10 — 코드 내비게이터 → 시뮬 핸드오프
- [ ] 시나리오 11 — Time-travel scrubber ★
- [ ] 시나리오 12 — Auto-PR 자바 방어 코드 ★
- [ ] 시나리오 13 — PlantMapping 마이그 라이브 데모
- [ ] 시나리오 14 — EDGING_SPEC wildcard 제거
- [ ] 시나리오 15 — 자바 미러 step 코드 변경
- [ ] 시나리오 16 — PG 직접 INSERT (사용자 정의 주문 + 신규 CastSpec) ★ PG 전용

체크 완료 후 발견 이슈는 `toClaude/simulation/CHANGES.md` 에 `[ ]` 로 기록 → 다음 세션에서 우선 처리.
