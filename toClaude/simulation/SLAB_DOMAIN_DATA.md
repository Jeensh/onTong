# slab-design-real_v2 — 도메인 데이터 reference

> 시뮬레이션 에이전트가 "현 시스템에 어떤 table 과 row 가 있는지" 를
> 사용자에게 보여주기 위한 reference. JPA Entity (`*Jpo.java` / `*Entity.java`)
> + seed SQL (`01_master.sql` + `02_orders.sql`) 합성.

---

## H2 환경

- `jdbc:h2:mem:slabdesign;MODE=Oracle;DB_CLOSE_DELAY=-1`
- ddl-auto: `create-drop` (JPA entity → schema 자동 생성)
- seed: `db/seed/01_master.sql` + `db/seed/02_orders.sql` (Spring SQL init)
- H2 console: `http://127.0.0.1:8080/h2-console` (user=`sa`, pw 없음)
- in-memory · same-JVM 만 접근 가능 → 외부 JDBC 불가능. 시뮬에이전트는 JPA 파일
  + seed SQL 을 **read-only 파싱** 으로 surface.

---

## 14 Tables

| 카테고리 | TABLE | JPA class | PK 컬럼 | 컬럼수 | seed row |
|---|---|---|---|---|---|
| **std** (기준) | `CAST_SPEC` | CastSpecJpo | CMP,ORG,SM,CAST,MACHINE,PRODUCT | 13 | 2 |
| std | `CUSTOMER_STD` | CustomerStdJpo | CMP,ORG,CUSTOMER | 7 | 2 |
| std | `EDGING_GROUP` | EdgingGroupJpo | CMP,ORG,GROUP_CD | 9 | 2 |
| std | `EDGING_SPEC` | EdgingSpecJpo | CMP,ORG,GROUP_CD | 5 | 3 |
| std | `HR_MAX_WGT` | HrMaxWgtJpo | CMP,ORG,GRADE | 6 | 5 |
| std | `HR_MIN_WGT` | HrMinWgtJpo | CMP,ORG,GRADE | 6 | 5 |
| std | `HR_SPEC` | HrSpecJpo | CMP,ORG,GRADE | 8 | 2 |
| std | `SD_PRODUCTIVITY_STD` | SdProductivityStdJpo | CMP,ORG,PROC,GRADE | 7 | 10 |
| **order** (주문) | `ORDER_OS` | SDOrderOsJpo | CMP,ORG,ORDER_NO | 19 | 5 |
| order | `ORDER_OM` | SDOrderOmJpo | CMP,ORG,ORDER_NO | 15 | 5 |
| order | `ORDER_QD` | SDOrderQdJpo | CMP,ORG,ORDER_NO | 9 | 5 |
| order | `ORDER_CHEMICAL` | SDOrderChemicalJpo | CMP,ORG,ORDER_NO | 27 | 5 |
| **result** | `SLAB_RESULT` | SlabResultJpo | CMP,ORG,SLAB_NO | 27 | 0 (런타임 생성) |
| **history** | `SLAB_DESIGN_HIST` | SlabDesignHistJpo | CMP,ORG,ORDER_NO,SLAB_NO | 10 | 0 (런타임 생성) |

총 14 tables · seed row 48 건 · 런타임 추가 (SLAB_RESULT, SLAB_DESIGN_HIST) 는 설계 실행 시 적재.

---

## 핵심 row 예 — CAST_SPEC (연주설비사양)

```
CMP_CD ORG_CD SM_CD CAST_CD MACHINE_CD PRODUCT_CD  SLAB_THICKNESS  WIDTH_LOW  WIDTH_HIGH  LENGTH_LOW  LENGTH_HIGH  WGT_LOW    WGT_HIGH
K      1      K     CC1     M1         COIL        230.00          800.00     2000.00     4000.00     12000.00     10000.000  30000.000
K      1      K     CC1     M1         FS          250.00          800.00     2200.00     4000.00     12000.00     10000.000  32000.000
```

→ Step 1 `SdThicknessAction` 이 `(cmp=K, org=1, SM=K, cast=CC1, machine=M1, product=COIL)`
   조회 시 `SLAB_THICKNESS=230` 반환. golden S1 의 `slabThickness=230` 일치.

---

## 주문 1건 예 — `ORD20260510001` (S1)

| Table | 핵심 컬럼 = 값 |
|---|---|
| `ORDER_OS` | `osProgress=C, confirmedPlantCd='K1 K    ', designPendQty=10000, designPendQtyLow=8000, designPendQtyHigh=12000` |
| `ORDER_OM` | `orderWgtLow=10000, orderWgtHigh=12000, orderWidth=1200, orderLength=8500, productCd=COIL, customerCd=CUST-001, pkgWgt 8000~18000` |
| `ORDER_QD` | `gradeCd=SS400` |
| `ORDER_CHEMICAL` | (강종별 화학성분 5종 — C/Si/Mn/P/S 등) |

5 시나리오 모두 같은 4 table 에 1 row 씩 (총 5×4=20 rows).

---

## 시뮬레이션 에이전트에서 보기

브라우저: `http://localhost:3000/?section=simulation&view=simulation` →
우측 패널 하단 **"slab-design 도메인 데이터"** 섹션
- 카테고리별 (기준 / 주문 / 결과 / 이력) table chip 목록
- 각 chip 의 row 카운트 표시
- click → schema (column · type · PK 표시) + sample row 표

API:
```bash
# 14 table 목록
curl http://127.0.0.1:8001/api/section3/simulation/data/tables | jq

# CAST_SPEC schema + rows
curl http://127.0.0.1:8001/api/section3/simulation/data/table/CAST_SPEC | jq
```

---

## 실제 결과 보기 (Java :8080)

런타임에 채워지는 SLAB_RESULT 는 H2 in-memory 라 직접 조회 불가. 대신 Java REST API:

```bash
curl 'http://127.0.0.1:8080/api/sd/working/single?trace=true' \
  -H 'Content-Type: application/json' \
  -d '{"cmpCd":"K","orgCd":"1","orderNo":"ORD20260510001"}'
```

응답 의 `slabResults[0]` 가 곧 SLAB_RESULT row.

시뮬에이전트의 `executed_full_design` 흐름 (시나리오 ①) 이 이 API 를 호출하여
slabThickness / slabWidth / slabLength / slabWgt 등을 카드로 surface.

---

## 변경 후 비교 (compare_runs)

지금은 단일 method transpile 의 fixture override 만 지원. 향후 작업:
- seed SQL 의 master 데이터 (CAST_SPEC.SLAB_THICKNESS 등) 를 변경한 뒤
- 별도 H2 인스턴스에 같은 schema + 변경된 seed 적용
- 두 Java 서버 인스턴스에서 같은 주문 실행 → diff
- 또는 H2 의 동적 UPDATE → 같은 서버에서 변경 전/후 실행 후 diff
